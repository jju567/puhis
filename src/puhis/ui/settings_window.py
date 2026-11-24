"""Puhiksen pääasetusikkuna: herätesana, omat avainsanat, sallitut sovellukset ja tapahtumaloki."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from puhis import __version__
from puhis.core.config_store import AppConfig
from puhis.core.config_validator import (
    validate_app_alias_rows,
    validate_keywords_rows,
    validate_wake_word,
)
from puhis.core.event_log import EventLog, LogEvent
from puhis.core.window_registry import WindowRegistry
from puhis.ui.tabs.apps_tab import AppsTab
from puhis.ui.tabs.commands_tab import CommandsTab
from puhis.ui.tabs.general_tab import GeneralTab
from puhis.ui.tabs.keywords_tab import KeywordsTab
from puhis.ui.tabs.windows_log_tab import WindowsLogTab


class SettingsWindow(QWidget):
    """Graafinen konfiguraattori Puhiksen asetuksille ja reaaliaikaiselle lokille."""

    config_saved = Signal(AppConfig)
    focus_window_requested = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        window_registry: WindowRegistry,
        event_log: EventLog,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Puhis v{__version__} – Asetukset ja hallinta")
        self.resize(840, 560)
        self._config = AppConfig.from_dict(config.to_dict())

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        body = QHBoxLayout()
        body.setSpacing(14)

        self.nav_list = QListWidget(self)
        self.nav_list.setFixedWidth(210)
        self.nav_list.addItems([
            "⚙️  Yleiset & Tunnistin",
            "🗣️  Puhekomennot",
            "⌨️  Omat avainsanat & näppäimet",
            "🚀  Sallitut sovellukset",
            "🪟  Ikkunat & Tapahtumaloki",
        ])

        self.stack = QStackedWidget(self)
        self.general_tab = GeneralTab(self)
        self.commands_tab = CommandsTab(self)
        self.keywords_tab = KeywordsTab(self)
        self.apps_tab = AppsTab(self)
        self.windows_log_tab = WindowsLogTab(window_registry, event_log, self)
        self.windows_log_tab.focus_window_requested.connect(self.focus_window_requested.emit)

        self.stack.addWidget(self.general_tab)
        self.stack.addWidget(self.commands_tab)
        self.stack.addWidget(self.keywords_tab)
        self.stack.addWidget(self.apps_tab)
        self.stack.addWidget(self.windows_log_tab)

        self.nav_list.currentRowChanged.connect(self._on_tab_changed)
        self.nav_list.setCurrentRow(0)

        body.addWidget(self.nav_list)
        body.addWidget(self.stack, stretch=1)
        root.addLayout(body, stretch=1)

        footer = QHBoxLayout()
        self.status_label = QLabel("", self)
        self.save_btn = QPushButton("Tallenna ja ota käyttöön", self)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save_clicked)

        self.close_btn = QPushButton("Sulje", self)
        self.close_btn.clicked.connect(self.close)

        footer.addWidget(self.status_label, stretch=1)
        footer.addWidget(self.save_btn)
        footer.addWidget(self.close_btn)
        root.addLayout(footer)

        self.load_config(config)

    def load_config(self, config: AppConfig) -> None:
        """Lataa asetukset kaikkiin välilehtiin."""
        self._config = AppConfig.from_dict(config.to_dict())
        self.general_tab.load_from_config(self._config)
        self.commands_tab.set_wake_word(self._config.wake_word)
        self.keywords_tab.load_keywords(self._config.keywords)
        self.apps_tab.load_app_aliases(self._config.app_aliases)
        self.windows_log_tab.refresh_windows()
        self.status_label.setText("")

    def notify_event_logged(self, event: LogEvent) -> None:
        """Päivittää tapahtumaloki- ja ikkunataulukon uuden tapahtuman jälkeen."""
        self.windows_log_tab.append_event_row(event)
        self.windows_log_tab.refresh_windows()

    def _on_tab_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if self.stack.currentWidget() is self.windows_log_tab:
            self.windows_log_tab.refresh_windows()

    def _on_save_clicked(self) -> None:
        updated = AppConfig.from_dict(self._config.to_dict())
        self.general_tab.apply_to_config(updated)

        errors: list[str] = []
        wake_err = validate_wake_word(updated.wake_word)
        if wake_err is not None:
            errors.append(wake_err)

        keywords, kw_errors = validate_keywords_rows(self.keywords_tab.collect_rows())
        errors.extend(kw_errors)

        app_aliases, app_errors = validate_app_alias_rows(self.apps_tab.collect_rows())
        errors.extend(app_errors)

        if errors:
            QMessageBox.warning(
                self,
                "Tarkista asetukset",
                "Asetuksia ei voitu tallentaa:\n\n• " + "\n• ".join(errors),
            )
            return

        updated.keywords = keywords
        updated.app_aliases = app_aliases
        self._config = updated
        self.commands_tab.set_wake_word(updated.wake_word)
        self.status_label.setText("✓ Asetukset tallennettu ja otettu käyttöön.")
        self.config_saved.emit(updated)
