"""Per-task change history — a Jalali, Persian rendering of Taskwarrior's own
``Date | Modification`` log (nothing fabricated; the raw line is always shown).
"""

from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import history, jalali, taskwarrior

from ..workers import submit

_ATTR_FA = {
    "Priority": "اولویت",
    "Project": "پروژه",
    "Due": "سررسید",
    "Scheduled": "زمان‌بندی",
    "Wait": "تاریخ انتظار",
    "Until": "مهلت",
    "Start": "شروع زمان‌سنجی",
    "End": "پایان",
    "Entry": "ایجاد",
    "Status": "وضعیت",
    "Description": "شرح",
    "Recur": "تکرار",
    "Modified": "آخرین ویرایش",
}
_STATUS_FA = {
    "pending": "در جریان",
    "completed": "انجام‌شده",
    "deleted": "حذف‌شده",
    "waiting": "در انتظار",
    "recurring": "تکرارشونده",
}
_DATE_ATTRS = {"Due", "Scheduled", "Wait", "Until", "Start", "End", "Entry", "Modified"}


def _val(attr: str, raw: str) -> str:
    if attr in _DATE_ATTRS:
        return jalali.from_local(raw, "datetime")
    if attr == "Status":
        return _STATUS_FA.get(raw, raw)
    return raw


def _fa_duration(d: dt.timedelta) -> str:
    total = int(d.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return jalali.to_persian_digits(f"{h}:{m:02d}:{s:02d}")
    return jalali.to_persian_digits(f"{m}:{s:02d}")


def describe(ch: history.ChangeEntry) -> str:
    attr = _ATTR_FA.get(ch.attr, ch.attr)
    if ch.kind == "annotation_added":
        return f"یادداشت «{ch.new}» افزوده شد"
    if ch.kind == "annotation_deleted":
        return f"یادداشت «{ch.new}» حذف شد"
    if ch.kind == "tag_added":
        return f"برچسب «{ch.new}» افزوده شد"
    if ch.kind == "tag_deleted":
        return f"برچسب «{ch.old}» حذف شد"
    if ch.attr == "Start":
        if ch.kind == "set":
            return f"زمان‌سنجی آغاز شد ({jalali.from_local(ch.new or '', 'datetime')})"
        if ch.kind == "deleted":
            dur = f" — مدت {_fa_duration(ch.duration)}" if ch.duration is not None else ""
            return f"زمان‌سنجی متوقف شد{dur}"
    if ch.kind == "changed":
        old_v = _val(ch.attr, ch.old or "")
        new_v = _val(ch.attr, ch.new or "")
        return f"{attr} از «{old_v}» به «{new_v}» تغییر کرد"
    if ch.kind == "set":
        return f"{attr}: «{_val(ch.attr, ch.new or '')}»"
    if ch.kind == "deleted":
        if ch.duration is not None:
            return f"{attr} پایان یافت (مدت: {_fa_duration(ch.duration)})"
        return f"{attr} پاک شد"
    return ch.raw


class TaskHistoryView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryView")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self._anchors = QLabel("")
        self._anchors.setObjectName("Muted")
        self._anchors.setWordWrap(True)
        lay.addWidget(self._anchors)

        self._tree = QTreeWidget()
        self._tree.setObjectName("HistoryTree")
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["زمان", "تغییر"])
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(False)
        self._tree.header().setStretchLastSection(True)
        lay.addWidget(self._tree, 1)

        self._empty = QLabel("تاریخچه‌ای برای این کار ثبت نشده است.")
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)
        lay.addWidget(self._empty)

        self._uuid: str | None = None

    def load_task(self, task: dict) -> None:
        uuid = task.get("uuid")
        self._uuid = uuid
        self._tree.clear()
        self._anchors.clear()
        if not uuid:
            return
        submit(
            lambda: history.parse_information(taskwarrior.information(uuid)),
            self._render,
            lambda _e: self._render(None),
        )

    def _render(self, rep: history.InformationReport | None) -> None:
        self._tree.clear()
        if rep is None or not rep.changes:
            self._empty.setVisible(True)
            self._tree.setVisible(False)
            return
        self._empty.setVisible(False)
        self._tree.setVisible(True)

        anchors = []
        for keys, label in (
            (("Entered", "Entry"), "ایجاد"),
            (("Last modified", "Modified"), "آخرین ویرایش"),
            (("End", "Ended"), "پایان"),
        ):
            raw = next((rep.attributes[k] for k in keys if rep.attributes.get(k)), "")
            if raw:
                shown = jalali.from_local(raw.split(" (")[0], "long")
                anchors.append(f"{label}: {shown}")
        self._anchors.setText("   ·   ".join(anchors))

        by_day: dict[str, list[history.ChangeEntry]] = {}
        for ch in rep.changes:
            day = jalali.from_local(ch.when.strftime("%Y-%m-%d"), "long")
            by_day.setdefault(day, []).append(ch)

        for day, entries in by_day.items():
            head = QTreeWidgetItem([day, ""])
            head.setFirstColumnSpanned(True)
            head.setExpanded(True)
            self._tree.addTopLevelItem(head)
            head.setExpanded(True)
            for ch in entries:
                t = jalali.to_persian_digits(ch.when.strftime("%H:%M"))
                row = QTreeWidgetItem([t, describe(ch)])
                row.setToolTip(1, ch.raw)
                head.addChild(row)
        self._tree.expandAll()
        self._tree.resizeColumnToContents(0)
