"""Omat avainsanat, välimerkit ja erikoisnäppäimet -välilehti."""

from collections.abc import Mapping

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from puhis.core.config_store import DEFAULT_KEYWORDS

_PRESET_KEY_TOKENS: list[tuple[str, str]] = [
    ("{ENTER}", "{ENTER} – Enter / rivinvaihto"),
    ("{TAB}", "{TAB} – Sarkain (Tab)"),
    ("{BACKSPACE}", "{BACKSPACE} – Pyyhi (Backspace)"),
    ("{SPACE}", "{SPACE} – Välilyönti"),
    ("{ESCAPE}", "{ESCAPE} – Esc"),
    ("{DELETE}", "{DELETE} – Delete"),
    ("{LEFT}", "{LEFT} – Nuoli vasemmalle"),
    ("{RIGHT}", "{RIGHT} – Nuoli oikealle"),
    ("{UP}", "{UP} – Nuoli ylös"),
    ("{DOWN}", "{DOWN} – Nuoli alas"),
]


class KeywordsTab(QWidget):
    """Välilehti puheavainsanojen, välimerkkien ja erikoisnäppäinten muokkaukseen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        info = QLabel(
            "Määrittele sanat, jotka sanelutilassa muunnetaan merkeiksi, omaksi tekstiksi "
            "tai erikoisnäppäimiksi (esim. 'piste' → '.', 'sähköposti' → 'oma@osoite.fi', 'enter' → '{ENTER}').",
            self,
        )
        info.setWordWrap(True)
        root.addWidget(info)

        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Suodata avainsanoja…")
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(QLabel("Haku:", self))
        filter_row.addWidget(self.filter_edit, stretch=1)
        root.addLayout(filter_row)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([
            "Puhesana (mitä sanot)",
            "Korvaava teksti tai näppäin ({ENTER}, {TAB}…)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        root.addWidget(self.table, stretch=1)

        add_row = QHBoxLayout()
        self.new_phrase_edit = QLineEdit(self)
        self.new_phrase_edit.setPlaceholderText("Uusi puhesana (esim. sähköposti)")
        self.new_output_combo = QComboBox(self)
        self.new_output_combo.setEditable(True)
        if self.new_output_combo.lineEdit() is not None:
            self.new_output_combo.lineEdit().setPlaceholderText(
                "Kirjoita teksti/merkki tai valitse {NÄPPÄIN}"
            )
        self.new_output_combo.addItem("")
        for token, desc in _PRESET_KEY_TOKENS:
            self.new_output_combo.addItem(desc, token)
        self.new_output_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.add_btn = QPushButton("+ Lisää / päivitä", self)
        self.add_btn.clicked.connect(self._on_add_clicked)

        add_row.addWidget(self.new_phrase_edit, stretch=1)
        add_row.addWidget(self.new_output_combo, stretch=1)
        add_row.addWidget(self.add_btn)
        root.addLayout(add_row)

        actions_row = QHBoxLayout()
        self.remove_btn = QPushButton("Poista valittu rivi", self)
        self.remove_btn.clicked.connect(self._on_remove_selected)
        self.restore_btn = QPushButton("Palauta oletusavainsanat", self)
        self.restore_btn.clicked.connect(self._on_restore_defaults)
        actions_row.addWidget(self.remove_btn)
        actions_row.addStretch(1)
        actions_row.addWidget(self.restore_btn)
        root.addLayout(actions_row)

    def load_keywords(self, keywords: Mapping[str, str]) -> None:
        """Täyttää taulukon annetulla avainsanasanakirjalla."""
        self.table.setRowCount(0)
        for phrase in sorted(keywords):
            self._append_row(phrase, keywords[phrase])
        self._apply_filter(self.filter_edit.text())

    def collect_rows(self) -> list[tuple[str, str]]:
        """Kerää taulukon kaikki rivit validointia ja tallennusta varten."""
        rows: list[tuple[str, str]] = []
        for row_idx in range(self.table.rowCount()):
            phrase_item = self.table.item(row_idx, 0)
            output_item = self.table.item(row_idx, 1)
            phrase = phrase_item.text() if phrase_item is not None else ""
            output = output_item.text() if output_item is not None else ""
            rows.append((phrase, output))
        return rows

    def _on_preset_selected(self, index: int) -> None:
        token = self.new_output_combo.itemData(index)
        if isinstance(token, str) and token:
            self.new_output_combo.setCurrentText(token)

    def _on_add_clicked(self) -> None:
        phrase = self.new_phrase_edit.text().strip().lower()
        output = self.new_output_combo.currentText().strip()
        if not phrase or not output:
            return

        # Jos sama puhesana on jo taulukossa, päivitetään sen arvo.
        for row_idx in range(self.table.rowCount()):
            item = self.table.item(row_idx, 0)
            if item is not None and item.text().strip().lower() == phrase:
                out_item = self.table.item(row_idx, 1)
                if out_item is not None:
                    out_item.setText(output)
                self.table.selectRow(row_idx)
                self.new_phrase_edit.clear()
                self.new_output_combo.setCurrentIndex(0)
                return

        new_row = self._append_row(phrase, output)
        self.table.selectRow(new_row)
        self.new_phrase_edit.clear()
        self.new_output_combo.setCurrentIndex(0)

    def _on_remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row_idx in rows:
            self.table.removeRow(row_idx)

    def _on_restore_defaults(self) -> None:
        self.load_keywords(DEFAULT_KEYWORDS)

    def _append_row(self, phrase: str, output: str) -> int:
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self.table.setItem(row_idx, 0, QTableWidgetItem(phrase))
        self.table.setItem(row_idx, 1, QTableWidgetItem(output))
        return row_idx

    def _apply_filter(self, query: str) -> None:
        needle = query.strip().lower()
        for row_idx in range(self.table.rowCount()):
            p_item = self.table.item(row_idx, 0)
            o_item = self.table.item(row_idx, 1)
            p_text = p_item.text().lower() if p_item is not None else ""
            o_text = o_item.text().lower() if o_item is not None else ""
            visible = not needle or needle in p_text or needle in o_text
            self.table.setRowHidden(row_idx, not visible)
