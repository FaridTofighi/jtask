"""M3 core additions: report specs, urgency breakdown, custom report rendering."""

from __future__ import annotations

import datetime
import shutil

import pytest

from jtask import jalali, reports, taskwarrior

pytestmark = pytest.mark.skipif(
    shutil.which("task") is None, reason="Taskwarrior not installed"
)

TEHRAN = datetime.timezone(datetime.timedelta(hours=3, minutes=30))


@pytest.fixture
def tw(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text(
        "report.mine.description=کارهای من\n"
        "report.mine.columns=id,project,description,due\n"
        "report.mine.labels=ش,پروژه,شرح,سررسید\n"
        "report.mine.filter=status:pending\n"
        "report.mine.sort=due+\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TASKRC", str(rc))
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)
    taskwarrior.refresh_lookups()
    yield
    taskwarrior.refresh_lookups()


def test_report_specs_discovers_custom_report(tw):
    specs = taskwarrior.report_specs()
    assert "mine" in specs
    assert specs["mine"]["description"] == "کارهای من"
    assert specs["mine"]["columns"].startswith("id,project")
    # built-ins are present too
    assert "next" in specs


def test_list_reports_falls_back_to_specs(tw):
    assert "mine" in taskwarrior.list_reports()


def test_run_custom_report_shapes_columns_and_jalali_dates(tw):
    taskwarrior.add(["خرید نان", "project:خانه", "due:2024-10-01"])
    out = reports.run_custom_report("mine")
    assert out["labels"] == ["ش", "پروژه", "شرح", "سررسید"]
    assert out["columns"] == ["id", "project", "description", "due"]
    row = out["rows"][0]
    assert row[1] == "خانه"
    assert row[2] == "خرید نان"
    assert row[3] == "۱۴۰۳-۰۷-۱۰"  # Jalali, not the raw UTC stamp


def test_run_custom_report_unknown_name_raises(tw):
    with pytest.raises(ValueError):
        reports.run_custom_report("does-not-exist")


def test_urgency_terms_parsed_from_info(tw):
    taskwarrior.add(["مهم", "project:X", "priority:H", "+next", "due:tomorrow"])
    uuid = taskwarrior.export(["1"])[0]["uuid"]
    terms = taskwarrior.urgency_terms(uuid)
    assert terms
    labels = {t["label"] for t in terms}
    assert any("priority" in x.lower() or "TAG" in x or "due" in x for x in labels)
    for t in terms:
        assert t["coefficient"] * t["weight"] == pytest.approx(t["value"], abs=0.05)
