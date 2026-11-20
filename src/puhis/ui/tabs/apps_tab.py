"""Sallitut puheella käynnistettävät sovellukset -välilehti."""

from collections.abc import Mapping, Sequence
import shlex

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
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

from puhis.core.config_store import DEFAULT_APP_ALIASES


class AppsTab(QWidget):
    """Välilehti valkolistattujen sovellusaliasten (`puhis avaa <nimi>`) hallintaan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        info = QLabel(
            "Määrittele ohjelmat, jotka voit käynnistää puheella ('puhis avaa <nimi>'). "
            "Tietoturvasyistä vain tässä listassa olevat ohjelmat voidaan käynnistää, "
            "ja käynnistyksen jälkeen sanelutila kytkeytyy heti päälle.",
            self,
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels([
            "Puhenimi (esim. selain)",
            "Ohjelma / .exe-polku",
            "Argumentit (valinnainen)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        root.addWidget(self.table, stretch=1)

        add_row = QHBoxLayout()
        self.new_alias_edit = QLineEdit(self)
        self.new_alias_edit.setPlaceholderText("Puhenimi (esim. selain)")
        self.new_exe_edit = QLineEdit(self)
        self.new_exe_edit.setPlaceholderText("Polku tai .exe (esim. msedge.exe)")
        self.new_args_edit = QLineEdit(self)
        self.new_args_edit.setPlaceholderText("Argumentit (valinnainen)")

        self.browse_btn = QPushButton("Selaa .exe…", self)
        self.browse_btn.clicked.connect(self._on_browse_exe)

        self.add_btn = QPushButton("+ Lisää / päivitä", self)
        self.add_btn.clicked.connect(self._on_add_clicked)

        add_row.addWidget(self.new_alias_edit, stretch=2)
        add_row.addWidget(self.new_exe_edit, stretch=3)
        add_row.addWidget(self.browse_btn)
        add_row.addWidget(self.new_args_edit, stretch=2)
        add_row.addWidget(self.add_btn)
        root.addLayout(add_row)

        actions_row = QHBoxLayout()
        self.remove_btn = QPushButton("Poista valittu sovellus", self)
        self.remove_btn.clicked.connect(self._on_remove_selected)
        self.restore_btn = QPushButton("Palauta oletussovellukset", self)
        self.restore_btn.clicked.connect(self._on_restore_defaults)
        actions_row.addWidget(self.remove_btn)
        actions_row.addStretch(1)
        actions_row.addWidget(self.restore_btn)
        root.addLayout(actions_row)

    def load_app_aliases(self, app_aliases: Mapping[str, Sequence[str]]) -> None:
        """Täyttää taulukon annetuilla sovellusaliaksilla."""
        self.table.setRowCount(0)
        for alias in sorted(app_aliases):
            cmd = list(app_aliases[alias])
            if not cmd:
                continue
            exe = cmd[0]
            args_str = " ".join(cmd[1:]) if len(cmd) > 1 else ""
            self._append_row(alias, exe, args_str)

    def collect_rows(self) -> list[tuple[str, list[str]]]:
        """Kerää taulukon rivit validointia ja tallennusta varten."""
        rows: list[tuple[str, list[str]]] = []
        for row_idx in range(self.table.rowCount()):
            alias_item = self.table.item(row_idx, 0)
            exe_item = self.table.item(row_idx, 1)
            args_item = self.table.item(row_idx, 2)

            alias = alias_item.text().strip() if alias_item is not None else ""
            exe = exe_item.text().strip() if exe_item is not None else ""
            args_text = args_item.text().strip() if args_item is not None else ""

            cmd_parts: list[str] = []
            if exe:
                cmd_parts.append(exe)
            if args_text:
                try:
                    cmd_parts.extend(shlex.split(args_text, posix=False))
                except ValueError:
                    cmd_parts.extend(args_text.split())
            rows.append((alias, cmd_parts))
        return rows

    def _on_browse_exe(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Valitse käynnistettävä ohjelma (.exe)",
            "",
            "Ohjelmat (*.exe);;Kaikki tiedostot (*.*)",
        )
        if file_path:
            self.new_exe_edit.setText(file_path)

    def _on_add_clicked(self) -> None:
        alias = self.new_alias_edit.text().strip().lower()
        exe = self.new_exe_edit.text().strip()
        args_str = self.new_args_edit.text().strip()
        if not alias or not exe:
            return

        for row_idx in range(self.table.rowCount()):
            item = self.table.item(row_idx, 0)
            if item is not None and item.text().strip().lower() == alias:
                self.table.setItem(row_idx, 1, QTableWidgetItem(exe))
                self.table.setItem(row_idx, 2, QTableWidgetItem(args_str))
                self.table.selectRow(row_idx)
                self._clear_inputs()
                return

        new_row = self._append_row(alias, exe, args_str)
        self.table.selectRow(new_row)
        self._clear_inputs()

    def _clear_inputs(self) -> None:
        self.new_alias_edit.clear()
        self.new_exe_edit.clear()
        self.new_args_edit.clear()

    def _on_remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row_idx in rows:
            self.table.removeRow(row_idx)

    def _on_restore_defaults(self) -> None:
        self.load_app_aliases(DEFAULT_APP_ALIASES)

    def _append_row(self, alias: str, exe: str, args_str: str) -> int:
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self.table.setItem(row_idx, 0, QTableWidgetItem(alias))
        self.table.setItem(row_idx, 1, QTableWidgetItem(exe))
        self.table.setItem(row_idx, 2, QTableWidgetItem(args_str))
        return row_idx
