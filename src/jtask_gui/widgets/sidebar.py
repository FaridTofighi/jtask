"""Navigation sidebar: quick views, projects, tags, contexts, reports."""

from __future__ import annotations

import datetime

import jdatetime
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from jtask import jalali

from .. import icons

_SPEC_ROLE = Qt.ItemDataRole.UserRole
_ICON_ROLE = Qt.ItemDataRole.UserRole + 5


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
    ("امروز", "today",
     {"kind": "filter", "title": "امروز", "filter": ["due:today", "status:pending"]}),
    ("این هفته", "week",
     {"kind": "filter", "title": "این هفته", "filter": _this_week_filter}),
    ("معوق", "overdue", {"kind": "filter", "title": "معوق", "filter": ["+OVERDUE"]}),
    ("اقدامات بعدی", "next",
     {"kind": "report", "title": "اقدامات بعدی", "fn": "report_ready"}),
    ("در انتظار", "waiting",
     {"kind": "report", "title": "در انتظار", "fn": "report_waiting"}),
    ("مسدودشده", "blocked",
     {"kind": "report", "title": "مسدودشده", "fn": "report_blocked"}),
    ("تکمیل‌شده", "completed",
     {"kind": "report", "title": "تکمیل‌شده", "fn": "report_completed"}),
]


class Sidebar(QTreeWidget):
    """Emits ``activated(dict)`` describing the view the user picked."""

    activated = pyqtSignal(dict)
    contextChangeRequested = pyqtSignal(str)  # "" clears the context

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setHeaderHidden(True)
        self.setIndentation(10)
        self.setColumnCount(1)
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(False)
        self.itemClicked.connect(self._on_click)

        self._quick = self._section("نماهای سریع")
        for label, glyph, spec in QUICK_VIEWS:
            self._leaf(self._quick, label, spec, glyph)

        gap = QTreeWidgetItem([""])
        gap.setFlags(Qt.ItemFlag.NoItemFlags)
        gap.setSizeHint(0, QSize(1, 10))
        self.addTopLevelItem(gap)

        self._reports = self._leaf(
            None, "  گزارش‌ها و نمودارها", {"kind": "placeholder"}, "reports"
        )
        f = self._reports.font(0)
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 0.5)
        self._reports.setFont(0, f)
        self.addTopLevelItem(self._reports)

        gap2 = QTreeWidgetItem([""])
        gap2.setFlags(Qt.ItemFlag.NoItemFlags)
        gap2.setSizeHint(0, QSize(1, 6))
        self.addTopLevelItem(gap2)

        self._projects = self._section("پروژه‌ها")
        self._tags = self._section("برچسب‌ها")
        self._contexts = self._section("زمینه‌ها")

        self.expandAll()
        self.retint()

    # --- build helpers ------------------------------------------

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([title])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = item.font(0)
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() - 1)
        item.setFont(0, font)
        self.addTopLevelItem(item)
        return item

    def _leaf(self, parent, label: str, spec: dict, glyph: str | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, _SPEC_ROLE, spec)
        if glyph:
            item.setData(0, _ICON_ROLE, glyph)
        if parent is not None:
            parent.addChild(item)
        return item

    def retint(self) -> None:
        """Re-tint every row icon for the active theme."""
        it = self._iter_items(self.invisibleRootItem())
        for item in it:
            glyph = item.data(0, _ICON_ROLE)
            if glyph:
                item.setIcon(0, icons.icon(glyph, "text_muted"))

    def _iter_items(self, root):
        for i in range(root.childCount()):
            child = root.child(i)
            yield child
            yield from self._iter_items(child)

    # --- dynamic population ------------------------------------

    def populate_projects(self, rows: list[dict]) -> None:
        self._projects.takeChildren()
        for row in rows:
            label = f"{row['project']}  ·  {row['open']}"
            spec = {
                "kind": "filter",
                "title": row["project"],
                "filter": [f"project:{row['project']}", "status:pending"],
            }
            self._leaf(self._projects, label, spec, "project")
        self.retint()

    def populate_tags(self, rows: list[dict]) -> None:
        self._tags.takeChildren()
        for row in rows:
            self._leaf(
                self._tags,
                f"#{row['tag']}  ·  {row['count']}",
                {
                    "kind": "filter",
                    "title": f"#{row['tag']}",
                    "filter": [f"+{row['tag']}", "status:pending"],
                },
                "tag",
            )
        self.retint()

    def populate_contexts(self, names: list[str], active: str | None) -> None:
        self._contexts.takeChildren()
        none_item = QTreeWidgetItem(["بدون زمینه" + ("  ●" if not active else "")])
        none_item.setData(0, _SPEC_ROLE, {"kind": "context", "name": ""})
        none_item.setData(0, _ICON_ROLE, "context")
        self._contexts.addChild(none_item)
        for name in names:
            mark = "  ●" if name == active else ""
            item = QTreeWidgetItem([name + mark])
            item.setData(0, _SPEC_ROLE, {"kind": "context", "name": name})
            item.setData(0, _ICON_ROLE, "context")
            self._contexts.addChild(item)
        self.retint()

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
