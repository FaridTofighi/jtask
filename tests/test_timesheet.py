"""Timesheet reconstruction from Taskwarrior's modification log."""

from __future__ import annotations

import datetime as dt

from jtask import timesheet


class FakeTW:
    def __init__(self, tasks, infos):
        self._tasks = tasks
        self._infos = infos

    def export(self, filter_args=None):
        return list(self._tasks)

    def information(self, spec):
        return self._infos[spec]


INFO_A = """
Date                Modification
------------------- ------------------------
2026-08-28 09:00:00 Start set to '2026-08-28 09:00:00'.
2026-08-28 11:00:00 Start deleted (duration: 2:00:00).
2026-08-29 14:00:00 Start set to '2026-08-29 14:00:00'.
2026-08-29 15:30:00 Start deleted (duration: 1:30:00).
"""

INFO_B = """
Date                Modification
------------------- ------------------------
2026-08-29 10:00:00 Start set to '2026-08-29 10:00:00'.
2026-08-29 10:45:00 Start deleted (duration: 0:45:00).
"""


def _tw():
    return FakeTW(
        tasks=[
            {"uuid": "a", "description": "کار الف", "project": "وب"},
            {"uuid": "b", "description": "کار ب", "project": "وب"},
        ],
        infos={"a": INFO_A, "b": INFO_B},
    )


def test_sessions_within_range_only(monkeypatch):
    monkeypatch.setattr(timesheet, "taskwarrior", _tw())
    rep = timesheet.build(None, dt.date(2026, 8, 29), dt.date(2026, 8, 29))
    # only the 08-29 sessions survive
    all_sessions = [s for r in rep.rows for s in r.sessions]
    assert len(all_sessions) == 2
    assert rep.total == dt.timedelta(hours=2, minutes=15)


def test_full_range_groups_by_task_and_totals(monkeypatch):
    monkeypatch.setattr(timesheet, "taskwarrior", _tw())
    rep = timesheet.build(None, dt.date(2026, 8, 28), dt.date(2026, 8, 31))
    by_uuid = {r.uuid: r for r in rep.rows}
    assert by_uuid["a"].total == dt.timedelta(hours=3, minutes=30)
    assert by_uuid["b"].total == dt.timedelta(minutes=45)
    assert rep.total == dt.timedelta(hours=4, minutes=15)
    assert rep.by_project["وب"] == dt.timedelta(hours=4, minutes=15)


def test_by_day_breakdown(monkeypatch):
    monkeypatch.setattr(timesheet, "taskwarrior", _tw())
    rep = timesheet.build(None, dt.date(2026, 8, 28), dt.date(2026, 8, 31))
    assert rep.by_day[dt.date(2026, 8, 28)] == dt.timedelta(hours=2)
    assert rep.by_day[dt.date(2026, 8, 29)] == dt.timedelta(hours=2, minutes=15)


def test_tasks_with_no_sessions_are_dropped(monkeypatch):
    tw = FakeTW(
        tasks=[{"uuid": "a", "description": "x", "project": ""}],
        infos={"a": "Name Value\nID 1\n"},
    )
    monkeypatch.setattr(timesheet, "taskwarrior", tw)
    rep = timesheet.build(None, dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    assert rep.rows == []
    assert rep.total == dt.timedelta(0)
