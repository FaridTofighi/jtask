"""Jalali (Persian / Solar Hijri) calendar layer.

Everything date-related in jtask goes through this module:

* parsing user input (absolute Jalali dates or Persian relative expressions),
* converting Jalali -> Gregorian for handing off to the ``task`` binary,
* converting Taskwarrior's stored UTC timestamps back to Jalali for display,
* calendar math where the week starts on **Saturday**.

The conversion itself is delegated to :mod:`jdatetime`; we never hand-roll
Julian-day arithmetic.  Times of day are interpreted in the system local
timezone (Taskwarrior stores everything as UTC).
"""

from __future__ import annotations

import datetime
import re

import jdatetime

__all__ = [
    "JalaliError",
    "normalize_digits",
    "to_persian_digits",
    "parse_jalali",
    "parse_relative",
    "resolve",
    "to_gregorian_string",
    "from_taskwarrior",
    "from_local",
    "is_leap",
    "month_length",
    "weekday_sat",
    "week_range",
    "month_grid",
    "MONTH_NAMES",
    "WEEKDAY_NAMES",
    "WEEKDAY_NAMES_SHORT",
]

# Local timezone, resolved once.  Tests monkeypatch this.
LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo or datetime.timezone.utc

MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# Jalali week starts on Saturday.
WEEKDAY_NAMES = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
WEEKDAY_NAMES_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"]

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII_DIGITS = "0123456789"
_TO_ASCII = {
    ord(p): a for p, a in zip(_PERSIAN_DIGITS + _ARABIC_DIGITS, _ASCII_DIGITS * 2, strict=True)
}
_TO_PERSIAN = {ord(a): p for a, p in zip(_ASCII_DIGITS, _PERSIAN_DIGITS, strict=True)}

# Jalali leap years within the 2820-year cycle, per the 33-year sub-cycle rule
# used by jdatetime internally.
_LEAP_REMAINDERS = frozenset({1, 5, 9, 13, 17, 22, 26, 30})


class JalaliError(ValueError):
    """Raised for any invalid Jalali date input, with a Persian message."""


def normalize_digits(text: str) -> str:
    """Convert Persian and Arabic-Indic digits in *text* to ASCII digits."""
    return text.translate(_TO_ASCII)


def to_persian_digits(text: str) -> str:
    """Convert ASCII digits in *text* to Persian digits."""
    return text.translate(_TO_PERSIAN)


def is_leap(year: int) -> bool:
    """Return whether *year* is a Jalali leap year."""
    return year % 33 in _LEAP_REMAINDERS


def month_length(year: int, month: int) -> int:
    """Number of days in Jalali *month* of *year*."""
    if not 1 <= month <= 12:
        raise JalaliError(f"ماه نامعتبر است: {month}")
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if is_leap(year) else 29


_DATE_RE = re.compile(
    r"^\s*(\d{1,4})[./-](\d{1,2})[./-](\d{1,2})"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$"
)


def parse_jalali(text: str) -> jdatetime.date | jdatetime.datetime:
    """Parse an absolute Jalali date (or datetime) string.

    Accepts ``.`` ``/`` ``-`` separators and Persian/Arabic/ASCII digits.
    A trailing ``THH:MM[:SS]`` (or space-separated) yields a datetime.
    """
    raw = normalize_digits(text)
    m = _DATE_RE.match(raw)
    if not m:
        raise JalaliError(f"قالب تاریخ جلالی قابل تشخیص نیست: «{text}»")

    year_s, month_s, day_s, hh, mm, ss = m.groups()
    if len(year_s) < 3:
        raise JalaliError(
            f"سال باید چهار رقمی باشد؛ «{year_s}» مبهم است (مثلاً ۱۴۰۳)."
        )
    year, month, day = int(year_s), int(month_s), int(day_s)

    if year >= 1700:
        raise JalaliError(
            f"«{year}» شبیه سال میلادی است، نه جلالی. اگر واقعاً میلادی است "
            f"از پرچم --gregorian استفاده کنید."
        )
    if not 1 <= month <= 12:
        raise JalaliError(f"ماه نامعتبر است: {month}")
    if not 1 <= day <= month_length(year, month):
        raise JalaliError(
            f"روز {day} در ماه {MONTH_NAMES[month - 1]} سال {year} وجود ندارد."
        )

    try:
        if hh is not None:
            return jdatetime.datetime(
                year, month, day, int(hh), int(mm), int(ss) if ss else 0
            )
        return jdatetime.date(year, month, day)
    except ValueError as exc:  # pragma: no cover - guarded above
        raise JalaliError(f"تاریخ جلالی نامعتبر است: «{text}»") from exc


