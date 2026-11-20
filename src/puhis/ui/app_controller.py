"""Sovelluksen kokoava ohjain: asetukset, kissa, valikko, Tray, STT ja komentoreititys."""

import logging

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from puhis.core.actions import UtteranceResult
from puhis.core.app_state import AssistantMode, toggle_dictation, toggle_mute
from puhis.core.config_store import AppConfig, CatTheme, ConfigStore
from puhis.core.utterance_router import UtteranceRouter
from puhis.core.window_registry import WindowRegistry
from puhis.platform.app_launcher import AppLauncher
from puhis.platform.keyboard_injector import KeyboardInjector
from puhis.platform.window_manager import WindowManager
from puhis.stt.audio_capture import AudioListener
from puhis.stt.transcriber import FasterWhisperTranscriber, build_initial_prompt
from puhis.ui.app_menu import AppMenu
from puhis.ui.cat_widget import CatWidget
from puhis.ui.tray_icon import PuhisTrayIcon

logger = logging.getLogger(__name__)

SCREEN_MARGIN = 24
FEEDBACK_FLASH_MS = 1000


class AppController(QObject):
    """Kytkee käyttöliittymän, taustakuuntelun ja komentoreitittimen toisiinsa."""

    utterance_received = Signal(str)
    listener_error = Signal(str)

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

        self._window_registry = WindowRegistry()
        self._router = router or UtteranceRouter(
            config=self._config,
            window_registry=self._window_registry,
            keyboard_injector=KeyboardInjector(),
            window_manager=WindowManager(),
            app_launcher=AppLauncher(self._config.app_aliases),
        )

        self._listener: AudioListener | None = None
        if listener is not None:
            self._listener = listener
        elif enable_audio:
            transcriber = FasterWhisperTranscriber(
                initial_prompt=build_initial_prompt(self._config),
            )
            self._listener = AudioListener(
                transcriber=transcriber,
                on_utterance=self.utterance_received.emit,
                on_error=self.listener_error.emit,
            )

        self._cat = CatWidget(self._config.cat_size, theme=self._config.cat_theme)
        self._menu = AppMenu()
        self._tray = PuhisTrayIcon(self._menu, self, theme=self._config.cat_theme)

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
        if self._listener is not None:
            self._listener.start()
        logger.info("puhis käynnistetty tilassa %s", self._mode.value)

    def handle_utterance(self, text: str) -> UtteranceResult:
        """Käsittelee tunnistetun puhejakson pääsäikeessä."""
        effective_mode = self._flash_restore_mode if self._flash_restore_mode is not None else self._mode
        result = self._router.handle_utterance(text, effective_mode)
        if not result.handled:
            return result

        if result.message:
            self._cat.setToolTip(f"Puhis – {result.message}")

        if result.new_mode is not None:
            self._flash_timer.stop()
            self._flash_restore_mode = None
            self._apply_mode(result.new_mode)
        elif not result.success:
            self._flash_temporary_mode(AssistantMode.ERROR, effective_mode)
        elif effective_mode is not AssistantMode.DICTATING:
            self._flash_temporary_mode(AssistantMode.COMMAND, effective_mode)

        return result

    # --- Kytkennät -----------------------------------------------------

    def _connect_signals(self) -> None:
        self._cat.clicked.connect(self._on_toggle_dictation)
        self._cat.context_menu_requested.connect(self._show_menu)
        self._cat.position_committed.connect(self._on_position_committed)

        self._menu.dictation_action.triggered.connect(self._on_toggle_dictation)
        self._menu.mute_action.triggered.connect(self._on_toggle_mute)
        self._menu.theme_selected.connect(self._on_theme_selected)
        self._menu.visibility_action.triggered.connect(self._on_toggle_visibility)
        self._menu.quit_action.triggered.connect(self.quit)

        self._tray.activated.connect(self._on_tray_activated)
        self._app.aboutToQuit.connect(self._on_about_to_quit)

        self.utterance_received.connect(self._on_utterance_signal)
        self.listener_error.connect(self._on_listener_error)

    # --- Toiminnot -----------------------------------------------------

    def _on_utterance_signal(self, text: str) -> None:
        self.handle_utterance(text)

    def _on_listener_error(self, message: str) -> None:
        logger.error("Taustakuuntelun virhe: %s", message)
        self._flash_timer.stop()
        self._flash_restore_mode = None
        self._cat.setToolTip(f"Puhis – {message}")
        self._apply_mode(AssistantMode.ERROR)

    def _on_toggle_dictation(self) -> None:
        self._flash_timer.stop()
        base_mode = self._flash_restore_mode if self._flash_restore_mode is not None else self._mode
        self._flash_restore_mode = None
        if base_mode is AssistantMode.ERROR:
            self._apply_mode(AssistantMode.IDLE)
            return
        self._apply_mode(toggle_dictation(base_mode))

    def _on_toggle_mute(self) -> None:
        self._flash_timer.stop()
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

    def _on_toggle_visibility(self) -> None:
        self._cat.setVisible(not self._cat.isVisible())
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

    def quit(self) -> None:
        """Sulkee taustakuuntelun ja sovelluksen hallitusti."""
        logger.info("puhis suljetaan")
        self._flash_timer.stop()
        if self._listener is not None:
            self._listener.stop()
        self._tray.hide()
        self._cat.close()
        self._app.quit()

    # --- Sisäiset ------------------------------------------------------

    def _flash_temporary_mode(self, temp_mode: AssistantMode, restore_mode: AssistantMode) -> None:
        self._flash_restore_mode = restore_mode
        self._cat.set_mode(temp_mode)
        self._tray.set_mode(temp_mode)
        self._flash_timer.start(FEEDBACK_FLASH_MS)

    def _restore_after_flash(self) -> None:
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
        self._menu.update_state(self._mode, self._cat.isVisible(), self._config.cat_theme)

    def _on_about_to_quit(self) -> None:
        if self._listener is not None:
            self._listener.stop()
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
