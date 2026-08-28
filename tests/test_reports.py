"""Tests for the framework-agnostic report data-shaping layer."""

from __future__ import annotations

import datetime

import jdatetime
import pytest

from jtask import jalali, reports

TEHRAN = datetime.timezone(datetime.timedelta(hours=3, minutes=30))


@pytest.fixture(autouse=True)
def _tz(monkeypatch):
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)


def _utc(y, m, d, hh=12):
    # noon UTC -> mid-afternoon in Tehran, safely inside the same local day
    return f"{y:04d}{m:02d}{d:02d}T{hh:02d}0000Z"


# 2024-10-01 noon UTC  ->  1403-07-10 local
_DUE_1403_07_10 = _utc(2024, 10, 1)


def _task(**kw):
    base = {"uuid": kw.get("uuid", "u"), "description": "x", "status": "pending"}
    base.update(kw)
    return base


# --- task list reports -------------------------------------------------

def test_shape_tasklist_converts_dates_and_keeps_gregorian():
    tasks = [_task(due=_DUE_1403_07_10, entry=_utc(2024, 1, 1))]
    out = reports.shape_task_list(tasks)
    assert out[0]["due"] == "۱۴۰۳-۰۷-۱۰"
    assert out[0]["due_gregorian"].startswith("20241001")


# --- projects --------------------------------------------------------

def test_projects_report_counts_and_percentage():
    tasks = [
        _task(uuid="1", project="وب", status="completed", end=_utc(2024, 6, 1)),
        _task(uuid="2", project="وب", status="pending"),
        _task(uuid="3", project="وب", status="pending", due=_utc(2000, 1, 1)),  # overdue
        _task(uuid="4", project="خانه", status="pending"),
    ]
    rows = {r["project"]: r for r in reports.shape_projects(tasks)}
    assert rows["وب"]["open"] == 2
    assert rows["وب"]["completed"] == 1
    assert rows["وب"]["overdue"] == 1
    assert rows["وب"]["pct"] == pytest.approx(33.3, abs=0.1)
    assert rows["خانه"]["open"] == 1


def test_projects_report_includes_dotted_hierarchy():
    tasks = [_task(uuid="1", project="Work.Backend", status="pending")]
    rows = [r["project"] for r in reports.shape_projects(tasks)]
    assert "Work.Backend" in rows


# --- tags -----------------------------------------------------------

def test_tags_report_excludes_virtual_tags():
    tasks = [
        _task(uuid="1", tags=["urgent", "OVERDUE", "PENDING"]),
        _task(uuid="2", tags=["urgent", "web"]),
    ]
    rows = {r["tag"]: r["count"] for r in reports.shape_tags(tasks)}
    assert rows == {"urgent": 2, "web": 1}


# --- history / ghistory --------------------------------------------

def test_history_monthly_buckets_added_completed_deleted():
    # Mehr 1403 == 2024-09-22 .. 2024-10-21
    tasks = [
        _task(uuid="1", entry=_utc(2024, 9, 25), status="pending"),
        _task(uuid="2", entry=_utc(2024, 10, 1), end=_utc(2024, 10, 5), status="completed"),
        _task(uuid="3", entry=_utc(2024, 8, 1), end=_utc(2024, 10, 10), status="deleted"),
    ]
    out = reports.shape_history(tasks, period="monthly")
    by_label = {b["label"]: b for b in out["buckets"]}
    mehr = "مهر 1403"  # labels carry ASCII digits
    assert by_label[mehr]["added"] == 2
    assert by_label[mehr]["completed"] == 1
    assert by_label[mehr]["deleted"] == 1


def test_history_weekly_labels_are_jalali_year_week():
    tasks = [_task(uuid="1", entry=_utc(2024, 9, 24), status="pending")]
    out = reports.shape_history(tasks, period="weekly")
    assert out["buckets"]
    assert all("-w" in b["label"] or "هفته" in b["label"] for b in out["buckets"])


# --- burndown -----------------------------------------------------

def test_burndown_daily_series_shape():
    tasks = [
        _task(uuid="1", entry=_utc(2024, 9, 20), status="pending"),
        _task(uuid="2", entry=_utc(2024, 9, 20), end=_utc(2024, 9, 24), status="completed"),
    ]
    out = reports.shape_burndown(tasks, period="daily", today=jdatetime.date(1403, 7, 5))
    assert set(out["buckets"][0]) == {"label", "pending", "started", "done"}
    last = out["buckets"][-1]
    assert last["done"] == 1
    assert last["pending"] == 1


def test_burndown_rejects_bad_period():
    with pytest.raises(ValueError):
        reports.shape_burndown([], period="hourly")


# --- calendar ---------------------------------------------------

def test_calendar_keys_tasks_on_jalali_day():
    tasks = [_task(uuid="1", due=_DUE_1403_07_10)]
    out = reports.shape_calendar(tasks, 1403, 7)
    assert (1403, 7, 10) in out["days"]
    assert out["days"][(1403, 7, 10)][0]["uuid"] == "1"
    assert out["grid"][0][0] is None  # 1403-07-01 is a Sunday -> one leading blank


def test_calendar_empty_month_has_grid_no_days():
    out = reports.shape_calendar([], 1404, 1)
    assert out["days"] == {}
    assert len(out["grid"]) >= 4
