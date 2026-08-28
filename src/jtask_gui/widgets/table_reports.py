"""Projects and Tags reports — sortable tables driven by jtask.reports."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from jtask.rtl import fa_digits


class _BaseTableReport(QTableWidget):
    rowActivated = pyqtSignal(list)  # a filter for the main task list

    headers: list[str] = []

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(len(self.headers))
        self.setHorizontalHeaderLabels(self.headers)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.doubleClicked.connect(self._on_activate)

    def _num(self, value) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, fa_digits(str(value)))
        item.setData(Qt.ItemDataRole.EditRole, float(value))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _on_activate(self, index) -> None:
        raise NotImplementedError


class ProjectsReport(_BaseTableReport):
    headers = ["پروژه", "باز", "در انتظار", "عقب‌افتاده", "٪ تکمیل"]

    def set_data(self, rows: list[dict]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            name = QTableWidgetItem(row["project"])
            self.setItem(r, 0, name)
            self.setItem(r, 1, self._num(row.get("open", 0)))
            self.setItem(r, 2, self._num(row.get("waiting", 0)))
            self.setItem(r, 3, self._num(row.get("overdue", 0)))
            self.setItem(r, 4, self._num(round(row.get("pct", 0), 1)))
        self.setSortingEnabled(True)

    def _on_activate(self, index) -> None:
        item = self.item(index.row(), 0)
        if item:
            self.rowActivated.emit([f"project:{item.text()}", "status:pending"])


class TagsReport(_BaseTableReport):
    headers = ["برچسب", "تعداد"]

    def set_data(self, rows: list[dict]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.setItem(r, 0, QTableWidgetItem(f"#{row['tag']}"))
            self.setItem(r, 1, self._num(row.get("count", 0)))
        self.setSortingEnabled(True)

    def _on_activate(self, index) -> None:
        item = self.item(index.row(), 0)
        if item:
            self.rowActivated.emit([f"+{item.text().lstrip('#')}", "status:pending"])
