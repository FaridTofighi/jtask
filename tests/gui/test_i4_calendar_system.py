"""i4 — CalendarSystem abstraction: Jalali and Gregorian, and the active() switch.

The stored Taskwarrior value is Gregorian/UTC in every case; only the *display*
and the *input parsing* change with the calendar system.
"""

from __future__ import annotations

import datetime as dt

import pytest

from jtask_gui import calendar_system as cs
from jtask_gui import i18n
from jtask_gui.settings import Settings


@pytest.fixture(autouse=True)
def _reset_active():
    """Every test starts with no cached active() instance."""
    cs._active = None
    yield
    cs._active = None


@pytest.fixture
def fa():
    prev = i18n.lang()
    i18n.set_language("fa")
    yield
    i18n.set_language(prev)


@pytest.fixture
def en():
    prev = i18n.lang()
    i18n.set_language("en")
    yield
    i18n.set_language(prev)


# --- Jalali ------------------------------------------------------------

def test_jalali_shape(fa):
    j = cs.JalaliCalendarSystem()
    assert j.id == "jalali"
    assert j.week_start_pyweekday() == 5  # Saturday
    assert len(j.month_names()) == 12
    assert j.month_names()[0] == "فروردین"
    grid = j.month_grid(1403, 1)
    assert all(len(w) == 7 for w in grid)
    assert sum(d is not None for w in grid for d in w) == 31


def test_jalali_latin_names_in_english_ui(en):
    j = cs.JalaliCalendarSystem()
    assert j.month_names()[0] == "Farvardin"
    assert j.month_names()[11] == "Esfand"
    assert j.weekday_names_short() == ["Sh", "Ye", "Do", "Se", "Ch", "Pa", "Jo"]
    assert j.label_ym(1403, 7) == "Mehr 1403"


def test_jalali_roundtrip_date():
    j = cs.JalaliCalendarSystem()
    greg = j.to_gregorian_date(1403, 7, 10)
    assert greg == dt.date(2024, 10, 1)
    assert j.from_gregorian_date(greg) == (1403, 7, 10)


def test_jalali_format_utc_matches_core(fa):
    from jtask import jalali

    j = cs.JalaliCalendarSystem()
    ts = "20241001T093000Z"
    assert j.format_utc(ts, "short") == jalali.from_taskwarrior(ts, fmt="short")


def test_jalali_to_taskwarrior_absolute():
    j = cs.JalaliCalendarSystem()
    assert j.to_taskwarrior("1403.07.10").startswith("2024-10-01")
    # an unrecognised relative word passes through for Taskwarrior to resolve
    assert j.to_taskwarrior("nonsense-token") == "nonsense-token"


# --- Gregorian --------------------------------------------------------

def test_gregorian_shape_monday_start():
    g = cs.GregorianCalendarSystem(week_start_pyweekday=0)
    assert g.id == "gregorian"
    assert g.weekday_names_short()[0] == "Mon"
    assert g.month_names()[9] == "October"
    grid = g.month_grid(2024, 10)  # Oct 2024 starts on a Tuesday
    assert all(len(w) == 7 for w in grid)
    assert grid[0][0] is None and grid[0][1] == 1
    assert sum(d is not None for w in grid for d in w) == 31


def test_gregorian_shape_sunday_start():
    g = cs.GregorianCalendarSystem(week_start_pyweekday=6)
    assert g.weekday_names_short()[0] == "Sun"
    grid = g.month_grid(2024, 10)  # Tuesday → 2 leading blanks from Sunday
    assert grid[0][:2] == [None, None]
    assert grid[0][2] == 1


def test_gregorian_roundtrip_and_identity():
    g = cs.GregorianCalendarSystem()
    assert g.to_gregorian_date(2024, 10, 1) == dt.date(2024, 10, 1)
    assert g.from_gregorian_date(dt.date(2024, 10, 1)) == (2024, 10, 1)


def test_gregorian_format_utc_is_iso_localised():
    g = cs.GregorianCalendarSystem()
    out = g.format_utc("20241001T000000Z", "short")
    # digits() may localise the glyphs; the ASCII skeleton is an ISO date
    from jtask.jalali import normalize_digits

    assert normalize_digits(out) == "2024-10-01"


def test_gregorian_to_taskwarrior():
    g = cs.GregorianCalendarSystem()
    assert g.to_taskwarrior("2024-10-01") == "2024-10-01"
    assert g.to_taskwarrior("2024/10/01 09:30") == "2024-10-01T09:30:00"
    assert g.to_taskwarrior("") == ""
    assert g.to_taskwarrior("tomorrow") == "tomorrow"  # left for Taskwarrior


def test_gregorian_invalid_date_passes_through():
    g = cs.GregorianCalendarSystem()
    assert g.to_taskwarrior("2024-13-40") == "2024-13-40"


# --- week_bounds -----------------------------------------------------

def test_week_bounds_respects_system_start():
    wed = dt.date(2024, 10, 2)  # a Wednesday
    j_start, j_end = cs.JalaliCalendarSystem().week_bounds(wed)
    assert j_start.weekday() == 5 and (j_end - j_start).days == 6
    assert j_start <= wed <= j_end

    g_start, g_end = cs.GregorianCalendarSystem(0).week_bounds(wed)
    assert g_start == dt.date(2024, 9, 30) and g_end == dt.date(2024, 10, 6)


# --- active() switch -------------------------------------------------

def test_active_follows_settings(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").setValue("calendar", "gregorian")
    cs._active = None
    assert isinstance(cs.active(), cs.GregorianCalendarSystem)

    QSettings("jtask", "jtask-gui").setValue("calendar", "jalali")
    cs.set_calendar("jalali")
    assert isinstance(cs.active(), cs.JalaliCalendarSystem)


def test_settings_calendar_persists(qapp):
    s = Settings()
    original = s.calendar
    try:
        s.calendar = "gregorian"
        assert Settings().calendar == "gregorian"
        s.calendar = "bogus"
        assert Settings().calendar == "jalali"  # invalid falls back
    finally:
        s.calendar = original