def weekday_sat(d: jdatetime.date) -> int:
    """Weekday index with Saturday == 0 ... Friday == 6."""
    return d.weekday()


def week_range(d: jdatetime.date) -> tuple[jdatetime.date, jdatetime.date]:
    """(Saturday, Friday) bounding the Jalali week containing *d*."""
    start = d - datetime.timedelta(days=weekday_sat(d))
    return start, start + datetime.timedelta(days=6)


def month_grid(year: int, month: int) -> list[list[int | None]]:
    """A list of weeks (Saturday-first), each a list of 7 day-numbers or None."""
    first = jdatetime.date(year, month, 1)
    lead = weekday_sat(first)
    days: list[int | None] = [None] * lead + list(range(1, month_length(year, month) + 1))
    while len(days) % 7:
        days.append(None)
    return [days[i : i + 7] for i in range(0, len(days), 7)]


_NUM_WORD = re.compile(r"(\d+)")


def parse_relative(text: str, today: jdatetime.date | None = None) -> jdatetime.date | None:
    """Resolve a Persian relative-date expression to a concrete Jalali date.

    Returns ``None`` when *text* is not a recognised relative expression.
    """
    if today is None:
        today = jdatetime.date.today()
    s = normalize_digits(text.strip()).replace("‌", " ")
    s = re.sub(r"\s+", " ", s).strip()

    simple = {
        "امروز": 0,
        "فردا": 1,
        "پس فردا": 2,
        "پسفردا": 2,
        "دیروز": -1,
        "پریروز": -2,
    }
    if s in simple:
        return today + datetime.timedelta(days=simple[s])

    m = _NUM_WORD.search(s)
    if m and ("روز" in s):
        n = int(m.group(1))
        if any(w in s for w in ("دیگر", "بعد", "آینده")):
            return today + datetime.timedelta(days=n)
        if any(w in s for w in ("پیش", "قبل", "گذشته")):
            return today - datetime.timedelta(days=n)

    if s in ("پایان هفته", "آخر هفته"):
        return week_range(today)[1]
    if s in ("اول هفته", "ابتدای هفته", "شروع هفته"):
        return week_range(today)[0]

    if s in ("هفته بعد", "هفته آینده", "هفته دیگر"):
        return today + datetime.timedelta(days=7)
    if s in ("هفته پیش", "هفته قبل", "هفته گذشته"):
        return today - datetime.timedelta(days=7)

    if s in ("اول ماه بعد", "اول ماه آینده", "ابتدای ماه بعد"):
        y, mo = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        return jdatetime.date(y, mo, 1)
    if s in ("اول ماه", "ابتدای ماه"):
        return jdatetime.date(today.year, today.month, 1)
    if s in ("آخر ماه", "پایان ماه"):
        return jdatetime.date(today.year, today.month, month_length(today.year, today.month))

    for idx, name in enumerate(WEEKDAY_NAMES):
        key = name.replace("‌", " ")
        if key in s:
            cur = weekday_sat(today)
            if any(w in s for w in ("بعد", "آینده", "دیگر")):
                delta = (idx - cur) % 7
                delta = delta or 7
                return today + datetime.timedelta(days=delta)
            if any(w in s for w in ("پیش", "قبل", "گذشته")):
                delta = (cur - idx) % 7
                delta = delta or 7
                return today - datetime.timedelta(days=delta)
            if "این" in s:
                return week_range(today)[0] + datetime.timedelta(days=idx)
    return None


