"""Puhejakson reititys: herätesanakomennot tai sanelutekstin syöttö."""

from collections.abc import Sequence
import logging

from puhis.core.actions import (
    AppLauncherProtocol,
    CommandType,
    InputAction,
    KeyboardInjectorProtocol,
    KeyAction,
    ParsedCommand,
    TextAction,
    UtteranceResult,
    VirtualKey,
    WindowManagerProtocol,
)
from puhis.core.app_state import AssistantMode
from puhis.core.command_parser import parse_command
from puhis.core.config_store import AppConfig
from puhis.core.llm_intent import IntentInterpreterProtocol
from puhis.core.text_transformer import transform_dictation
from puhis.core.window_registry import WindowEntry, WindowRegistry

logger = logging.getLogger(__name__)

_NO_LEADING_SPACE_CHARS = frozenset({".", ",", "?", "!", ":", ";", ")", "]", "}"})
_NO_TRAILING_SPACE_CHARS = frozenset({"(", "[", "{"})
_RESET_SPACE_KEYS = frozenset({
    VirtualKey.ENTER,
    VirtualKey.TAB,
    VirtualKey.SPACE,
    VirtualKey.BACKSPACE,
    VirtualKey.CTRL_BACKSPACE,
})
_DIRECT_STOP_DICTATION_PHRASES = frozenset({
    ("lopeta", "sanelu"),
    ("lopeta", "sanelut"),
    ("lopeta", "sanelun"),
    ("lopettaa", "sanelu"),
    ("sanelu", "pois"),
    ("pysäytä", "sanelu"),
})
_DIRECT_STOP_STRIP_CHARS = ".,!?:;\"'()[]{}-–—"


