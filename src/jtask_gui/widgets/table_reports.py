"""Projects and Tags reports — sortable tables driven by jtask.reports."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from .. import fmt
from ..i18n import t


class _NumItem(QTableWidgetItem):
    """A cell that displays a Persian-digit number but sorts numerically."""

    def __init__(self, value: float) -> None:
        super().__init__(fmt.num(value))
        self._value = float(value)
        self.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))

    def __lt__(self, other) -> bool:  # noqa: D401 - Qt sort hook
        if isinstance(other, _NumItem):
            return self._value < other._value
        return super().__lt__(other)


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

    def refresh_digits(self) -> None:
        """Re-render numeric cells after a digit-mode change."""
        for r in range(self.rowCount()):
            for c in range(1, self.columnCount()):
                item = self.item(r, c)
                if isinstance(item, _NumItem):
                    item.setText(fmt.num(item._value))

    def _on_activate(self, index) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class ProjectsReport(_BaseTableReport):
    headers = [
        t("table_reports.col.project"), t("table_reports.col.open"),
        t("table_reports.col.waiting"), t("table_reports.col.overdue"),
        t("table_reports.col.percent_done"),
    ]

    def set_data(self, rows: list[dict]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.setItem(r, 0, QTableWidgetItem(row["project"]))
            self.setItem(r, 1, _NumItem(row.get("open", 0)))
            self.setItem(r, 2, _NumItem(row.get("waiting", 0)))
            self.setItem(r, 3, _NumItem(row.get("overdue", 0)))
            self.setItem(r, 4, _NumItem(round(row.get("pct", 0), 1)))
        self.setSortingEnabled(True)

    def _on_activate(self, index) -> None:
        item = self.item(index.row(), 0)
        if item:
            self.rowActivated.emit([f"project:{item.text()}", "status:pending"])


class TagsReport(_BaseTableReport):
    headers = [t("table_reports.col.tag"), t("table_reports.col.count")]

    def set_data(self, rows: list[dict]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.setItem(r, 0, QTableWidgetItem(f"#{row['tag']}"))
            self.setItem(r, 1, _NumItem(row.get("count", 0)))
        self.setSortingEnabled(True)

    def _on_activate(self, index) -> None:
        item = self.item(index.row(), 0)
        if item:
            self.rowActivated.emit([f"+{item.text().lstrip('#')}", "status:pending"])
