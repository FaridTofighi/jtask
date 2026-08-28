"""Tests for the date-token rewriting layer (both directions)."""

import datetime

import jdatetime
import pytest

from jtask import jalali, rewrite
from jtask.errors import JtaskError


@pytest.fixture
def today():
    return jdatetime.date(1403, 7, 10)


# --- input: args Jalali -> Gregorian ---------------------------------

def test_rewrites_due_attribute():
    out = rewrite.rewrite_args(["add", "خرید", "due:1403.07.10"])
    assert out == ["add", "خرید", "due:2024-10-01"]


def test_rewrites_attribute_modifier_form():
    out = rewrite.rewrite_args(["list", "due.before:1403.08.01"])
    assert out == ["list", "due.before:2024-10-22"]


def test_rewrites_datetime_with_time():
    out = rewrite.rewrite_args(["add", "جلسه", "due:1403.07.10T14:30"])
    assert out == ["add", "جلسه", "due:2024-10-01T14:30:00"]


def test_preserves_taskwarrior_date_math_tail(today):
    out = rewrite.rewrite_args(["add", "کار", "due:فردا+3d"], today=today)
    assert out == ["add", "کار", "due:2024-10-02+3d"]


def test_leaves_recur_duration_untouched():
    out = rewrite.rewrite_args(["add", "قبض", "recur:monthly", "due:1403.07.10"])
    assert out == ["add", "قبض", "recur:monthly", "due:2024-10-01"]


def test_leaves_non_date_attributes_untouched():
    args = ["add", "کار", "project:Website", "priority:H", "+tag"]
    assert rewrite.rewrite_args(args) == args


def test_leaves_persian_description_with_colon_untouched():
    args = ["add", "خرید: شیر و نان"]
    assert rewrite.rewrite_args(args) == args


def test_passes_through_english_taskwarrior_keyword(today):
    out = rewrite.rewrite_args(["list", "due:today"], today=today)
    assert out == ["list", "due:today"]


def test_rejects_gregorian_looking_date():
    with pytest.raises(JtaskError):
        rewrite.rewrite_args(["add", "x", "due:2024-10-01"])


def test_rewrites_date_typed_uda():
    out = rewrite.rewrite_args(["add", "x", "reviewed:1403.07.10"], date_udas={"reviewed"})
    assert out == ["add", "x", "reviewed:2024-10-01"]


def test_empty_value_is_left_alone():
    assert rewrite.rewrite_args(["modify", "due:"]) == ["modify", "due:"]


# --- output: task dicts Gregorian UTC -> Jalali ----------------------

@pytest.fixture(autouse=True)
def _tehran_tz(monkeypatch):
    monkeypatch.setattr(
        jalali, "LOCAL_TZ", datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    )


def test_rewrites_task_date_fields_for_display():
    task = {"id": 1, "description": "x", "due": "20240930T203000Z", "entry": "20240101T000000Z"}
    out = rewrite.rewrite_task_dates(task)
    assert out["due"] == "۱۴۰۳-۰۷-۱۰"
    assert out["description"] == "x"
    assert out["id"] == 1


def test_keep_gregorian_attaches_both_representations():
    task = {"due": "20240930T203000Z"}
    out = rewrite.rewrite_task_dates(task, keep_gregorian=True)
    assert out["due"] == "۱۴۰۳-۰۷-۱۰"
    assert out["due_gregorian"] == "20240930T203000Z"


def test_rewrites_annotation_entry_dates():
    task = {
        "description": "x",
        "annotations": [{"entry": "20240930T203000Z", "description": "یادداشت"}],
    }
    out = rewrite.rewrite_task_dates(task)
    assert out["annotations"][0]["entry"] == "۱۴۰۳-۰۷-۱۰"


def test_rewrites_date_uda_field_on_output():
    task = {"reviewed": "20240930T203000Z"}
    out = rewrite.rewrite_task_dates(task, date_udas={"reviewed"})
    assert out["reviewed"] == "۱۴۰۳-۰۷-۱۰"


def test_long_format_uses_month_name():
    task = {"due": "20240930T203000Z"}
    out = rewrite.rewrite_task_dates(task, fmt="long")
    assert "مهر" in out["due"]
