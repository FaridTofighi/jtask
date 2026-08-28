"""Renders a discovered custom ``.taskrc`` report as a sortable table."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from .. import fmt


class GenericReport(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)

    def set_data(self, data: dict) -> None:
        cols = data.get("columns", [])
        labels = data.get("labels", cols)
        rows = data.get("rows", [])

        self.setSortingEnabled(False)
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(labels)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                text = fmt.digits(value) if _looks_numeric(value) else value
                item = QTableWidgetItem(text)
                if c == 0:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                self.setItem(r, c, item)
        if cols:
            self.horizontalHeader().setSectionResizeMode(
                len(cols) - 1, QHeaderView.ResizeMode.Stretch
            )
        self.setSortingEnabled(True)


def _looks_numeric(value: str) -> bool:
    v = value.strip().replace("-", "").replace(".", "").replace(",", "")
    return bool(v) and v.isdigit()