class UtteranceRouter:
    """Ohjaa tunnistetun puheen joko Windows-komennoksi tai sanelusyötteeksi."""

    def __init__(
        self,
        config: AppConfig,
        window_registry: WindowRegistry,
        keyboard_injector: KeyboardInjectorProtocol,
        window_manager: WindowManagerProtocol,
        app_launcher: AppLauncherProtocol,
        intent_interpreter: IntentInterpreterProtocol | None = None,
    ) -> None:
        self._config = config
        self._registry = window_registry
        self._keyboard = keyboard_injector
        self._windows = window_manager
        self._launcher = app_launcher
        self._intent_interpreter = intent_interpreter
        self._needs_leading_space = False

    def update_config(self, config: AppConfig) -> None:
        """Päivittää aktiiviset asetukset (herätesana, avainsanat)."""
        self._config = config

    def handle_utterance(self, text: str, current_mode: AssistantMode) -> UtteranceResult:
        """Käsittelee yhden tunnistetun puhejakson."""
        _, result = self.handle_candidates([text], current_mode)
        return result

    def handle_candidates(
        self,
        candidates: Sequence[str],
        current_mode: AssistantMode,
    ) -> tuple[str, UtteranceResult]:
        """Valitsee parhaan tunnistusehdokkaan (komento ennen vapaata tekstiä) ja suorittaa sen."""
        cleaned = [c.strip() for c in candidates if isinstance(c, str) and c.strip()]
        if not cleaned:
            return "", UtteranceResult(handled=False, success=True, message="")

        if current_mode is AssistantMode.MUTED:
            return cleaned[0], UtteranceResult(
                handled=False,
                success=True,
                message="Mikrofoni on mykistetty.",
            )

        known_aliases = [entry.alias for entry in self._registry.list_entries()]
        known_apps = list(self._config.app_aliases.keys())

        # Etsitään ensin komento kaikista Googlen/selaimen antamista ehdokkaista.
        best_command: tuple[str, ParsedCommand] | None = None
        fallback_command: tuple[str, ParsedCommand] | None = None
        for candidate in cleaned:
            cmd = parse_command(
                candidate,
                wake_word=self._config.wake_word,
                known_window_aliases=known_aliases,
                known_app_aliases=known_apps,
                require_wake_word=(current_mode is not AssistantMode.COMMAND),
            )
            if cmd is None:
                continue
            if cmd.command_type not in (CommandType.UNKNOWN, CommandType.WAKE):
                best_command = (candidate, cmd)
                break
            if fallback_command is None:
                fallback_command = (candidate, cmd)

        chosen_cmd = best_command or fallback_command
        if self._should_try_llm_fallback(chosen_cmd, current_mode):
            llm_cmd = self._try_llm_fallback(
                cleaned,
                chosen_cmd=chosen_cmd,
                known_aliases=known_aliases,
                known_apps=known_apps,
            )
            if llm_cmd is not None:
                chosen_cmd = llm_cmd

        if chosen_cmd is not None:
            chosen_text, command = chosen_cmd
            self._needs_leading_space = False
            return chosen_text, self._execute_command(command, current_mode=current_mode)

        if current_mode is not AssistantMode.DICTATING:
            return cleaned[0], UtteranceResult(handled=False, success=True, message="")

        for candidate in cleaned:
            if _is_direct_stop_dictation(candidate):
                self._needs_leading_space = False
                logger.info("Suora sanelun lopetuskomento ilman herätesanaa")
                return candidate, UtteranceResult(
                    handled=True,
                    success=True,
                    message="Sanelu pysäytetty",
                    new_mode=AssistantMode.IDLE,
                )

        return cleaned[0], self._execute_dictation(cleaned[0])

    def _should_try_llm_fallback(
        self,
        chosen_cmd: tuple[str, ParsedCommand] | None,
        current_mode: AssistantMode,
    ) -> bool:
        if self._intent_interpreter is None or not self._config.llm_enabled:
            return False
        if chosen_cmd is not None:
            return chosen_cmd[1].command_type is CommandType.UNKNOWN
        return current_mode is AssistantMode.COMMAND

    def _try_llm_fallback(
        self,
        candidates: Sequence[str],
        *,
        chosen_cmd: tuple[str, ParsedCommand] | None,
        known_aliases: Sequence[str],
        known_apps: Sequence[str],
    ) -> tuple[str, ParsedCommand] | None:
        assert self._intent_interpreter is not None
        text_for_llm = chosen_cmd[0] if chosen_cmd is not None else candidates[0]
        interpreted = self._intent_interpreter.interpret_intent(
            text_for_llm,
            known_window_aliases=known_aliases,
            known_app_aliases=known_apps,
        )
        if interpreted is None or interpreted.command_type is CommandType.UNKNOWN:
            return None
        logger.info("LLM tulkitsi komennon: %s (%s)", interpreted.command_type.value, interpreted.target)
        return text_for_llm, interpreted

    def _execute_command(
        self,
        command: ParsedCommand,
        *,
        current_mode: AssistantMode = AssistantMode.IDLE,
    ) -> UtteranceResult:
        result = self._dispatch_command(command)
        # Jos sanelutilassa annetaan jokin muu käsky (esim. save t1 / fokus / piilota),
        # sanelu päättyy automaattisesti, ellei komento itse kytkenyt uutta tilaa.
        if current_mode is AssistantMode.DICTATING and result.new_mode is None:
            return UtteranceResult(
                handled=result.handled,
                success=result.success,
                message=result.message,
                new_mode=AssistantMode.IDLE,
            )
        return result

    def _dispatch_command(self, command: ParsedCommand) -> UtteranceResult:
        cmd_type = command.command_type
        target = command.target

        if cmd_type is CommandType.WAKE:
            logger.info("Herätesana tunnistettu -> kuuntelutila (COMMAND)")
            return UtteranceResult(
                handled=True,
                success=True,
                message="KUUNTELEN!",
                new_mode=AssistantMode.COMMAND,
            )

        if cmd_type is CommandType.START_DICTATION:
            logger.info("Komento: sanelu päälle")
            return UtteranceResult(
                handled=True,
                success=True,
                message="Sanelu päällä",
                new_mode=AssistantMode.DICTATING,
            )

        if cmd_type is CommandType.STOP_DICTATION:
            logger.info("Komento: sanelu seis")
            return UtteranceResult(
                handled=True,
                success=True,
                message="Sanelu pysäytetty",
                new_mode=AssistantMode.IDLE,
            )

        if cmd_type is CommandType.MUTE:
            logger.info("Komento: mykistä")
            return UtteranceResult(
                handled=True,
                success=True,
                message="Mikrofoni mykistetty",
                new_mode=AssistantMode.MUTED,
            )

        if cmd_type is CommandType.SAVE_WINDOW:
            return self._handle_save_window(target)

        if cmd_type is CommandType.FOCUS_WINDOW:
            return self._handle_focus_window(target)

        if cmd_type is CommandType.HIDE_WINDOW:
            return self._handle_hide_window(target)

        if cmd_type is CommandType.LAUNCH_APP:
            if not target:
                return UtteranceResult(
                    handled=True,
                    success=False,
                    message="Sovelluksen nimi puuttuu.",
                )
            ok, msg = self._launcher.launch(target)
            if ok:
                return UtteranceResult(
                    handled=True,
                    success=True,
                    message=f"{msg} – sanelu päällä",
                    new_mode=AssistantMode.DICTATING,
                )
            return UtteranceResult(handled=True, success=False, message=msg)

        label = target or command.raw_text.strip()
        logger.warning("Tuntematon herätesanakomento: %s", label)
        return UtteranceResult(
            handled=True,
            success=False,
            message=f"Tuntematon komento: {label}",
        )

    def _handle_save_window(self, alias: str | None) -> UtteranceResult:
        if not alias:
            return UtteranceResult(
                handled=True,
                success=False,
                message="Ikkuna-alias puuttuu.",
            )
        active = self._windows.get_active_window()
        if active is None or active.hwnd <= 0:
            return UtteranceResult(
                handled=True,
                success=False,
                message="Aktiivista ikkunaa ei löytynyt.",
            )
        try:
            entry = self._registry.save(alias, active)
        except ValueError as exc:
            logger.warning("Ikkuna-aliaksen tallennus epäonnistui: %s", exc)
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Virheellinen ikkuna-alias: {alias}",
            )

        title = entry.window.title or entry.window.process_name or f"HWND {entry.window.hwnd}"
        logger.info("Tallennettu ikkuna %s -> %s (%d)", entry.alias, title, entry.window.hwnd)
        return UtteranceResult(
            handled=True,
            success=True,
            message=f"Tallennettu {entry.alias}: {title}",
        )

    def _handle_focus_window(self, alias: str | None) -> UtteranceResult:
        if not alias:
            return UtteranceResult(
                handled=True,
                success=False,
                message="Ikkuna-alias puuttuu.",
            )
        entry = self._resolve_valid_window_entry(alias)
        if isinstance(entry, UtteranceResult):
            return entry
        if not self._windows.focus_window(entry.window.hwnd):
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Ikkunan {entry.alias} aktivointi epäonnistui.",
            )
        return UtteranceResult(
            handled=True,
            success=True,
            message=f"→ {entry.alias}",
        )

    def _handle_hide_window(self, alias: str | None) -> UtteranceResult:
        if alias is None:
            active = self._windows.get_active_window()
            if active is None or active.hwnd <= 0:
                return UtteranceResult(
                    handled=True,
                    success=False,
                    message="Aktiivista ikkunaa ei löytynyt.",
                )
            ok = self._windows.minimize_window(active.hwnd)
            return UtteranceResult(
                handled=True,
                success=ok,
                message="Ikkuna piilotettu" if ok else "Ikkunan piilotus epäonnistui.",
            )

        entry = self._resolve_valid_window_entry(alias)
        if isinstance(entry, UtteranceResult):
            return entry
        ok = self._windows.minimize_window(entry.window.hwnd)
        return UtteranceResult(
            handled=True,
            success=ok,
            message=f"Piilotettu {entry.alias}" if ok else f"Ikkunan {entry.alias} piilotus epäonnistui.",
        )

    def _resolve_valid_window_entry(self, alias: str) -> WindowEntry | UtteranceResult:
        entry = self._registry.get(alias)
        if entry is None:
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Tuntematon ikkuna: {alias}",
            )
        if self._windows.is_window_valid(entry.window.hwnd):
            return entry
        finder = getattr(self._windows, "find_matching_window", None)
        if callable(finder):
            matched = finder(entry.window.process_name, entry.window.title)
            if matched is not None:
                return self._registry.save(entry.alias, matched)
        self._registry.remove(alias)
        return UtteranceResult(
            handled=True,
            success=False,
            message=f"Ikkuna {entry.alias} on suljettu.",
        )

    def _execute_dictation(self, text: str) -> UtteranceResult:
        actions = transform_dictation(text, self._config.keywords)
        if not actions:
            return UtteranceResult(handled=False, success=True, message="")

        if self._needs_leading_space and isinstance(actions[0], TextAction):
            first_text = actions[0].text
            if first_text and not first_text[0].isspace() and first_text[0] not in _NO_LEADING_SPACE_CHARS:
                actions = [TextAction(text=" " + first_text), *actions[1:]]

        ok = self._keyboard.send_actions(actions)
        if not ok:
            return UtteranceResult(
                handled=True,
                success=False,
                message="Näppäinsyöttö epäonnistui.",
            )

        self._update_spacing_state(actions)
        return UtteranceResult(
            handled=True,
            success=True,
            message="Sanelu syötetty",
        )

    def _update_spacing_state(self, actions: list[InputAction]) -> None:
        last = actions[-1]
        if isinstance(last, TextAction):
            self._needs_leading_space = (
                bool(last.text)
                and not last.text[-1].isspace()
                and last.text[-1] not in _NO_TRAILING_SPACE_CHARS
            )
        elif isinstance(last, KeyAction):
            self._needs_leading_space = last.key not in _RESET_SPACE_KEYS


def _is_direct_stop_dictation(text: str) -> bool:
    tokens = tuple(
        tok
        for raw in text.split()
        if (tok := raw.strip(_DIRECT_STOP_STRIP_CHARS).lower())
    )
    return tokens in _DIRECT_STOP_DICTATION_PHRASES
