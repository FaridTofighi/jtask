"""Calendar-system abstraction (§ i4).

The UI can render and accept dates in **Jalali** or **Gregorian**, independently
of the UI language.  Taskwarrior's storage stays Gregorian/UTC either way — a
``CalendarSystem`` only decides how a date is shown and how typed input is
turned back into a Taskwarrior string.

``JalaliCalendarSystem`` wraps the existing :mod:`jtask.jalali`.
``GregorianCalendarSystem`` is a near-passthrough (storage is already Gregorian).

Week-start follows the *system*: Saturday for Jalali (as always); for Gregorian
the locale-appropriate default, honouring Taskwarrior's ``rc.weekstart`` when set.

Changing the calendar requires an app restart (like the language), so a single
process-wide :func:`active` instance is fine.
"""

from __future__ import annotations

import datetime as _dt
from abc import ABC, abstractmethod

import jdatetime

from jtask import jalali

from . import i18n

# --- Jalali display names (Latin transliteration for en mode) -----------
# Canonical table from docs/i18n-glossary.md §7. Used everywhere a Jalali date
# is rendered while the UI language is English.
JALALI_MONTHS_LATIN = [
    "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
    "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand",
]
JALALI_WEEKDAYS_LATIN = [
    "Shanbeh", "Yekshanbeh", "Doshanbeh", "Seshanbeh",
    "Chaharshanbeh", "Panjshanbeh", "Jomeh",
]
JALALI_WEEKDAYS_LATIN_SHORT = ["Sh", "Ye", "Do", "Se", "Ch", "Pa", "Jo"]

_GREGORIAN_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_GREGORIAN_WEEKDAYS_SHORT_MON = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_TW_TS = jalali._TW_TS_RE  # ^YYYYMMDDTHHMMSSZ$
_LOCAL_TS = jalali._LOCAL_TS_RE


class CalendarSystem(ABC):
    id: str

    # -- calendar shape ------------------------------------------------
    @abstractmethod
    def today(self) -> object:  # a jdatetime.date or datetime.date
        ...

    @abstractmethod
    def month_names(self) -> list[str]: ...

    @abstractmethod
    def weekday_names_short(self) -> list[str]: ...

    @abstractmethod
    def week_start_pyweekday(self) -> int:
        """Python ``date.weekday()`` value of the first column (Mon=0 … Sun=6)."""

    @abstractmethod
    def month_grid(self, year: int, month: int) -> list[list[int | None]]: ...

    @abstractmethod
    def label_ym(self, year: int, month: int) -> str: ...

    @abstractmethod
    def is_today(self, year: int, month: int, day: int) -> bool: ...

    @abstractmethod
    def to_gregorian_date(self, year: int, month: int, day: int) -> _dt.date: ...

    @abstractmethod
    def from_gregorian_date(self, d: _dt.date) -> tuple[int, int, int]:
        """(year, month, day) in this system for a Gregorian date."""

    # -- display -----------------------------------------------------
    @abstractmethod
    def format_utc(self, tw_ts: str, style: str = "short") -> str:
        """A stored Taskwarrior UTC timestamp → a display string."""

    @abstractmethod
    def format_local(self, local_ts: str, style: str = "short") -> str:
        """A local ``YYYY-MM-DD[ HH:MM[:SS]]`` string → a display string."""

    def week_bounds(self, ref: _dt.date | None = None) -> tuple[_dt.date, _dt.date]:
        """(first day, last day) Gregorian dates of the week containing *ref*
        (today by default), using this system's week-start convention."""
        ref = ref or _dt.date.today()
        offset = (ref.weekday() - self.week_start_pyweekday()) % 7
        start = ref - _dt.timedelta(days=offset)
        return start, start + _dt.timedelta(days=6)

    # -- input -----------------------------------------------------
    @abstractmethod
    def to_taskwarrior(self, text: str) -> str:
        """User-typed date/relative expression → a Taskwarrior-ready string
        (``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS``), or the text unchanged when
        it is not recognisably a date this system parses (Taskwarrior then
        interprets it)."""


