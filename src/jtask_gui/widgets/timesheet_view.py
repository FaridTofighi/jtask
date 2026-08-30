"""Timesheet — time-tracking sessions rebuilt from Taskwarrior's own log.

Honestly labelled: this is not a live tracker, it is a reconstruction from the
``Start set`` / ``Start deleted (duration:…)`` entries Taskwarrior records.
Timewarrior, if installed, is noted as a richer optional source.
"""

from __future__ import annotations

import datetime as dt
import shutil

import jdatetime
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import timesheet

from .. import fmt
from .. import tokens as tok
from ..calendar_system import active
from ..i18n import t
from ..workers import submit
from .jalali_date_picker import JalaliDatePicker


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

        self._summary = QLabel("")
        self._summary.setObjectName("H2")
        lay.addWidget(self._summary)

        note = (
            t("ts.note.base")
            + (t("ts.note.timew") if shutil.which("timew") else ".")
        )
        self._note = QLabel(note)
        self._note.setObjectName("Muted")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)

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
        submit(
            lambda: timesheet.build(self._filter, since, until),
            self._render,
            lambda _e: self._summary.setText(t("ts.calc_failed")),
        )

    def _render(self, sheet: timesheet.Timesheet) -> None:
        self._tree.clear()
        for row in sheet.rows:
            top = QTreeWidgetItem(
                [row.description, row.project or "—", _hm(row.total)]
            )
            if row.running:
                top.setText(0, "▶ " + row.description)
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

        if not sheet.rows:
            self._summary.setText(t("ts.empty"))
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
