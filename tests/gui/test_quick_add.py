"""Quick-add parser + widget, end-to-end through to a real task."""

import jdatetime
import pytest

from jtask import reports, taskwarrior
from jtask_gui.quickadd import parse_quick_add, preview_text


@pytest.fixture
def today():
    return jdatetime.date(1403, 7, 10)


def test_parses_description_project_tag_priority_and_relative_date(today):
    p = parse_quick_add("تماس با آرش فردا +تماس pri:H project:کار", today=today)
    assert p.description == "تماس با آرش"
    assert p.project == "کار"
    assert p.tags == ["تماس"]
    assert p.priority == "H"
    assert p.dates["due"] == "۱۴۰۳-۰۷-۱۱"
    assert p.ok


def test_raw_args_are_gregorian(today):
    p = parse_quick_add("خرید due:1403.07.10", today=today)
    assert "due:2024-10-01" in p.raw_args


def test_absolute_jalali_and_persian_digits(today):
    p = parse_quick_add("کار due:۱۴۰۳/۰۸/۰۱", today=today)
    assert p.dates["due"] == "۱۴۰۳-۰۸-۰۱"


def test_invalid_date_is_a_soft_error_not_a_crash(today):
    p = parse_quick_add("کار due:2024-10-01", today=today)
    assert p.errors
    assert not p.ok


def test_preview_text_is_persian_and_mentions_fields(today):
    p = parse_quick_add("جلسه فردا +کار", today=today)
    txt = preview_text(p)
    assert "جلسه" in txt and "#کار" in txt and "سررسید" in txt


def test_widget_creates_task_via_worker(qtbot, tw_env):
    from jtask_gui.widgets.quick_add import QuickAddBar
    from jtask_gui.workers import wait_for_done

    bar = QuickAddBar()
    qtbot.addWidget(bar)
    got: list = []
    bar.taskRequested.connect(got.append)

    bar._edit.setText("خرید نان فردا +خرید")
    bar._commit()
    assert got, "taskRequested should fire for a valid line"

    taskwarrior.add(got[0])
    wait_for_done()
    descs = [t["description"] for t in reports.report_next()]
    assert "خرید نان" in descs
