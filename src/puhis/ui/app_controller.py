"""Sovelluksen kokoava ohjain: asetukset, kissa, puhekupla, valikko, Tray ja STT."""

from collections.abc import Sequence
import logging
import webbrowser

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from puhis.core.actions import UtteranceResult
from puhis.core.app_state import AssistantMode, toggle_dictation, toggle_mute
from puhis.core.config_store import AppConfig, CatTheme, ConfigStore, SttEngine
from puhis.core.event_log import EventLog
from puhis.core.utterance_router import UtteranceRouter
from puhis.core.window_registry import WindowRegistry
from puhis.platform.app_launcher import AppLauncher
from puhis.platform.keyboard_injector import KeyboardInjector
from puhis.platform.openrouter_client import OpenRouterIntentClient
from puhis.platform.paths import get_windows_path
from puhis.platform.window_manager import WindowManager
from puhis.stt.audio_capture import AudioListener
from puhis.stt.browser_bridge import (
    BRIDGE_WINDOW_TITLE,
    DEFAULT_BRIDGE_PORT,
    BrowserSpeechBridge,
    launch_chrome_app,
)
from puhis.stt.transcriber import SwitchableTranscriber, build_initial_prompt
from puhis.ui.app_menu import AppMenu, ENGINE_LABELS_FI
from puhis.ui.cat_widget import CatWidget
from puhis.ui.settings_window import SettingsWindow
from puhis.ui.speech_bubble import BubbleTone, SpeechBubble
from puhis.ui.tray_icon import PuhisTrayIcon

logger = logging.getLogger(__name__)

SCREEN_MARGIN = 24
FEEDBACK_FLASH_MS = 2500
WAKE_WINDOW_MS = 12_000
BUBBLE_DEFAULT_MS = 3800


