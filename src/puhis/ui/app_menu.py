"""Yhteinen pikavalikko kissalle ja ilmaisinalueen kuvakkeelle."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import CatTheme, SttEngine

MODE_LABELS_FI: dict[AssistantMode, str] = {
    AssistantMode.IDLE: "Lepotila – odottaa herätesanaa",
    AssistantMode.DICTATING: "Sanelu päällä",
    AssistantMode.COMMAND: "Kuuntelee komentoa…",
    AssistantMode.MUTED: "Mikrofoni mykistetty",
    AssistantMode.ERROR: "Virhe – katso loki",
}

THEME_LABELS_FI: dict[CatTheme, str] = {
    CatTheme.CHARCOAL: "Hiili",
    CatTheme.ORANGE: "Oranssi",
    CatTheme.CREAM: "Kerma",
}

ENGINE_LABELS_FI: dict[SttEngine, str] = {
    SttEngine.WEB: "🌐 Selaintunnistus (Google fi-FI – nopea)",
    SttEngine.WHISPER: "💻 Paikallinen Whisper (offline CPU)",
}


class AppMenu(QMenu):
    """Sama valikko-olio jaetaan kissan oikean klikin ja Tray-kuvakkeen kesken,
    jotta toiminnot ja niiden tila pysyvät aina synkronissa."""

    theme_selected = Signal(CatTheme)
    engine_selected = Signal(SttEngine)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.status_action = QAction(self)
        self.status_action.setEnabled(False)

        self.dictation_action = QAction("Sanelu", self)
        self.dictation_action.setCheckable(True)

        self.mute_action = QAction("Mykistä mikrofoni", self)
        self.mute_action.setCheckable(True)

        self.engine_menu = QMenu("Puheentunnistin", self)
        self._engine_group = QActionGroup(self)
        self._engine_group.setExclusive(True)
        self._engine_actions: dict[SttEngine, QAction] = {}
        for engine, label in ENGINE_LABELS_FI.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, e=engine: checked and self.engine_selected.emit(e))
            self._engine_group.addAction(action)
            self.engine_menu.addAction(action)
            self._engine_actions[engine] = action

        self.theme_menu = QMenu("Kissan väri", self)
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions: dict[CatTheme, QAction] = {}
        for theme, label in THEME_LABELS_FI.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, t=theme: checked and self.theme_selected.emit(t))
            self._theme_group.addAction(action)
            self.theme_menu.addAction(action)
            self._theme_actions[theme] = action

        self.settings_action = QAction("Asetukset ja hallinta…", self)

        self.visibility_action = QAction(self)
        self.quit_action = QAction("Sulje Puhis", self)

        self.addAction(self.status_action)
        self.addSeparator()
        self.addAction(self.dictation_action)
        self.addAction(self.mute_action)
        self.addMenu(self.engine_menu)
        self.addMenu(self.theme_menu)
        self.addSeparator()
        self.addAction(self.settings_action)
        self.addAction(self.visibility_action)
        self.addSeparator()
        self.addAction(self.quit_action)

        self.update_state(AssistantMode.IDLE, cat_visible=True)

    def update_state(
        self,
        mode: AssistantMode,
        cat_visible: bool,
        theme: CatTheme = CatTheme.CHARCOAL,
        engine: SttEngine = SttEngine.WEB,
    ) -> None:
        """Päivittää valikon tekstit ja valintatilat."""
        self.status_action.setText(MODE_LABELS_FI.get(mode, str(mode)))
        self.dictation_action.setChecked(mode is AssistantMode.DICTATING)
        self.dictation_action.setEnabled(mode in (AssistantMode.IDLE, AssistantMode.DICTATING))
        self.mute_action.setChecked(mode is AssistantMode.MUTED)
        if theme in self._theme_actions:
            self._theme_actions[theme].setChecked(True)
        if engine in self._engine_actions:
            self._engine_actions[engine].setChecked(True)
        self.visibility_action.setText("Piilota kissa" if cat_visible else "Näytä kissa")
