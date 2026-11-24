"""Yleiset asetukset: herätesana, puheentunnistin ja kissan ulkoasu."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import (
    DEFAULT_CAT_SIZE,
    DEFAULT_OPENROUTER_MODELS,
    MAX_CAT_SIZE,
    MIN_CAT_SIZE,
    AppConfig,
    CatTheme,
    SttEngine,
)
from puhis.ui.app_menu import ENGINE_LABELS_FI, THEME_LABELS_FI
from puhis.ui.cat_painter import CatGeometry, paint_cat

_START_MODE_LABELS: list[tuple[AssistantMode, str]] = [
    (AssistantMode.IDLE, "Lepotila (odottaa herätesanaa)"),
    (AssistantMode.DICTATING, "Sanelutila heti päällä"),
    (AssistantMode.MUTED, "Mikrofoni mykistettynä"),
]


class _CatPreviewWidget(QWidget):
    """Pieni esikatselu-widget kissan väriteemalle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(88, 88)
        self._theme = CatTheme.CHARCOAL

    def set_theme(self, theme: CatTheme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            paint_cat(
                painter,
                CatGeometry(float(self.width())),
                AssistantMode.DICTATING,
                (1.5, -1.0),
                (1.5, -1.0),
                theme=self._theme,
            )
        finally:
            painter.end()


class GeneralTab(QWidget):
    """Välilehti herätesanalle, tunnistusmoottorille ja kissan ulkoasulle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(14)

        voice_group = QGroupBox("Puheohjaus ja tunnistin", self)
        voice_form = QFormLayout(voice_group)
        voice_form.setSpacing(10)

        self.wake_word_edit = QLineEdit(self)
        self.wake_word_edit.setPlaceholderText("esim. puhis")
        self.wake_word_edit.setToolTip(
            "Sana, jolla komennot aloitetaan (esim. 'puhis avaa muistio')."
        )
        voice_form.addRow("Herätesana:", self.wake_word_edit)

        self.engine_combo = QComboBox(self)
        for engine, label in ENGINE_LABELS_FI.items():
            self.engine_combo.addItem(label, engine)
        voice_form.addRow("Puheentunnistin:", self.engine_combo)

        self.start_mode_combo = QComboBox(self)
        for mode, label in _START_MODE_LABELS:
            self.start_mode_combo.addItem(label, mode)
        voice_form.addRow("Aloitustila käynnistyessä:", self.start_mode_combo)

        root.addWidget(voice_group)

        cat_group = QGroupBox("Kissa-avustimen ulkoasu", self)
        cat_layout = QHBoxLayout(cat_group)
        cat_form = QFormLayout()
        cat_form.setSpacing(10)

        self.theme_combo = QComboBox(self)
        for theme, label in THEME_LABELS_FI.items():
            self.theme_combo.addItem(label, theme)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        cat_form.addRow("Turkin väriteema:", self.theme_combo)

        self.size_spin = QSpinBox(self)
        self.size_spin.setRange(MIN_CAT_SIZE, MAX_CAT_SIZE)
        self.size_spin.setSingleStep(8)
        self.size_spin.setSuffix(" px")
        cat_form.addRow("Kissan koko:", self.size_spin)

        cat_layout.addLayout(cat_form, stretch=1)
        self._preview = _CatPreviewWidget(self)
        cat_layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        root.addWidget(cat_group)

        llm_group = QGroupBox("Älykäs komentotulkinta (OpenRouter)", self)
        llm_form = QFormLayout(llm_group)
        llm_form.setSpacing(10)

        self.llm_enabled_check = QCheckBox(
            "Käytä OpenRouter-tulkitsijaa epäselville komennoille",
            self,
        )
        llm_form.addRow(self.llm_enabled_check)

        self.openrouter_key_edit = QLineEdit(self)
        self.openrouter_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key_edit.setPlaceholderText("sk-or-v1-... (tai OPENROUTER_API_KEY)")
        llm_form.addRow("OpenRouter API -avain:", self.openrouter_key_edit)

        self.openrouter_model_combo = QComboBox(self)
        self.openrouter_model_combo.setEditable(True)
        for model_name in DEFAULT_OPENROUTER_MODELS:
            self.openrouter_model_combo.addItem(model_name)
        llm_form.addRow("Ensisijainen malli:", self.openrouter_model_combo)

        root.addWidget(llm_group)

        hint = QLabel(
            "Vinkki: Kun sanot 'puhis avaa <sovellus>', sovellus käynnistyy ja "
            "sanelutila kytkeytyy automaattisesti päälle, jotta voit heti puhua ohjelmaan.",
            self,
        )
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

    def load_from_config(self, config: AppConfig) -> None:
        """Täyttää kentät annetusta asetustietomallista."""
        self.wake_word_edit.setText(config.wake_word)
        self._select_combo_data(self.engine_combo, config.stt_engine)
        self._select_combo_data(self.start_mode_combo, config.start_mode)
        self._select_combo_data(self.theme_combo, config.cat_theme)
        self.size_spin.setValue(config.cat_size)
        self._preview.set_theme(config.cat_theme)
        self.llm_enabled_check.setChecked(config.llm_enabled)
        self.openrouter_key_edit.setText(config.openrouter_api_key)
        self.openrouter_model_combo.setCurrentText(config.openrouter_model)

    def apply_to_config(self, config: AppConfig) -> None:
        """Kirjoittaa kenttien arvot `AppConfig`-olioon."""
        config.wake_word = self.wake_word_edit.text().strip().lower()
        engine = self.engine_combo.currentData()
        if isinstance(engine, SttEngine):
            config.stt_engine = engine
        start_mode = self.start_mode_combo.currentData()
        if isinstance(start_mode, AssistantMode):
            config.start_mode = start_mode
        theme = self.theme_combo.currentData()
        if isinstance(theme, CatTheme):
            config.cat_theme = theme
        config.cat_size = int(self.size_spin.value() or DEFAULT_CAT_SIZE)
        config.llm_enabled = self.llm_enabled_check.isChecked()
        config.openrouter_api_key = self.openrouter_key_edit.text().strip()
        model_text = self.openrouter_model_combo.currentText().strip()
        if model_text:
            config.openrouter_model = model_text

    def _on_theme_changed(self) -> None:
        theme = self.theme_combo.currentData()
        if isinstance(theme, CatTheme):
            self._preview.set_theme(theme)

    @staticmethod
    def _select_combo_data(combo: QComboBox, target: object) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == target:
                combo.setCurrentIndex(idx)
                return
