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

from jtask import jalali, taskwarrior

from .. import fmt
from ..workers import submit

_LABEL_FA = {
    "Pending": "در جریان",
    "Waiting": "در انتظار",
    "Recurring": "تکرارشونده",
    "Completed": "انجام‌شده",
    "Deleted": "حذف‌شده",
    "Total": "کل",
    "Annotations": "یادداشت‌ها",
    "Unique tags": "برچسب‌های یکتا",
    "Projects": "پروژه‌ها",
    "Blocked tasks": "کارهای مسدود",
    "Blocking tasks": "کارهای بازدارنده",
    "Undo transactions": "تراکنش‌های واگرد",
    "Sync backlog transactions": "تراکنش‌های همگام‌سازی معلق",
    "Tasks tagged": "درصد برچسب‌خورده",
    "Oldest task": "قدیمی‌ترین کار",
    "Newest task": "تازه‌ترین کار",
    "Task used for": "بازهٔ استفاده",
    "Task added every": "میانگین فاصلهٔ افزودن",
    "Task completed every": "میانگین فاصلهٔ تکمیل",
    "Average time pending": "میانگین زمان در انتظار",
    "Average desc length": "میانگین طول شرح",
}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNIT_FA = {"characters": "نویسه", "min": "دقیقه", "hours": "ساعت", "days": "روز"}


def _render_value(raw: str) -> str:
    if not raw:
        return "—"
    if _ISO_DATE.match(raw):
        return jalali.from_local(raw, "short")
    m = re.match(r"^(-?[\d.]+)\s*(.*)$", raw)
    if m:
        val = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
        unit = m.group(2).strip()
        if unit == "%":
            return fmt.pct(val)
        num = fmt.num(val)
        return f"{num} {_UNIT_FA.get(unit, unit)}".strip()
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
        self._table.setHorizontalHeaderLabels(["دسته", "مقدار"])
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
            label = QTableWidgetItem(_LABEL_FA.get(cat, cat))
            value = QTableWidgetItem(_render_value(val))
            value.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(r, 0, label)
            self._table.setItem(r, 1, value)
