"""Timesheet — time-tracking sessions rebuilt from Taskwarrior's own log.

Honestly labelled: this is not a live tracker, it is a reconstruction from the
``Start set`` / ``Start deleted (duration:…)`` entries Taskwarrior records.
Timewarrior, if installed, is noted as a richer optional source.
"""

from __future__ import annotations

import datetime as dt

import jdatetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import timesheet, timew
from jtask.rtl import auto_isolate

from .. import fmt
from .. import tokens as tok
from ..bidi import content_alignment
from ..calendar_system import active
from ..i18n import t
from ..workers import submit
from .jalali_date_picker import JalaliDatePicker
from .segmented import SegmentedControl


def _hm(d: dt.timedelta) -> str:
    total = int(d.total_seconds())
    h, m = divmod(total // 60, 60)
    return fmt.digits(f"{h}:{m:02d}")


def _clock(moment: dt.datetime) -> str:
    return fmt.digits(moment.strftime("%H:%M"))


class TimesheetView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimesheetView")
        self._filter: list[str] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_8)

        bar = QHBoxLayout()
        bar.setSpacing(tok.SP_6)
        bar.addWidget(QLabel(t("word.from")))
        self._from = JalaliDatePicker()
        bar.addWidget(self._from)
        bar.addWidget(QLabel(t("word.to")))
        self._to = JalaliDatePicker()
        bar.addWidget(self._to)
        self._go = QPushButton(t("ts.refresh"))
        self._go.setObjectName("Primary")
        self._go.clicked.connect(self.reload)
        bar.addWidget(self._go)
        bar.addStretch(1)
        lay.addLayout(bar)

        src = QHBoxLayout()
        src.setSpacing(tok.SP_6)
        src.addWidget(QLabel(t("ts.source")))
        self._source = SegmentedControl([
            (t("ts.source.taskwarrior"), "tw"),
            (t("ts.source.timewarrior"), "timew"),
        ])
        self._source.changed.connect(lambda _v: self.reload())
        self._source._group.button(1).setEnabled(timew.available())
        src.addWidget(self._source)
        src.addStretch(1)
        lay.addLayout(src)

        start, end = active().week_bounds()
        self._from.set_value(start)
        self._to.set_value(end)

        self._tree = QTreeWidget()
        self._tree.setObjectName("TimesheetTree")
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(
            [t("ts.col.task_session"), t("ts.col.project"), t("ts.col.duration")]
        )
        self._tree.header().setStretchLastSection(False)
        self._tree.setColumnWidth(0, 320)
        lay.addWidget(self._tree, 1)

        self._empty = QLabel(t("ts.empty"))
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()
        lay.addWidget(self._empty, 1)

        self._summary = QLabel("")
        self._summary.setObjectName("H2")
        lay.addWidget(self._summary)

        self._note = QLabel("")
        self._note.setObjectName("Muted")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)
        self._update_note()

    def _update_note(self) -> None:
        if self._source.value() == "timew":
            self._note.setText(t("ts.note.timew_active"))
        elif timew.available():
            self._note.setText(t("ts.note.base") + t("ts.note.timew"))
        else:
            self._note.setText(t("ts.note.base") + ".")

    def set_filter(self, tokens: list[str]) -> None:
        self._filter = tokens or None

    def refresh_digits(self) -> None:
        self.reload()

    def reload(self) -> None:
        fv, tv = self._from.value(), self._to.value()
        if fv is None or tv is None:
            return
        since = fv.togregorian() if isinstance(fv, jdatetime.date) else fv
        until = tv.togregorian() if isinstance(tv, jdatetime.date) else tv
        if isinstance(since, dt.datetime):
            since = since.date()
        if isinstance(until, dt.datetime):
            until = until.date()
        self._summary.setText(t("ts.calculating"))
        self._update_note()
        if self._source.value() == "timew" and timew.available():
            submit(
                lambda: timew.summary(since, until),
                self._render_timew,
                lambda _e: self._summary.setText(t("ts.calc_failed")),
            )
            return
        submit(
            lambda: timesheet.build(self._filter, since, until),
            self._render,
            lambda _e: self._summary.setText(t("ts.calc_failed")),
        )

    def _render_timew(self, s: timew.Summary) -> None:
        self._tree.clear()
        for tag, total in sorted(s.by_tag.items(), key=lambda kv: kv[1], reverse=True):
            self._tree.addTopLevelItem(QTreeWidgetItem([tag, "", _hm(total)]))
        self._empty.setVisible(not s.by_tag)
        self._tree.setVisible(bool(s.by_tag))
        if not s.by_tag:
            self._summary.setText("")
            return
        days = t("list.sep_wide").join(
            f"{active().format_local(d.strftime('%Y-%m-%d'), 'short')}: {_hm(dur)}"
            for d, dur in sorted(s.by_day.items())
        )
        self._summary.setText(
            t("ts.summary", total=_hm(s.total), projects=days, extra="")
        )

    def _render(self, sheet: timesheet.Timesheet) -> None:
        self._tree.clear()
        vc = Qt.AlignmentFlag.AlignVCenter
        for row in sheet.rows:
            top = QTreeWidgetItem(
                [auto_isolate(row.description), auto_isolate(row.project or "—"), _hm(row.total)]
            )
            if row.running:
                top.setText(0, "▶ " + auto_isolate(row.description))
            top.setTextAlignment(0, content_alignment(row.description) | vc)
            top.setTextAlignment(1, content_alignment(row.project or "") | vc)
            self._tree.addTopLevelItem(top)
            for s in row.sessions:
                span = (
                    f"{_clock(s.start)} — "
                    + (t("ts.running") if s.running else _clock(s.end))
                    if s.end or s.running
                    else _clock(s.start)
                )
                child = QTreeWidgetItem([f"    {span}", "", _hm(s.duration)])
                top.addChild(child)
            top.setExpanded(True)

        self._empty.setVisible(not sheet.rows)
        self._tree.setVisible(bool(sheet.rows))
        if not sheet.rows:
            self._summary.clear()
            return

        projects = t("list.sep_wide").join(
            f"{p or '—'}: {_hm(d)}" for p, d in sorted(
                sheet.by_project.items(), key=lambda kv: kv[1], reverse=True
            )
        )
        extra = t("ts.truncated") if sheet.truncated else ""
        self._summary.setText(
            t("ts.summary", total=_hm(sheet.total), projects=projects, extra=extra)
        )

    def sizeHint(self):  # noqa: N802
        from PyQt6.QtCore import QSize

        return QSize(820, 520)
