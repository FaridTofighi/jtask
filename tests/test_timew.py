"""N-E: the Timewarrior wrapper + Timesheet-view source toggle."""

from __future__ import annotations

import datetime as dt

from jtask import timew


def test_available_reflects_the_path(monkeypatch):
    monkeypatch.setattr(timew.shutil, "which", lambda _n: "/usr/bin/timew")
    assert timew.available() is True
    monkeypatch.setattr(timew.shutil, "which", lambda _n: None)
    assert timew.available() is False


def test_intervals_empty_when_timew_absent(monkeypatch):
    monkeypatch.setattr(timew, "available", lambda: False)
    assert timew.intervals(dt.date(2026, 9, 1), dt.date(2026, 9, 7)) == []


def test_summary_parses_export_json(monkeypatch):
    monkeypatch.setattr(timew, "available", lambda: True)
    monkeypatch.setattr(timew, "_run", lambda _a: (
        '[{"id":2,"start":"20260901T060000Z","end":"20260901T073000Z",'
        '"tags":["Write report","proj:Work"]},'
        '{"id":1,"start":"20260901T100000Z","end":"20260901T110000Z",'
        '"tags":["Review"]}]'
    ))
    s = timew.summary(dt.date(2026, 9, 1), dt.date(2026, 9, 1),
                      local_tz=dt.timezone.utc)
    assert s.total == dt.timedelta(hours=2, minutes=30)
    assert s.by_tag["Write report"] == dt.timedelta(hours=1, minutes=30)
    assert s.by_tag["proj:Work"] == dt.timedelta(hours=1, minutes=30)
    assert s.by_tag["Review"] == dt.timedelta(hours=1)
    assert s.by_day[dt.date(2026, 9, 1)] == dt.timedelta(hours=2, minutes=30)


def test_summary_survives_garbage(monkeypatch):
    monkeypatch.setattr(timew, "available", lambda: True)
    monkeypatch.setattr(timew, "_run", lambda _a: "not json")
    s = timew.summary(dt.date(2026, 9, 1), dt.date(2026, 9, 2))
    assert s.total == dt.timedelta() and s.by_tag == {}


# --- the Timesheet view --------------------------------------------

def test_timesheet_view_source_toggle(qtbot, monkeypatch):
    from jtask_gui.widgets.timesheet_view import TimesheetView

    monkeypatch.setattr(timew, "available", lambda: True)
    v = TimesheetView()
    qtbot.addWidget(v)
    assert v._source.value() == "tw"                       # default = reconstruction
    assert v._source._group.button(1).isEnabled()          # timew option enabled
    assert "Timewarrior" in v._note.text() or "بازسازی" in v._note.text()

    v._source.set_value("timew")
    v._update_note()
    assert "Timewarrior" in v._note.text() or "بازه" in v._note.text()


def test_timesheet_timew_option_disabled_when_absent(qtbot, monkeypatch):
    from jtask_gui.widgets.timesheet_view import TimesheetView

    monkeypatch.setattr(timew, "available", lambda: False)
    v = TimesheetView()
    qtbot.addWidget(v)
    assert not v._source._group.button(1).isEnabled()


def test_timew_render_groups_by_tag(qtbot):
    from jtask_gui.widgets.timesheet_view import TimesheetView

    v = TimesheetView()
    qtbot.addWidget(v)
    s = timew.Summary(
        total=dt.timedelta(hours=3),
        by_tag={"deep work": dt.timedelta(hours=2), "email": dt.timedelta(hours=1)},
        by_day={dt.date(2026, 9, 1): dt.timedelta(hours=3)},
    )
    v._render_timew(s)
    labels = [v._tree.topLevelItem(i).text(0) for i in range(v._tree.topLevelItemCount())]
    assert labels == ["deep work", "email"]               # ranked by duration
    assert not v._tree.isHidden() and v._empty.isHidden()
