"""Sovelluksen kokoava ohjain: asetukset, kissa, valikko ja Tray-kuvake."""

import logging

from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from puhis.core.app_state import AssistantMode, toggle_dictation, toggle_mute
from puhis.core.config_store import AppConfig, CatTheme, ConfigStore
from puhis.ui.app_menu import AppMenu
from puhis.ui.cat_widget import CatWidget
from puhis.ui.tray_icon import PuhisTrayIcon

logger = logging.getLogger(__name__)

SCREEN_MARGIN = 24


class AppController(QObject):
    """Kytkee käyttöliittymän osat toisiinsa ja ydinlogiikkaan."""

    def __init__(self, app: QApplication, store: ConfigStore) -> None:
        super().__init__()
        self._app = app
        self._store = store
        self._config: AppConfig = store.load()
        self._mode = self._config.start_mode

        self._cat = CatWidget(self._config.cat_size, theme=self._config.cat_theme)
        self._menu = AppMenu()
        self._tray = PuhisTrayIcon(self._menu, self, theme=self._config.cat_theme)
        self._connect_signals()

    def start(self) -> None:
        """Näyttää kissan ja Tray-kuvakkeen."""
        self._cat.move(self._initial_position())
        self._cat.show()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()
        else:
            logger.warning("Windowsin ilmaisinalue ei ole käytettävissä")
        self._apply_mode(self._mode)
        logger.info("puhis käynnistetty tilassa %s", self._mode.value)

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
        self._app.aboutToQuit.connect(self._persist_position)

    # --- Toiminnot -----------------------------------------------------

    def _on_toggle_dictation(self) -> None:
        self._apply_mode(toggle_dictation(self._mode))

    def _on_toggle_mute(self) -> None:
        self._apply_mode(toggle_mute(self._mode))

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
        """Sulkee sovelluksen hallitusti."""
        logger.info("puhis suljetaan")
        self._tray.hide()
        self._cat.close()
        self._app.quit()

    # --- Sisäiset ------------------------------------------------------

    def _apply_mode(self, mode: AssistantMode) -> None:
        if mode is not self._mode:
            logger.info("Tila vaihtui: %s -> %s", self._mode.value, mode.value)
        self._mode = mode
        self._cat.set_mode(mode)
        self._tray.set_mode(mode)
        self._refresh_menu()

    def _refresh_menu(self) -> None:
        self._menu.update_state(self._mode, self._cat.isVisible(), self._config.cat_theme)

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
