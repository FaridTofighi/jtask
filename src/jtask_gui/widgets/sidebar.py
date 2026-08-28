"""Navigation sidebar: quick views, projects, tags, contexts, reports."""

from __future__ import annotations

import datetime

import jdatetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from jtask import jalali

_SPEC_ROLE = Qt.ItemDataRole.UserRole


def _this_week_filter() -> list[str]:
    start, end = jalali.week_range(jdatetime.date.today())
    g_start = start.togregorian() - datetime.timedelta(days=1)
    g_end = end.togregorian() + datetime.timedelta(days=1)
    return [
        f"due.after:{g_start:%Y-%m-%d}",
        f"due.before:{g_end:%Y-%m-%d}",
        "status:pending",
    ]


QUICK_VIEWS = [
    ("امروز", {"kind": "filter", "title": "امروز", "filter": ["due:today", "status:pending"]}),
    ("این هفته", {"kind": "filter", "title": "این هفته", "filter": _this_week_filter}),
    ("معوق", {"kind": "filter", "title": "معوق", "filter": ["+OVERDUE"]}),
    ("اقدامات بعدی", {"kind": "report", "title": "اقدامات بعدی", "fn": "report_ready"}),
    ("در انتظار", {"kind": "report", "title": "در انتظار", "fn": "report_waiting"}),
    ("مسدودشده", {"kind": "report", "title": "مسدودشده", "fn": "report_blocked"}),
    ("تکمیل‌شده", {"kind": "report", "title": "تکمیل‌شده", "fn": "report_completed"}),
]


class Sidebar(QTreeWidget):
    """Emits ``activated(dict)`` describing the view the user picked."""

    activated = pyqtSignal(dict)
    contextChangeRequested = pyqtSignal(str)  # "" clears the context

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setHeaderHidden(True)
        self.setIndentation(12)
        self.setColumnCount(1)
        self.itemClicked.connect(self._on_click)

        self._quick = self._section("نماهای سریع")
        for label, spec in QUICK_VIEWS:
            self._leaf(self._quick, label, spec)

        self._projects = self._section("پروژه‌ها")
        self._tags = self._section("برچسب‌ها")
        self._contexts = self._section("زمینه‌ها")

        self._reports = self._leaf(
            None, "گزارش‌ها و نمودارها", {"kind": "placeholder"}
        )
        self.addTopLevelItem(self._reports)

        self.expandAll()

    # --- build helpers ------------------------------------------

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([title])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        self.addTopLevelItem(item)
        return item

    def _leaf(self, parent, label: str, spec: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, _SPEC_ROLE, spec)
        if parent is not None:
            parent.addChild(item)
        return item

    # --- dynamic population ------------------------------------

    def populate_projects(self, rows: list[dict]) -> None:
        self._projects.takeChildren()
        for row in rows:
            label = f"{row['project']}  ({row['open']})"
            spec = {
                "kind": "filter",
                "title": row["project"],
                "filter": [f"project:{row['project']}", "status:pending"],
            }
            self._leaf(self._projects, label, spec)

    def populate_tags(self, rows: list[dict]) -> None:
        self._tags.takeChildren()
        for row in rows:
            self._leaf(
                self._tags,
                f"#{row['tag']}  ({row['count']})",
                {
                    "kind": "filter",
                    "title": f"#{row['tag']}",
                    "filter": [f"+{row['tag']}", "status:pending"],
                },
            )

    def populate_contexts(self, names: list[str], active: str | None) -> None:
        self._contexts.takeChildren()
        none_item = QTreeWidgetItem(["(بدون زمینه)" + ("  ●" if not active else "")])
        none_item.setData(0, _SPEC_ROLE, {"kind": "context", "name": ""})
        self._contexts.addChild(none_item)
        for name in names:
            mark = "  ●" if name == active else ""
            item = QTreeWidgetItem([name + mark])
            item.setData(0, _SPEC_ROLE, {"kind": "context", "name": name})
            self._contexts.addChild(item)

    # --- events -----------------------------------------------

    def _on_click(self, item: QTreeWidgetItem, _column: int) -> None:
        spec = item.data(0, _SPEC_ROLE)
        if not spec:
            return
        if spec["kind"] == "context":
            self.contextChangeRequested.emit(spec["name"])
            return
        resolved = dict(spec)
        flt = resolved.get("filter")
        if callable(flt):
            resolved["filter"] = flt()
        self.activated.emit(resolved)