class AppController(QObject):
    """Kytkee käyttöliittymän, taustakuuntelun ja komentoreitittimen toisiinsa."""

    utterance_received = Signal(str)
    candidates_received = Signal(list)
    bridge_status_received = Signal(str)
    listener_error = Signal(str)
    processing_changed = Signal(bool)
    listener_ready = Signal()

    def __init__(
        self,
        app: QApplication,
        store: ConfigStore,
        router: UtteranceRouter | None = None,
        listener: AudioListener | None = None,
        enable_audio: bool = True,
    ) -> None:
        super().__init__()
        self._app = app
        self._store = store
        self._config: AppConfig = store.load()
        self._mode = self._config.start_mode

        self._window_registry = WindowRegistry(storage_path=get_windows_path())
        self._event_log = EventLog()
        self._app_launcher = AppLauncher(self._config.app_aliases)
        self._window_manager = WindowManager()
        self._intent_client = OpenRouterIntentClient(
            api_key=self._config.openrouter_api_key,
            primary_model=self._config.openrouter_model,
            fallback_models=self._config.openrouter_fallback_models,
        )
        self._router = router or UtteranceRouter(
            config=self._config,
            window_registry=self._window_registry,
            keyboard_injector=KeyboardInjector(),
            window_manager=self._window_manager,
            app_launcher=self._app_launcher,
            intent_interpreter=self._intent_client,
        )

        self._transcriber: SwitchableTranscriber | None = None
        self._listener: AudioListener | None = None
        if listener is not None:
            self._listener = listener
        elif enable_audio:
            self._transcriber = SwitchableTranscriber(
                initial_engine=self._config.stt_engine,
                initial_prompt=build_initial_prompt(self._config),
            )
            self._listener = AudioListener(
                transcriber=self._transcriber,
                on_utterance=self.utterance_received.emit,
                on_candidates=self.candidates_received.emit,
                on_error=self.listener_error.emit,
                on_processing=self.processing_changed.emit,
                on_ready=self.listener_ready.emit,
            )

        self._browser_bridge: BrowserSpeechBridge | None = None
        self._bridge_minimized = False
        self._bridge_minimize_attempts = 0

        self._cat = CatWidget(
            self._config.cat_size,
            theme=self._config.cat_theme,
            wake_word=self._config.wake_word,
        )
        self._bubble = SpeechBubble()
        self._menu = AppMenu()
        self._tray = PuhisTrayIcon(self._menu, self, theme=self._config.cat_theme)
        self._settings_window: SettingsWindow | None = None

        self._flash_restore_mode: AssistantMode | None = None
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._restore_after_flash)

        self._connect_signals()

    def start(self) -> None:
        """Näyttää kissan, Tray-kuvakkeen ja käynnistää taustakuuntelun."""
        self._cat.move(self._initial_position())
        self._cat.show()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()
        else:
            logger.warning("Windowsin ilmaisinalue ei ole käytettävissä")
        self._apply_mode(self._mode)
        if self._config.stt_engine is SttEngine.CHROME:
            self._cat.set_sleeping(True)
            self._cat.setToolTip("Puhis – Käynnistetään Chrome-kuuntelua…")
            self._start_chrome_bridge()
        elif self._listener is not None:
            # Kissa nukkuu, kunnes mikrofoni ja puheentunnistin ovat valmiina.
            self._cat.set_sleeping(True)
            self._cat.setToolTip("Puhis – Käynnistetään mikrofonia…")
            self._listener.start()
        logger.info("puhis käynnistetty tilassa %s", self._mode.value)

    def handle_utterance(self, text: str) -> UtteranceResult:
        """Käsittelee tunnistetun puhejakson pääsäikeessä."""
        return self.handle_candidates([text])

    def handle_candidates(self, candidates: Sequence[str]) -> UtteranceResult:
        """Valitsee parhaan tunnistusehdokkaan ja päivittää kissan sekä puhekuplan."""
        self._cat.set_processing(False)
        chosen_text, result = self._router.handle_candidates(candidates, self._mode)
        engine_tag = "🌐" if self._config.stt_engine in (SttEngine.WEB, SttEngine.CHROME) else "💻"
        heard_line = f'{engine_tag} "{chosen_text}"'

        if not result.handled:
            return result

        self._record_event(chosen_text, result.message or "OK", success=result.success)

        if result.message:
            self._cat.setToolTip(f"Puhis – {result.message}")

        base_mode = self._flash_restore_mode if self._flash_restore_mode is not None else self._mode
        if base_mode is AssistantMode.COMMAND:
            base_mode = AssistantMode.IDLE

        if result.new_mode is AssistantMode.COMMAND:
            # Pelkkä "puhis" herättää kissan kuuntelemaan jatkokomentoa.
            self._flash_temporary_mode(
                AssistantMode.COMMAND,
                base_mode,
                duration_ms=WAKE_WINDOW_MS,
                badge="KUUNTELEN!",
            )
            self._show_bubble(
                heard_line,
                "🟢 Kuuntelen! Sano komento…",
                BubbleTone.COMMAND,
                duration_ms=WAKE_WINDOW_MS,
            )
        elif result.new_mode is not None:
            self._flash_timer.stop()
            self._flash_restore_mode = None
            self._cat.set_badge_text("")
            self._apply_mode(result.new_mode)
            self._show_bubble(
                heard_line,
                f"⚡ {result.message}",
                BubbleTone.DICTATING if result.new_mode is AssistantMode.DICTATING else BubbleTone.COMMAND,
                duration_ms=BUBBLE_DEFAULT_MS,
            )
        elif not result.success:
            self._flash_temporary_mode(
                AssistantMode.ERROR,
                base_mode,
                duration_ms=FEEDBACK_FLASH_MS,
                badge=result.message,
            )
            self._show_bubble(
                heard_line,
                f"⚠️ {result.message}",
                BubbleTone.ERROR,
                duration_ms=BUBBLE_DEFAULT_MS,
            )
        else:
            was_dictating = base_mode is AssistantMode.DICTATING
            if not was_dictating:
                self._flash_temporary_mode(
                    AssistantMode.COMMAND,
                    base_mode,
                    duration_ms=FEEDBACK_FLASH_MS,
                    badge=result.message,
                )
            icon = "✍️" if was_dictating and result.message == "Sanelu syötetty" else "⚡"
            tone = BubbleTone.DICTATING if was_dictating else BubbleTone.COMMAND
            self._show_bubble(
                heard_line,
                f"{icon} {result.message}",
                tone,
                duration_ms=BUBBLE_DEFAULT_MS,
            )

        return result

    # --- Kytkennät -----------------------------------------------------

    def _connect_signals(self) -> None:
        self._cat.clicked.connect(self._on_toggle_dictation)
        self._cat.context_menu_requested.connect(self._show_menu)
        self._cat.position_committed.connect(self._on_position_committed)
        self._cat.geometry_changed.connect(self._bubble.update_anchor)

        self._menu.dictation_action.triggered.connect(self._on_toggle_dictation)
        self._menu.mute_action.triggered.connect(self._on_toggle_mute)
        self._menu.engine_selected.connect(self._on_engine_selected)
        self._menu.theme_selected.connect(self._on_theme_selected)
        self._menu.settings_action.triggered.connect(self._on_open_settings)
        self._menu.visibility_action.triggered.connect(self._on_toggle_visibility)
        self._menu.quit_action.triggered.connect(self.quit)

        self._tray.activated.connect(self._on_tray_activated)
        self._app.aboutToQuit.connect(self._on_about_to_quit)

        self.utterance_received.connect(self._on_utterance_signal)
        self.candidates_received.connect(self._on_candidates_signal)
        self.bridge_status_received.connect(self._on_bridge_status)
        self.listener_error.connect(self._on_listener_error)
        self.processing_changed.connect(self._on_processing_changed)
        self.listener_ready.connect(self._on_listener_ready)

    # --- Toiminnot -----------------------------------------------------

    def _on_utterance_signal(self, text: str) -> None:
        self.handle_utterance(text)

    def _on_candidates_signal(self, candidates: list[str]) -> None:
        self.handle_candidates(candidates)

    def _on_processing_changed(self, is_processing: bool) -> None:
        self._cat.set_processing(is_processing)
        if is_processing:
            # Jos kissa on COMMAND-kuuntelutilassa, estetään tilan vanheneminen
            # kesken puheentunnistuksen.
            if self._mode is AssistantMode.COMMAND and self._flash_timer.isActive():
                self._flash_timer.stop()
        elif self._mode is AssistantMode.COMMAND and not self._flash_timer.isActive():
            self._flash_timer.start(WAKE_WINDOW_MS // 2)

    def _on_listener_ready(self) -> None:
        self._cat.set_sleeping(False)
        self._cat.setToolTip("Puhis")
        logger.info("Puhis heräsi kuuntelemaan (tila=%s)", self._mode.value)

    def _on_listener_error(self, message: str) -> None:
        logger.error("Taustakuuntelun virhe: %s", message)
        self._flash_timer.stop()
        self._flash_restore_mode = None
        self._cat.set_sleeping(False)
        self._cat.set_processing(False)
        self._cat.setToolTip(f"Puhis – {message}")
        self._apply_mode(AssistantMode.ERROR)
        self._show_bubble("⚠️ Virhe", message, BubbleTone.ERROR, duration_ms=5000)

    def _on_toggle_dictation(self) -> None:
        self._flash_timer.stop()
        self._cat.set_badge_text("")
        base_mode = self._flash_restore_mode if self._flash_restore_mode is not None else self._mode
        self._flash_restore_mode = None
        if base_mode in (AssistantMode.ERROR, AssistantMode.COMMAND):
            self._apply_mode(AssistantMode.DICTATING)
        else:
            self._apply_mode(toggle_dictation(base_mode))

        if self._mode is AssistantMode.DICTATING:
            self._show_bubble("✍️ Sanelutila päällä", "Puhu tekstiä tai komentoja", BubbleTone.DICTATING, duration_ms=2200)
        elif self._mode is AssistantMode.IDLE:
            self._show_bubble("😺 Lepotila", f'Herätä sanomalla "{self._config.wake_word}"', BubbleTone.COMMAND, duration_ms=2000)

    def _on_toggle_mute(self) -> None:
        self._flash_timer.stop()
        self._cat.set_badge_text("")
        self._cat.set_processing(False)
        base_mode = self._flash_restore_mode if self._flash_restore_mode is not None else self._mode
        self._flash_restore_mode = None
        self._apply_mode(toggle_mute(base_mode))

    def _on_theme_selected(self, theme: CatTheme) -> None:
        if theme is self._config.cat_theme:
            return
        self._config.cat_theme = theme
        self._cat.set_theme(theme)
        self._tray.set_theme(theme)
        self._refresh_menu()
        self._save_config()

    def _on_engine_selected(self, engine: SttEngine) -> None:
        was_same = engine is self._config.stt_engine
        self._config.stt_engine = engine
        if self._transcriber is not None:
            self._transcriber.set_engine(engine)
        if engine is SttEngine.CHROME:
            self._start_chrome_bridge()
        else:
            self._stop_chrome_bridge()
            if self._listener is not None and not self._listener.is_running:
                self._listener.start()
        self._refresh_menu()
        if not was_same:
            self._save_config()
            if engine is not SttEngine.CHROME:
                label = ENGINE_LABELS_FI.get(engine, engine.value)
                self._show_bubble("Puheentunnistin vaihdettu", label, BubbleTone.COMMAND, duration_ms=3200)

    def _on_toggle_visibility(self) -> None:
        visible = not self._cat.isVisible()
        self._cat.setVisible(visible)
        if not visible:
            self._bubble.hide()
        self._refresh_menu()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason is QSystemTrayIcon.ActivationReason.Trigger:
            self._on_toggle_visibility()

    def _show_menu(self, global_pos: QPoint) -> None:
        self._refresh_menu()
        self._menu.popup(global_pos)

    def _on_position_committed(self, pos: QPoint) -> None:
        self._config.cat_x = pos.x()
        self._config.cat_y = pos.y()
        self._save_config()

    def _on_open_settings(self) -> None:
        if self._settings_window is None:
            self._settings_window = SettingsWindow(
                config=self._config,
                window_registry=self._window_registry,
                event_log=self._event_log,
            )
            self._settings_window.config_saved.connect(self._on_config_saved)
            self._settings_window.focus_window_requested.connect(self._on_focus_window_from_ui)
        else:
            self._settings_window.load_config(self._config)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _on_config_saved(self, new_config: AppConfig) -> None:
        prev_engine = self._config.stt_engine
        new_config.cat_x = self._config.cat_x
        new_config.cat_y = self._config.cat_y
        self._config = new_config
        self._intent_client.update_settings(
            api_key=self._config.openrouter_api_key,
            primary_model=self._config.openrouter_model,
            fallback_models=self._config.openrouter_fallback_models,
        )
        self._router.update_config(self._config)
        self._app_launcher.update_aliases(self._config.app_aliases)
        if self._transcriber is not None:
            self._transcriber.set_engine(self._config.stt_engine)
        if self._config.stt_engine is not prev_engine:
            if self._config.stt_engine is SttEngine.CHROME:
                self._start_chrome_bridge()
            else:
                self._stop_chrome_bridge()
                if self._listener is not None and not self._listener.is_running:
                    self._listener.start()
        self._cat.set_theme(self._config.cat_theme)
        self._cat.set_cat_size(self._config.cat_size)
        self._cat.set_wake_word(self._config.wake_word)
        self._tray.set_theme(self._config.cat_theme)
        self._refresh_menu()
        self._save_config()
        self._show_bubble(
            "⚙️ Asetukset tallennettu",
            "Muutokset ovat heti voimassa",
            BubbleTone.COMMAND,
            duration_ms=2800,
        )

    def _on_focus_window_from_ui(self, alias: str) -> None:
        self.handle_utterance(f"{self._config.wake_word} fokus {alias}")

    def _start_chrome_bridge(self) -> None:
        if self._browser_bridge is None:
            self._browser_bridge = BrowserSpeechBridge(
                on_candidates=self.candidates_received.emit,
                on_status=self.bridge_status_received.emit,
                port=DEFAULT_BRIDGE_PORT,
            )
        self._bridge_minimized = False
        url = self._browser_bridge.start()
        # Vapautetaan sisäinen mikrofonivirta kokonaan, jotta Chrome saa yksin
        # käyttää mikrofonia ilman WASAPI/Web Speech -konfliktia.
        if self._listener is not None and self._listener.is_running:
            self._listener.stop()
        self._window_manager.close_matching_window("Chrome-puhekuuntelu")
        launch_chrome_app(url)
        self._show_bubble(
            "🌐 Chrome-kuuntelu käynnistyy",
            "Kuuntelu alkaa automaattisesti…",
            BubbleTone.COMMAND,
            duration_ms=3200,
        )

    def _stop_chrome_bridge(self) -> None:
        self._window_manager.close_matching_window("Chrome-puhekuuntelu")
        if self._browser_bridge is not None:
            self._browser_bridge.stop()

    def _on_bridge_status(self, state: str) -> None:
        logger.info("Chrome-kuuntelun tila: %s", state)
        if state == "listening":
            self._cat.set_sleeping(False)
            self._cat.setToolTip("Puhis")
            if not self._bridge_minimized:
                self._bridge_minimize_attempts = 0
                self._try_minimize_bridge_window()
                self._show_bubble(
                    "🌐 Chrome-kuuntelu päällä",
                    "Taustakuuntelu aktiivinen",
                    BubbleTone.COMMAND,
                    duration_ms=2600,
                )
        elif state.startswith("error:"):
            err = state.split(":", 1)[1]
            if err not in ("no-speech", "aborted"):
                self._show_bubble(
                    "🌐 Chrome-kuuntelu",
                    f"Salli mikrofoni selaimessa ({err})",
                    BubbleTone.ERROR,
                    duration_ms=4200,
                )

    def _try_minimize_bridge_window(self) -> None:
        if self._bridge_minimized:
            return
        if self._window_manager.minimize_matching_window("Chrome-puhekuuntelu"):
            self._bridge_minimized = True
            return
        self._bridge_minimize_attempts += 1
        if self._bridge_minimize_attempts < 6:
            QTimer.singleShot(500, self._try_minimize_bridge_window)

    def quit(self) -> None:
        """Sulkee taustakuuntelun ja sovelluksen hallitusti."""
        logger.info("puhis suljetaan")
        self._flash_timer.stop()
        if self._listener is not None:
            self._listener.stop()
        if self._browser_bridge is not None:
            self._window_manager.close_matching_window("Chrome-puhekuuntelu")
            self._browser_bridge.stop()
        if self._settings_window is not None:
            self._settings_window.close()
        self._tray.hide()
        self._bubble.close()
        self._cat.close()
        self._app.quit()

    # --- Sisäiset ------------------------------------------------------

    def _record_event(self, heard_text: str, action_message: str, *, success: bool) -> None:
        event = self._event_log.append(heard_text, action_message, success=success)
        if self._settings_window is not None:
            self._settings_window.notify_event_logged(event)

    def _show_bubble(
        self,
        heard_line: str,
        action_line: str,
        tone: BubbleTone,
        *,
        duration_ms: int = BUBBLE_DEFAULT_MS,
    ) -> None:
        if not self._cat.isVisible():
            return
        self._bubble.show_message(
            heard_line,
            action_line,
            tone,
            self._cat.geometry(),
            duration_ms=duration_ms,
        )

    def _flash_temporary_mode(
        self,
        temp_mode: AssistantMode,
        restore_mode: AssistantMode,
        *,
        duration_ms: int = FEEDBACK_FLASH_MS,
        badge: str = "",
    ) -> None:
        self._flash_restore_mode = restore_mode
        self._mode = temp_mode
        self._cat.set_badge_text(badge)
        self._cat.set_mode(temp_mode)
        self._tray.set_mode(temp_mode)
        self._refresh_menu()
        self._flash_timer.start(duration_ms)

    def _restore_after_flash(self) -> None:
        self._cat.set_badge_text("")
        if self._flash_restore_mode is not None:
            restore = self._flash_restore_mode
            self._flash_restore_mode = None
            self._apply_mode(restore)

    def _apply_mode(self, mode: AssistantMode) -> None:
        if mode is not self._mode:
            logger.info("Tila vaihtui: %s -> %s", self._mode.value, mode.value)
        self._mode = mode
        if self._listener is not None:
            self._listener.set_muted(mode is AssistantMode.MUTED)
        self._cat.set_mode(mode)
        self._tray.set_mode(mode)
        self._refresh_menu()

    def _refresh_menu(self) -> None:
        self._menu.update_state(
            self._mode,
            self._cat.isVisible(),
            self._config.cat_theme,
            self._config.stt_engine,
        )

    def _on_about_to_quit(self) -> None:
        if self._listener is not None:
            self._listener.stop()
        if self._browser_bridge is not None:
            self._window_manager.close_matching_window("Chrome-puhekuuntelu")
            self._browser_bridge.stop()
        self._persist_position()

    def _persist_position(self) -> None:
        pos = self._cat.pos()
        if (pos.x(), pos.y()) == (self._config.cat_x, self._config.cat_y):
            return
        self._on_position_committed(pos)

    def _save_config(self) -> None:
        try:
            self._store.save(self._config)
        except OSError:
            logger.exception("Asetusten tallennus epäonnistui: %s", self._store.path)
            self._tray.showMessage(
                "Puhis",
                "Asetusten tallennus epäonnistui. Lisätiedot lokitiedostossa.",
                QSystemTrayIcon.MessageIcon.Warning,
            )

    def _initial_position(self) -> QPoint:
        """Palauttaa tallennetun sijainnin, jos se on näkyvissä, muuten oletuspaikan."""
        size = self._cat.size()
        if self._config.cat_x is not None and self._config.cat_y is not None:
            saved = QRect(QPoint(self._config.cat_x, self._config.cat_y), size)
            # Kissa ei saa jäädä irrotetun näytön alueelle näkymättömiin.
            if any(s.availableGeometry().contains(saved.center()) for s in QGuiApplication.screens()):
                return saved.topLeft()
            logger.info("Tallennettu sijainti ei ole näkyvissä, käytetään oletuspaikkaa")

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QPoint(SCREEN_MARGIN, SCREEN_MARGIN)
        area = screen.availableGeometry()
        return QPoint(
            area.right() - size.width() - SCREEN_MARGIN,
            area.bottom() - size.height() - SCREEN_MARGIN,
        )
