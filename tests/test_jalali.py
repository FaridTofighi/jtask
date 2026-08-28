"""Tests for the Jalali conversion + parsing layer."""

import datetime

import jdatetime
import pytest

from jtask import jalali


# --- digit handling -------------------------------------------------------

def test_normalize_digits_persian_to_ascii():
    assert jalali.normalize_digits("۱۴۰۳/۰۷/۱۰") == "1403/07/10"


def test_normalize_digits_arabic_indic_to_ascii():
    assert jalali.normalize_digits("١٤٠٣") == "1403"


def test_to_persian_digits():
    assert jalali.to_persian_digits("1403-07-10") == "۱۴۰۳-۰۷-۱۰"


# --- absolute parsing ---------------------------------------------------

@pytest.mark.parametrize("text", ["1403/07/10", "1403-07-10", "1403.07.10", "۱۴۰۳.۰۷.۱۰"])
def test_parse_jalali_accepts_all_separators_and_digits(text):
    d = jalali.parse_jalali(text)
    assert (d.year, d.month, d.day) == (1403, 7, 10)
    assert not isinstance(d, jdatetime.datetime)


def test_parse_jalali_with_time_returns_datetime():
    d = jalali.parse_jalali("1403.07.10T14:30")
    assert isinstance(d, jdatetime.datetime)
    assert (d.hour, d.minute) == (14, 30)


def test_parse_jalali_rejects_two_digit_year():
    with pytest.raises(jalali.JalaliError):
        jalali.parse_jalali("03/07/10")


def test_parse_jalali_rejects_gregorian_looking_year():
    with pytest.raises(jalali.JalaliError):
        jalali.parse_jalali("2024-10-01")


def test_parse_jalali_rejects_impossible_date():
    with pytest.raises(jalali.JalaliError):
        jalali.parse_jalali("1403.13.01")


def test_parse_jalali_error_message_is_persian():
    with pytest.raises(jalali.JalaliError) as exc:
        jalali.parse_jalali("2024-10-01")
    assert any("؀" <= ch <= "ۿ" for ch in str(exc.value))


# --- leap years & month lengths ---------------------------------------

def test_is_leap_year():
    assert jalali.is_leap(1403) is True
    assert jalali.is_leap(1404) is False


def test_month_length():
    assert jalali.month_length(1403, 1) == 31
    assert jalali.month_length(1403, 7) == 30
    assert jalali.month_length(1403, 12) == 30  # 1403 is leap
    assert jalali.month_length(1404, 12) == 29  # 1404 is not


def test_parse_esfand_30_only_valid_in_leap_year():
    assert jalali.parse_jalali("1403.12.30").day == 30
    with pytest.raises(jalali.JalaliError):
        jalali.parse_jalali("1404.12.30")


# --- conversion to gregorian -----------------------------------------

def test_to_gregorian_string_date_only():
    assert jalali.to_gregorian_string("1403.07.10") == "2024-10-01"


def test_to_gregorian_string_with_time():
    assert jalali.to_gregorian_string("1403.07.10T14:30") == "2024-10-01T14:30:00"


def test_roundtrip_is_lossless_across_year_boundary():
    for text in ["1402.12.29", "1403.01.01", "1403.06.31", "1403.07.01", "1403.12.30"]:
        greg = jalali.to_gregorian_string(text)
        back = jdatetime.date.fromgregorian(
            date=datetime.date.fromisoformat(greg)
        )
        assert back.strftime("%Y.%m.%d") == text


# --- taskwarrior UTC -> jalali display -------------------------------

def test_from_taskwarrior_short_format(monkeypatch):
    monkeypatch.setattr(jalali, "LOCAL_TZ", datetime.timezone(datetime.timedelta(hours=3, minutes=30)))
    assert jalali.from_taskwarrior("20240930T203000Z", fmt="short") == "۱۴۰۳-۰۷-۱۰"


def test_from_taskwarrior_long_format(monkeypatch):
    monkeypatch.setattr(jalali, "LOCAL_TZ", datetime.timezone(datetime.timedelta(hours=3, minutes=30)))
    out = jalali.from_taskwarrior("20240930T203000Z", fmt="long")
    assert "مهر" in out and "۱۴۰۳" in out


def test_from_taskwarrior_empty_returns_empty():
    assert jalali.from_taskwarrior("") == ""


# --- persian relative dates -----------------------------------------

@pytest.fixture
def today():
    # 1403-07-10 == Tuesday
    return jdatetime.date(1403, 7, 10)


def test_relative_emrooz(today):
    assert jalali.parse_relative("امروز", today=today) == today


def test_relative_farda(today):
    assert jalali.parse_relative("فردا", today=today) == jdatetime.date(1403, 7, 11)


def test_relative_dirooz(today):
    assert jalali.parse_relative("دیروز", today=today) == jdatetime.date(1403, 7, 9)


def test_relative_n_days_ahead(today):
    assert jalali.parse_relative("۳ روز دیگر", today=today) == jdatetime.date(1403, 7, 13)


def test_relative_n_days_ago(today):
    assert jalali.parse_relative("۵ روز پیش", today=today) == jdatetime.date(1403, 7, 5)


def test_relative_next_saturday(today):
    # Tuesday 1403-07-10 -> "شنبه بعد" is 1403-07-14
    assert jalali.parse_relative("شنبه بعد", today=today) == jdatetime.date(1403, 7, 14)


def test_relative_end_of_week_is_friday(today):
    # week starts Saturday; end is Friday 1403-07-13
    assert jalali.parse_relative("پایان هفته", today=today) == jdatetime.date(1403, 7, 13)


def test_relative_first_of_next_month(today):
    assert jalali.parse_relative("اول ماه بعد", today=today) == jdatetime.date(1403, 8, 1)


def test_relative_unknown_returns_none(today):
    assert jalali.parse_relative("چرند", today=today) is None


def test_resolve_accepts_relative_and_absolute(today):
    assert jalali.to_gregorian_string("فردا", today=today) == "2024-10-02"
    assert jalali.to_gregorian_string("1403.07.10") == "2024-10-01"


# --- calendar helpers ----------------------------------------------

def test_weekday_saturday_is_zero():
    # 1403-07-13 is a Friday -> index 6; 1403-07-14 Saturday -> 0
    assert jalali.weekday_sat(jdatetime.date(1403, 7, 14)) == 0
    assert jalali.weekday_sat(jdatetime.date(1403, 7, 13)) == 6


def test_week_range_starts_saturday(today):
    start, end = jalali.week_range(today)
    assert start == jdatetime.date(1403, 7, 7)   # Saturday
    assert end == jdatetime.date(1403, 7, 13)    # Friday


def test_month_grid_first_row_padded_to_weekday():
    grid = jalali.month_grid(1403, 7)
    # 1403-07-01 is a Sunday -> one leading blank
    assert grid[0][0] is None
    assert grid[0][1] == 1
    assert grid[-1][-1] == 30 or 30 in grid[-1]