# ======================================================================
# Jalali
# ======================================================================
class JalaliCalendarSystem(CalendarSystem):
    id = "jalali"

    def _latin(self) -> bool:
        return i18n.lang() == "en"

    def today(self):
        return jdatetime.date.today()

    def month_names(self) -> list[str]:
        return JALALI_MONTHS_LATIN if self._latin() else list(jalali.MONTH_NAMES)

    def weekday_names_short(self) -> list[str]:
        return (
            JALALI_WEEKDAYS_LATIN_SHORT
            if self._latin()
            else list(jalali.WEEKDAY_NAMES_SHORT)
        )

    def week_start_pyweekday(self) -> int:
        return 5  # Saturday

    def month_grid(self, year: int, month: int) -> list[list[int | None]]:
        return jalali.month_grid(year, month)

    def label_ym(self, year: int, month: int) -> str:
        name = self.month_names()[month - 1]
        text = f"{name} {year}"
        if self._latin():
            return text
        from .fmt import digits
        return digits(text)

    def is_today(self, year: int, month: int, day: int) -> bool:
        t = jdatetime.date.today()
        return (t.year, t.month, t.day) == (year, month, day)

    def to_gregorian_date(self, year: int, month: int, day: int) -> _dt.date:
        return jdatetime.date(year, month, day).togregorian()

    def from_gregorian_date(self, d: _dt.date) -> tuple[int, int, int]:
        j = jdatetime.date.fromgregorian(date=d)
        return j.year, j.month, j.day

    def _jalali_ymd_local(self, tw_ts: str) -> tuple[int, int, int, str] | None:
        m = _TW_TS.match((tw_ts or "").strip())
        if not m:
            return None
        y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
        local = _dt.datetime(y, mo, d, hh, mm, ss, tzinfo=_dt.timezone.utc).astimezone(
            jalali.LOCAL_TZ
        )
        j = jdatetime.date.fromgregorian(date=local.date())
        return j.year, j.month, j.day, f"{local.hour:02d}:{local.minute:02d}"

    def format_utc(self, tw_ts: str, style: str = "short") -> str:
        if self._latin() and style == "long":
            parts = self._jalali_ymd_local(tw_ts)
            return self._latin_long(*parts[:3]) if parts else (tw_ts or "")
        return jalali.from_taskwarrior(tw_ts, fmt=style)

    def format_local(self, local_ts: str, style: str = "short") -> str:
        if self._latin() and style == "long":
            m = _LOCAL_TS.match((local_ts or "").strip())
            if not m:
                return local_ts or ""
            y, mo, d, hh, mi, _s = m.groups()
            j = jdatetime.date.fromgregorian(date=_dt.date(int(y), int(mo), int(d)))
            hm = f"{hh}:{mi}" if hh is not None else ""
            return self._latin_long(j.year, j.month, j.day, hm)
        return jalali.from_local(local_ts, fmt=style)

    @staticmethod
    def _latin_long(jy: int, jm: int, jd_: int, hm: str = "") -> str:
        j = jdatetime.date(jy, jm, jd_)
        wd = JALALI_WEEKDAYS_LATIN[jalali.weekday_sat(j)]
        mn = JALALI_MONTHS_LATIN[jm - 1]
        return f"{wd} {jd_} {mn} {jy}{(' ' + hm) if hm else ''}".strip()

    def to_taskwarrior(self, text: str) -> str:
        try:
            return jalali.to_gregorian_string(text)
        except jalali.JalaliError:
            return text