def resolve(
    text: str, today: jdatetime.date | None = None
) -> jdatetime.date | jdatetime.datetime:
    """Resolve *text* (relative expression or absolute date) to a Jalali object."""
    rel = parse_relative(text, today=today)
    if rel is not None:
        return rel
    return parse_jalali(text)


def to_gregorian_string(text: str, today: jdatetime.date | None = None) -> str:
    """Convert Jalali input to a Taskwarrior-friendly Gregorian string.

    Date-only input yields ``YYYY-MM-DD``; input with a time yields
    ``YYYY-MM-DDTHH:MM:SS`` (interpreted by ``task`` in local time).
    """
    obj = resolve(text, today=today)
    if isinstance(obj, jdatetime.datetime):
        g = obj.togregorian()
        return g.strftime("%Y-%m-%dT%H:%M:%S")
    g = obj.togregorian()
    return g.strftime("%Y-%m-%d")


_TW_TS_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$")


def from_taskwarrior(value: str, fmt: str = "short") -> str:
    """Format a Taskwarrior UTC timestamp (``YYYYMMDDTHHMMSSZ``) as a Jalali string.

    *fmt* is ``"short"`` (``۱۴۰۳-۰۷-۱۰``) or ``"long"``
    (``سه‌شنبه ۱۰ مهر ۱۴۰۳``).  Empty input returns an empty string.
    """
    if not value:
        return ""
    m = _TW_TS_RE.match(value.strip())
    if not m:
        raise JalaliError(f"برچسب زمانی Taskwarrior نامعتبر است: «{value}»")
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    utc = datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)
    local = utc.astimezone(LOCAL_TZ)
    if fmt == "gregorian":
        return local.strftime("%Y-%m-%d")
    jd = jdatetime.date.fromgregorian(date=local.date())
    if fmt == "long":
        wd = WEEKDAY_NAMES[weekday_sat(jd)]
        return to_persian_digits(f"{wd} {jd.day} {MONTH_NAMES[jd.month - 1]} {jd.year}")
    return to_persian_digits(f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}")


_LOCAL_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$"
)


def from_local(value: str, fmt: str = "short") -> str:
    """Format an already-*local* timestamp as a Jalali string.

    Accepts ``YYYY-MM-DD`` and ``YYYY-MM-DD HH:MM[:SS]`` — the form Taskwarrior's
    ``information`` report and modification log emit (rendered in local time).
    ``fmt``: ``short`` (``۱۴۰۳-۰۷-۱۰``), ``long`` (``سه‌شنبه ۱۰ مهر ۱۴۰۳``),
    ``datetime`` (``۱۴۰۳-۰۷-۱۰ ۱۴:۳۰``), ``time`` (``۱۴:۳۰``),
    ``gregorian`` (``2024-10-01``).  Empty / unparseable input returns it unchanged.
    """
    if not value:
        return ""
    m = _LOCAL_TS_RE.match(value.strip())
    if not m:
        return value
    y, mo, d, hh, mm, _ss = m.groups()
    jd = jdatetime.date.fromgregorian(date=datetime.date(int(y), int(mo), int(d)))
    hm = f"{hh}:{mm}" if hh is not None else ""
    if fmt == "gregorian":
        return f"{y}-{mo}-{d}"
    if fmt == "time":
        return to_persian_digits(hm)
    if fmt == "long":
        wd = WEEKDAY_NAMES[weekday_sat(jd)]
        base = f"{wd} {jd.day} {MONTH_NAMES[jd.month - 1]} {jd.year}"
        return to_persian_digits(f"{base} {hm}".strip())
    base = f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"
    if fmt == "datetime" and hm:
        base = f"{base} {hm}"
    return to_persian_digits(base)
