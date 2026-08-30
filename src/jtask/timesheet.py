"""Retroactive time-tracking sheet, built from Taskwarrior's own data.

Plain ``task export`` keeps only the *current* ``start``; there is no session
store.  But ``task <id> information`` records every ``Start set`` /
``Start deleted (duration: …)`` pair — a real, first-party session history.
This module stitches those per-task logs into a timesheet.  Timewarrior, when
installed, is a richer optional source; it is **not** required and not assumed
(see ``docs/taskwarrior-feature-matrix.md`` → Timesheet).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from . import history, taskwarrior

__all__ = ["Session", "TaskRow", "Timesheet", "build"]

Session = history.Session

# Cap the per-task ``information`` calls a single build will make.
_MAX_TASKS = 300


@dataclass
class TaskRow:
    uuid: str
    description: str
    project: str
    sessions: list[Session] = field(default_factory=list)

    @property
    def total(self) -> dt.timedelta:
        return sum((s.duration for s in self.sessions), dt.timedelta(0))

    @property
    def running(self) -> bool:
        return any(s.running for s in self.sessions)


@dataclass
class Timesheet:
    rows: list[TaskRow] = field(default_factory=list)
    by_project: dict[str, dt.timedelta] = field(default_factory=dict)
    by_day: dict[dt.date, dt.timedelta] = field(default_factory=dict)
    truncated: bool = False

    @property
    def total(self) -> dt.timedelta:
        return sum((r.total for r in self.rows), dt.timedelta(0))


def _clip(session: Session, lo: dt.datetime, hi: dt.datetime, now: dt.datetime) -> Session | None:
    start = session.start
    end = session.end or now
    if end <= lo or start >= hi:
        return None
    cs, ce = max(start, lo), min(end, hi)
    return Session(cs, None if session.running else ce, ce - cs)


def build(
    filter_args: list[str] | None,
    since: dt.date,
    until: dt.date,
    *,
    now: dt.datetime | None = None,
) -> Timesheet:
    """Sessions overlapping ``[since, until]`` (inclusive days), per task."""
    now = now or dt.datetime.now()
    lo = dt.datetime.combine(since, dt.time.min)
    hi = dt.datetime.combine(until, dt.time.max)

    flt = list(filter_args or [])
    # anything touched in or after the window, plus whatever is running now
    candidates = taskwarrior.export([*flt, f"modified.after:{since.isoformat()}"])
    seen = {t.get("uuid") for t in candidates}
    for t in taskwarrior.export([*flt, "+ACTIVE"]):
        if t.get("uuid") not in seen:
            candidates.append(t)

    sheet = Timesheet()
    if len(candidates) > _MAX_TASKS:
        candidates = candidates[:_MAX_TASKS]
        sheet.truncated = True

    for task in candidates:
        uuid = task.get("uuid") or ""
        if not uuid:
            continue
        rep = history.parse_information(taskwarrior.information(uuid))
        clipped: list[Session] = []
        for s in rep.sessions:
            c = _clip(s, lo, hi, now)
            if c is not None:
                clipped.append(c)
        if not clipped:
            continue
        row = TaskRow(
            uuid=uuid,
            description=task.get("description", ""),
            project=task.get("project", "") or "",
            sessions=clipped,
        )
        sheet.rows.append(row)
        sheet.by_project[row.project] = (
            sheet.by_project.get(row.project, dt.timedelta(0)) + row.total
        )
        for s in clipped:
            day = s.start.date()
            sheet.by_day[day] = sheet.by_day.get(day, dt.timedelta(0)) + s.duration

    sheet.rows.sort(key=lambda r: r.total, reverse=True)
    return sheet