# ======================================================================
# Gregorian
# ======================================================================
class GregorianCalendarSystem(CalendarSystem):
    id = "gregorian"

    def __init__(self, week_start_pyweekday: int = 0) -> None:
        self._ws = week_start_pyweekday  # 0 = Monday, 6 = Sunday

    # ---- shape ----
    def today(self):
        return _dt.date.today()

    def month_names(self) -> list[str]:
        return list(_GREGORIAN_MONTHS)

    def weekday_names_short(self) -> list[str]:
        base = _GREGORIAN_WEEKDAYS_SHORT_MON  # Mon-first
        return base[self._ws:] + base[:self._ws]

    def week_start_pyweekday(self) -> int:
        return self._ws

    def month_grid(self, year: int, month: int) -> list[list[int | None]]:
        first = _dt.date(year, month, 1)
        lead = (first.weekday() - self._ws) % 7
        length = _month_length_greg(year, month)
        days: list[int | None] = [None] * lead + list(range(1, length + 1))
        while len(days) % 7:
            days.append(None)
        return [days[i:i + 7] for i in range(0, len(days), 7)]

    def label_ym(self, year: int, month: int) -> str:
        from .fmt import digits

        return digits(f"{_GREGORIAN_MONTHS[month - 1]} {year}")

    def is_today(self, year: int, month: int, day: int) -> bool:
        t = _dt.date.today()
        return (t.year, t.month, t.day) == (year, month, day)

    def to_gregorian_date(self, year: int, month: int, day: int) -> _dt.date:
        return _dt.date(year, month, day)

    def from_gregorian_date(self, d: _dt.date) -> tuple[int, int, int]:
        return d.year, d.month, d.day

    # ---- display ----
    def format_utc(self, tw_ts: str, style: str = "short") -> str:
        m = _TW_TS.match((tw_ts or "").strip())
        if not m:
            return tw_ts or ""
        y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
        local = _dt.datetime(y, mo, d, hh, mm, ss, tzinfo=_dt.timezone.utc).astimezone(
            jalali.LOCAL_TZ
        )
        return self._render(local.date(), f"{local.hour:02d}:{local.minute:02d}", style)

    def format_local(self, local_ts: str, style: str = "short") -> str:
        m = _LOCAL_TS.match((local_ts or "").strip())
        if not m:
            return local_ts or ""
        y, mo, d, hh, mi, _s = m.groups()
        hm = f"{hh}:{mi}" if hh is not None else ""
        return self._render(_dt.date(int(y), int(mo), int(d)), hm, style)

    def _render(self, d: _dt.date, hm: str, style: str) -> str:
        from .fmt import digits

        if style == "time":
            return digits(hm)
        if style == "gregorian":
            return d.isoformat()
        if style == "long":
            wd = _dt.date(d.year, d.month, d.day).strftime("%A")
            base = f"{wd} {d.day} {_GREGORIAN_MONTHS[d.month - 1]} {d.year}"
            return digits(f"{base} {hm}".strip())
        base = d.isoformat()
        if style == "datetime" and hm:
            base = f"{base} {hm}"
        return digits(base)

    # ---- input ----
    def to_taskwarrior(self, text: str) -> str:
        s = jalali.normalize_digits(text.strip())
        if not s:
            return ""
        # an absolute Y-M-D / Y.M.D / Y/M/D date, optionally with a time
        m = jalali._DATE_RE.match(s)
        if m:
            y, mo, d, hh, mi, ss = m.groups()
            try:
                _dt.date(int(y), int(mo), int(d))
            except ValueError:
                return text
            base = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            if hh is None:
                return base
            return f"{base}T{int(hh):02d}:{int(mi):02d}:{int(ss or 0):02d}"
        # anything else (today / tomorrow / eom / a weekday name / date math):
        # let Taskwarrior's own parser handle it
        return text


def _month_length_greg(year: int, month: int) -> int:
    if month == 12:
        nxt = _dt.date(year + 1, 1, 1)
    else:
        nxt = _dt.date(year, month + 1, 1)
    return (nxt - _dt.date(year, month, 1)).days


# ======================================================================
# active instance
# ======================================================================
_active: CalendarSystem | None = None


def _read_weekstart() -> int:
    """Gregorian week-start from Taskwarrior's ``rc.weekstart`` (default Monday)."""
    try:
        from jtask import taskwarrior

        val = "".join(taskwarrior._lines(["_get", "rc.weekstart"])).strip().lower()
    except Exception:  # noqa: BLE001
        val = ""
    return {"sunday": 6, "monday": 0}.get(val, 0)


def active() -> CalendarSystem:
    global _active
    if _active is None:
        from .settings import Settings

        cal = Settings().calendar
        _active = (
            GregorianCalendarSystem(_read_weekstart())
            if cal == "gregorian"
            else JalaliCalendarSystem()
        )
    return _active


def set_calendar(system_id: str) -> None:
    """Force the active calendar (tests / an explicit switch)."""
    global _active
    _active = (
        GregorianCalendarSystem(_read_weekstart())
        if system_id == "gregorian"
        else JalaliCalendarSystem()
    )
