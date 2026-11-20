"""Puhejakson reititys: herätesanakomennot tai sanelutekstin syöttö."""

import logging

from puhis.core.actions import (
    AppLauncherProtocol,
    CommandType,
    KeyboardInjectorProtocol,
    ParsedCommand,
    UtteranceResult,
    WindowManagerProtocol,
)
from puhis.core.app_state import AssistantMode
from puhis.core.command_parser import parse_command
from puhis.core.config_store import AppConfig
from puhis.core.text_transformer import transform_dictation
from puhis.core.window_registry import WindowRegistry

logger = logging.getLogger(__name__)


class UtteranceRouter:
    """Ohjaa tunnistetun puheen joko Windows-komennoksi tai sanelusyötteeksi."""

    def __init__(
        self,
        config: AppConfig,
        window_registry: WindowRegistry,
        keyboard_injector: KeyboardInjectorProtocol,
        window_manager: WindowManagerProtocol,
        app_launcher: AppLauncherProtocol,
    ) -> None:
        self._config = config
        self._registry = window_registry
        self._keyboard = keyboard_injector
        self._windows = window_manager
        self._launcher = app_launcher

    def update_config(self, config: AppConfig) -> None:
        """Päivittää aktiiviset asetukset (herätesana, avainsanat)."""
        self._config = config

    def handle_utterance(self, text: str, current_mode: AssistantMode) -> UtteranceResult:
        """Käsittelee yhden tunnistetun puhejakson."""
        if not text or not text.strip():
            return UtteranceResult(handled=False, success=True, message="")

        if current_mode is AssistantMode.MUTED:
            return UtteranceResult(
                handled=False,
                success=True,
                message="Mikrofoni on mykistetty.",
            )

        known_aliases = [entry.alias for entry in self._registry.list_entries()]
        command = parse_command(
            text,
            wake_word=self._config.wake_word,
            known_window_aliases=known_aliases,
        )
        if command is not None:
            return self._execute_command(command)

        if current_mode is not AssistantMode.DICTATING:
            return UtteranceResult(handled=False, success=True, message="")

        return self._execute_dictation(text)

    def _execute_command(self, command: ParsedCommand) -> UtteranceResult:
        cmd_type = command.command_type
        target = command.target

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
            return UtteranceResult(handled=True, success=ok, message=msg)

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
        entry = self._registry.get(alias)
        if entry is None:
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Tuntematon ikkuna: {alias}",
            )
        if not self._windows.is_window_valid(entry.window.hwnd):
            self._registry.remove(alias)
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Ikkuna {entry.alias} on suljettu.",
            )
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

        entry = self._registry.get(alias)
        if entry is None:
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Tuntematon ikkuna: {alias}",
            )
        if not self._windows.is_window_valid(entry.window.hwnd):
            self._registry.remove(alias)
            return UtteranceResult(
                handled=True,
                success=False,
                message=f"Ikkuna {entry.alias} on suljettu.",
            )
        ok = self._windows.minimize_window(entry.window.hwnd)
        return UtteranceResult(
            handled=True,
            success=ok,
            message=f"Piilotettu {entry.alias}" if ok else f"Ikkunan {entry.alias} piilotus epäonnistui.",
        )

    def _execute_dictation(self, text: str) -> UtteranceResult:
        actions = transform_dictation(text, self._config.keywords)
        if not actions:
            return UtteranceResult(handled=False, success=True, message="")
        ok = self._keyboard.send_actions(actions)
        if not ok:
            return UtteranceResult(
                handled=True,
                success=False,
                message="Näppäinsyöttö epäonnistui.",
            )
        return UtteranceResult(
            handled=True,
            success=True,
            message="Sanelu syötetty",
        )
