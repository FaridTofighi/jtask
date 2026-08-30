"""M9 — end-to-end date-grammar regression sweep.

Exercises ``rewrite.rewrite_args`` (the path every CLI arg and every GUI token
travels) across the full grammar: absolute Jalali, Persian relatives, date math,
every date attribute + ``.before``/``.after`` modifiers, recurrence durations
that must be left alone, date UDAs, and the Gregorian-mistake guard.

Fixed reference: Jalali 1403-07-10 == Gregorian 2024-10-01 (Tehran).
"""

from __future__ import annotations

import datetime as dt

import jdatetime
import pytest

from jtask import jalali, rewrite
from jtask.errors import JtaskError

TEHRAN = dt.timezone(dt.timedelta(hours=3, minutes=30))
TODAY = jdatetime.date(1403, 7, 10)  # a Tuesday


@pytest.fixture(autouse=True)
def _tz(monkeypatch):
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)


def rw(*args: str, udas=()):
    return rewrite.rewrite_args(list(args), date_udas=udas, today=TODAY)


# --- absolute Jalali ------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["1403.07.10", "1403/07/10", "1403-07-10", "۱۴۰۳-۰۷-۱۰", "۱۴۰۳/۷/۱۰"],
)
def test_absolute_jalali_all_separators_and_digits(raw):
    assert rw(f"due:{raw}") == ["due:2024-10-01"]


def test_absolute_jalali_with_time():
    assert rw("due:1403-07-10T14:30") == ["due:2024-10-01T14:30:00"]
    assert rw("due:1403-07-10T14:30:45") == ["due:2024-10-01T14:30:45"]


def test_esfand_leap_boundary():
    # 1403 is a leap year → 30 Esfand exists → 1404-03-20 Gregorian
    assert rw("due:1403-12-30") == ["due:2025-03-20"]


# --- Persian relatives --------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("امروز", "2024-10-01"),
        ("فردا", "2024-10-02"),
        ("دیروز", "2024-09-30"),
        ("پس‌فردا", "2024-10-03"),
        ("پریروز", "2024-09-29"),
    ],
)
def test_persian_relative_keywords(word, expected):
    assert rw(f"due:{word}") == [f"due:{expected}"]


def test_persian_relative_offsets():
    assert rw("due:۳ روز دیگر") == ["due:2024-10-04"]
    assert rw("due:۲ روز پیش") == ["due:2024-09-29"]


# --- date math tails --------------------------------------------------


def test_date_math_preserved_after_conversion():
    assert rw("due:1403-07-10+3d") == ["due:2024-10-01+3d"]
    assert rw("due:فردا+1wk") == ["due:2024-10-02+1wk"]


def test_english_keywords_pass_through_untouched():
    for kw in ("today", "tomorrow", "eom", "sow", "monday", "now"):
        assert rw(f"due:{kw}") == [f"due:{kw}"]
    assert rw("due:now+2d") == ["due:now+2d"]


# --- every date attribute + modifiers --------------------------------


@pytest.mark.parametrize("attr", sorted(rewrite.DATE_ATTRS))
def test_all_date_attributes_convert(attr):
    assert rw(f"{attr}:1403-07-10") == [f"{attr}:2024-10-01"]


@pytest.mark.parametrize("mod", ["before", "after", "is", "isnt", "not", "under", "over", "by"])
def test_date_modifiers_convert(mod):
    assert rw(f"due.{mod}:1403-07-10") == [f"due.{mod}:2024-10-01"]


def test_unknown_modifier_left_alone():
    assert rw("due.none:") == ["due.none:"]
    assert rw("due.any:") == ["due.any:"]


# --- things that must NOT be touched --------------------------------


def test_recurrence_duration_not_a_date():
    assert rw("recur:weekly") == ["recur:weekly"]
    assert rw("recur:3d") == ["recur:3d"]


def test_non_date_attributes_pass_through():
    assert rw("project:خانه", "priority:H", "+فوری", "-later") == [
        "project:خانه", "priority:H", "+فوری", "-later"
    ]


def test_description_with_colon_is_not_a_token():
    assert rw("خرید: نان و شیر") == ["خرید: نان و شیر"]


def test_plain_words_and_ids_pass_through():
    assert rw("add", "تماس با آرش", "1-5", "/regex/") == [
        "add", "تماس با آرش", "1-5", "/regex/"
    ]


# --- date UDAs ------------------------------------------------------


def test_date_uda_converts_only_when_declared():
    assert rw("reviewed:1403-07-10") == ["reviewed:1403-07-10"]
    assert rw("reviewed:1403-07-10", udas=["reviewed"]) == ["reviewed:2024-10-01"]
    assert rw("reviewed.before:فردا", udas=["reviewed"]) == ["reviewed.before:2024-10-02"]


# --- Gregorian-mistake guard --------------------------------------


def test_gregorian_looking_bare_date_is_rejected():
    with pytest.raises(JtaskError):
        rw("due:2024-10-01")


def test_round_trip_losslessness():
    for j in (
        jdatetime.date(1403, 1, 1),
        jdatetime.date(1403, 12, 30),
        jdatetime.date(1404, 6, 31),
        jdatetime.date(1399, 11, 22),
    ):
        s = f"{j.year:04d}-{j.month:02d}-{j.day:02d}"
        [out] = rw(f"due:{s}")
        greg = dt.date.fromisoformat(out.split(":", 1)[1])
        assert jdatetime.date.fromgregorian(date=greg) == j
