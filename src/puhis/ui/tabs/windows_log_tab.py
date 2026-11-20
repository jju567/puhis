"""Tallennetut ikkunapaikat (`t1`, `t2`…) ja reaaliaikainen tapahtumaloki -välilehti."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from puhis.core.event_log import EventLog, LogEvent
from puhis.core.window_registry import WindowRegistry


class WindowsLogTab(QWidget):
    """Välilehti tallennetuille ikkuna-aliaksille ja reaaliaikaiselle tapahtumalokille."""

    focus_window_requested = Signal(str)

    def __init__(
        self,
        window_registry: WindowRegistry,
        event_log: EventLog,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = window_registry
        self._event_log = event_log

        root = QVBoxLayout(self)
        root.setSpacing(12)

        win_group = QGroupBox("Tallennetut ikkunapaikat ('puhis save t1', 'puhis t1')", self)
        win_layout = QVBoxLayout(win_group)

        self.windows_table = QTableWidget(0, 4, self)
        self.windows_table.setHorizontalHeaderLabels([
            "Alias",
            "Ikkunan otsikko",
            "Prosessi",
            "HWND",
        ])
        self.windows_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.windows_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.windows_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.windows_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.windows_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.windows_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        win_layout.addWidget(self.windows_table)

        win_btn_row = QHBoxLayout()
        self.focus_win_btn = QPushButton("Tuo valittu ikkuna etualalle", self)
        self.focus_win_btn.clicked.connect(self._on_focus_selected_window)
        self.remove_win_btn = QPushButton("Poista valittu ikkunapaikka", self)
        self.remove_win_btn.clicked.connect(self._on_remove_selected_window)
        self.refresh_win_btn = QPushButton("Päivitä lista", self)
        self.refresh_win_btn.clicked.connect(self.refresh_windows)

        win_btn_row.addWidget(self.focus_win_btn)
        win_btn_row.addWidget(self.remove_win_btn)
        win_btn_row.addStretch(1)
        win_btn_row.addWidget(self.refresh_win_btn)
        win_layout.addLayout(win_btn_row)
        root.addWidget(win_group, stretch=2)

        log_group = QGroupBox("Reaaliaikainen tapahtumaloki (mitä kuultiin & mitä tehtiin)", self)
        log_layout = QVBoxLayout(log_group)

        self.log_table = QTableWidget(0, 3, self)
        self.log_table.setHorizontalHeaderLabels([
            "Aika",
            "Tunnistettu puhe",
            "Suoritettu toiminto",
        ])
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        log_layout.addWidget(self.log_table)

        log_btn_row = QHBoxLayout()
        log_hint = QLabel("Viimeisimmät puhe- ja komentotapahtumat tästä istunnosta.", self)
        self.clear_log_btn = QPushButton("Tyhjennä tapahtumaloki", self)
        self.clear_log_btn.clicked.connect(self._on_clear_log)
        log_btn_row.addWidget(log_hint)
        log_btn_row.addStretch(1)
        log_btn_row.addWidget(self.clear_log_btn)
        log_layout.addLayout(log_btn_row)
        root.addWidget(log_group, stretch=3)

        self.refresh_windows()
        self.refresh_events()

    def refresh_windows(self) -> None:
        """Päivittää tallennettujen ikkunapaikkojen taulukon."""
        entries = self._registry.list_entries()
        self.windows_table.setRowCount(0)
        for entry in entries:
            row_idx = self.windows_table.rowCount()
            self.windows_table.insertRow(row_idx)
            self.windows_table.setItem(row_idx, 0, QTableWidgetItem(entry.alias))
            self.windows_table.setItem(row_idx, 1, QTableWidgetItem(entry.window.title or "(nimetön)"))
            self.windows_table.setItem(row_idx, 2, QTableWidgetItem(entry.window.process_name or "-"))
            self.windows_table.setItem(row_idx, 3, QTableWidgetItem(str(entry.window.hwnd)))

    def refresh_events(self) -> None:
        """Lataa koko tapahtumalokin taulukkoon."""
        self.log_table.setRowCount(0)
        for event in self._event_log.list_events():
            self.append_event_row(event)

    def append_event_row(self, event: LogEvent) -> None:
        """Lisää yksittäisen lokitapahtuman taulukon alkuun (uusin ylimpänä)."""
        self.log_table.insertRow(0)
        ts_item = QTableWidgetItem(event.timestamp)
        ts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        heard_item = QTableWidgetItem(event.heard_text)
        action_item = QTableWidgetItem(event.action_message)
        if not event.success:
            action_item.setForeground(QColor("#EF4444"))

        self.log_table.setItem(0, 0, ts_item)
        self.log_table.setItem(0, 1, heard_item)
        self.log_table.setItem(0, 2, action_item)

        while self.log_table.rowCount() > self._event_log.max_entries:
            self.log_table.removeRow(self.log_table.rowCount() - 1)

    def _on_focus_selected_window(self) -> None:
        alias = self._selected_window_alias()
        if alias:
            self.focus_window_requested.emit(alias)

    def _on_remove_selected_window(self) -> None:
        alias = self._selected_window_alias()
        if alias:
            self._registry.remove(alias)
            self.refresh_windows()

    def _selected_window_alias(self) -> str | None:
        selected = self.windows_table.selectedIndexes()
        if not selected:
            return None
        item = self.windows_table.item(selected[0].row(), 0)
        return item.text().strip() if item is not None else None

    def _on_clear_log(self) -> None:
        self._event_log.clear()
        self.log_table.setRowCount(0)
