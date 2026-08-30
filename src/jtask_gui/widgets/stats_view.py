"""Statistics view — a Jalali/Persian rendering of ``task stats``."""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from .. import fmt
from ..calendar_system import active
from ..i18n import t
from ..workers import submit

_LABEL_KEY = {
    "Pending": "stats.Pending", "Waiting": "stats.Waiting", "Recurring": "stats.Recurring",
    "Completed": "stats.Completed", "Deleted": "stats.Deleted", "Total": "stats.Total",
    "Annotations": "stats.Annotations", "Unique tags": "stats.UniqueTags",
    "Projects": "stats.Projects", "Blocked tasks": "stats.BlockedTasks",
    "Blocking tasks": "stats.BlockingTasks", "Undo transactions": "stats.UndoTransactions",
    "Sync backlog transactions": "stats.SyncBacklog", "Tasks tagged": "stats.TasksTagged",
    "Oldest task": "stats.OldestTask", "Newest task": "stats.NewestTask",
    "Task used for": "stats.TaskUsedFor", "Task added every": "stats.TaskAddedEvery",
    "Task completed every": "stats.TaskCompletedEvery",
    "Average time pending": "stats.AvgTimePending", "Average desc length": "stats.AvgDescLength",
}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNIT_KEY = {
    "characters": "stats.unit.characters", "min": "stats.unit.min",
    "hours": "stats.unit.hours", "days": "stats.unit.days",
}


def _render_value(raw: str) -> str:
    if not raw:
        return "—"
    if _ISO_DATE.match(raw):
        return active().format_local(raw, "short")
    m = re.match(r"^(-?[\d.]+)\s*(.*)$", raw)
    if m:
        val = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
        unit = m.group(2).strip()
        if unit == "%":
            return fmt.pct(val)
        num = fmt.num(val)
        return f"{num} {t(_UNIT_KEY[unit]) if unit in _UNIT_KEY else unit}".strip()
    return fmt.digits(raw)


class StatsView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatsView")
        self._filter: list[str] | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 2)
        self._table.setObjectName("StatsTable")
        self._table.setHorizontalHeaderLabels(
            [t("stats.col.category"), t("stats.col.value")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self._table)

    def set_filter(self, tokens: list[str]) -> None:
        self._filter = tokens or None

    def reload(self) -> None:
        submit(lambda: taskwarrior.stats(self._filter), self._render, lambda _e: None)

    def refresh_digits(self) -> None:
        self.reload()

    def _render(self, pairs: list[tuple[str, str]]) -> None:
        self._table.setRowCount(len(pairs))
        for r, (cat, val) in enumerate(pairs):
            label = QTableWidgetItem(t(_LABEL_KEY[cat]) if cat in _LABEL_KEY else cat)
            value = QTableWidgetItem(_render_value(val))
            value.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(r, 0, label)
            self._table.setItem(r, 1, value)
