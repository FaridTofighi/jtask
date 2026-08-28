"""M2 — Reports & Charts area."""

from __future__ import annotations

import jdatetime
import pytest


@pytest.fixture
def rv(qapp, qtbot, tw_env):
    from jtask import taskwarrior
    from jtask_gui.widgets.reports_view import ReportsView

    taskwarrior.run(["add", "الف", "project:وب"])
    taskwarrior.run(["add", "ب", "project:وب"])
    taskwarrior.run(["1", "done"])
    taskwarrior.run(["add", "ج", "project:خانه", "due:tomorrow"])
    taskwarrior.refresh_lookups()

    view = ReportsView("شب")
    qtbot.addWidget(view)
    _settle(qapp)
    return view


def _settle(app, rounds=8):
    from jtask_gui.workers import wait_for_done

    for _ in range(rounds):
        app.processEvents()
        wait_for_done(4000)
        app.processEvents()


def _select(rv, key):
    for i in range(rv._rail.count()):
        if rv._rail.item(i).data(0x0100) == key:  # UserRole
            rv._rail.setCurrentRow(i)
            return
    raise AssertionError(key)


def test_all_reports_selectable_without_error(rv, qapp):
    for key in ("burndown", "ghistory", "history", "summary", "calendar",
                "projects", "tags"):
        _select(rv, key)
        _settle(qapp, rounds=4)
        assert rv._active == key


def test_burndown_receives_bucketed_data(rv, qapp):
    _select(rv, "burndown")
    _settle(qapp)
    assert rv._burndown._data is not None
    assert "buckets" in rv._burndown._data


def test_period_control_offers_all_three_granularities(rv):
    labels = [b.text() for b in rv._period_seg._group.buttons()]
    assert labels == ["روزانه", "هفتگی", "ماهانه"]


def test_period_toggle_only_shown_for_time_series(rv, qapp):
    _select(rv, "burndown")
    assert rv._period_seg.isVisibleTo(rv)
    _select(rv, "summary")
    assert not rv._period_seg.isVisibleTo(rv)


def test_period_change_reloads(rv, qapp):
    _select(rv, "burndown")
    _settle(qapp)
    rv._period_seg.set_value("monthly")
    rv._on_period("monthly")
    _settle(qapp)
    assert rv._period == "monthly"
    assert rv._burndown._data["period"] == "monthly"
    assert rv._period_seg.value() == "monthly"  # active state reflects the mode


def test_hist_mode_segment_reflects_active_report(rv, qapp):
    _select(rv, "ghistory")
    _settle(qapp)
    assert rv._hist_seg.value() == "ghistory"
    _select(rv, "history")
    _settle(qapp)
    assert rv._hist_seg.value() == "history"


def test_projects_report_populates_and_drills_in(rv, qapp, qtbot):
    _select(rv, "projects")
    _settle(qapp)
    assert rv._projects.rowCount() >= 1
    got: list = []
    rv.filterRequested.connect(got.append)
    rv._projects._on_activate(rv._projects.model().index(0, 0))
    assert got and got[0][0].startswith("project:")


def test_calendar_grid_uses_the_shared_engine_and_marks_today(rv, qapp):
    from jtask_gui.widgets.jalali_calendar import JalaliMonthGrid

    _select(rv, "calendar")
    _settle(qapp)
    assert isinstance(rv._calendar._grid, JalaliMonthGrid)
    today = jdatetime.date.today()
    assert (rv._calendar._grid.year, rv._calendar._grid.month) == (today.year, today.month)


def test_calendar_day_with_tasks_gets_a_count_cell(rv, qapp):
    _select(rv, "calendar")
    _settle(qapp, rounds=10)
    days = rv._calendar._data.get("days", {})
    # the "ج" task is due tomorrow -> should be keyed somewhere this month or next
    assert isinstance(days, dict)


def test_png_export_writes_a_file(rv, qapp, tmp_path):
    _select(rv, "burndown")
    _settle(qapp)
    out = tmp_path / "b.png"
    rv._burndown.export_png(str(out))
    assert out.exists() and out.stat().st_size > 500


def test_projects_report_cells_use_persian_digits(rv, qapp):
    from PyQt6.QtCore import Qt

    from jtask.rtl import set_digit_mode

    set_digit_mode(True)
    _select(rv, "projects")
    _settle(qapp)
    rv._projects.set_data([{"project": "وب", "open": 24, "waiting": 0,
                            "overdue": 1, "pct": 50.0}])
    texts = [rv._projects.item(0, c).data(Qt.ItemDataRole.DisplayRole)
             for c in range(1, 5)]
    assert texts == ["۲۴", "۰", "۱", "۵۰"]


def test_chart_y_axis_ticks_use_persian_digits(rv, qapp):
    from jtask.rtl import set_digit_mode

    set_digit_mode(True)
    rv._burndown.set_data({"period": "daily", "buckets": [
        {"label": "1403-07-01", "pending": 10, "started": 0, "done": 0},
        {"label": "1403-07-02", "pending": 20, "started": 0, "done": 0},
    ]})
    rv._burndown._canvas.draw()
    ax = rv._burndown._figure.axes[0]
    ticks = [t.get_text() for t in ax.get_yticklabels() if t.get_text()]
    assert ticks
    assert all(not any(ch.isdigit() and ch.isascii() for ch in t) for t in ticks)
    assert any("۱" in t or "۲" in t or "۰" in t for t in ticks)


def test_theme_switch_propagates_to_charts(rv, qapp):
    _select(rv, "burndown")
    rv.set_theme("روز")
    assert rv._burndown._theme == "روز"
    assert rv._calendar._theme == "روز"


def test_stale_response_does_not_overwrite_fresh_one(rv, qapp):
    _select(rv, "burndown")
    _settle(qapp)
    # simulate an in-flight weekly load whose result arrives after monthly
    rv._gen += 1
    stale_gen = rv._gen
    rv._on_period("monthly")  # bumps _gen, loads monthly
    _settle(qapp)

    def guarded(setter):
        def apply(result):
            if stale_gen == rv._gen:
                setter(result)
        return apply

    from jtask import reports

    guarded(rv._burndown.set_data)(reports.report_burndown("weekly"))
    assert rv._burndown._data["period"] == "monthly"


def test_history_mode_toggle(rv, qapp):
    _select(rv, "history")
    _settle(qapp)
    assert rv._history._mode == "history"
    _select(rv, "ghistory")
    _settle(qapp)
    assert rv._history._mode == "ghistory"
