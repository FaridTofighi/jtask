"""Detect and rewrite date-bearing tokens between Jalali and Gregorian.

Two directions:

* :func:`rewrite_args` — user command-line tokens (``due:1403.07.10``,
  ``due.before:فردا``, date-typed UDAs) are converted to Gregorian before the
  arguments are handed to the ``task`` binary.  Everything else passes through
  byte-for-byte, so unrecognised Taskwarrior features keep working.
* :func:`rewrite_task_dates` / :func:`rewrite_export` — the UTC timestamps in
  ``task export`` JSON are converted to Jalali strings for display.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import jdatetime

from . import jalali
from .errors import JtaskError

__all__ = [
    "DATE_ATTRS",
    "rewrite_args",
    "rewrite_task_dates",
    "rewrite_export",
]

DATE_ATTRS = frozenset(
    {"due", "scheduled", "wait", "until", "entry", "start", "end", "modified"}
)

# Attribute modifiers that carry a date value.
_DATE_MODIFIERS = frozenset(
    {"before", "after", "under", "over", "by", "is", "isnt", "not"}
)

# Sentinel values that are not dates and must be left alone.
_SENTINELS = frozenset({"", "none", "any"})

_TOKEN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z]+))?:(.*)$", re.DOTALL)
# a trailing Taskwarrior date-math expression, e.g. "+3d", "- 2 wk"
_DATEMATH_RE = re.compile(r"^(?P<date>.+?)\s*(?P<math>[+-]\s*\d+\s*[A-Za-z]+)$")
# a bare numeric date that the user probably meant as Jalali but got wrong
_BARE_NUMERIC_DATE_RE = re.compile(r"^\d{2,4}[./-]\d{1,2}[./-]\d{1,2}")


def _convert_value(value: str, today: jdatetime.date | None) -> str:
    if value.strip().lower() in _SENTINELS:
        return value

    math = ""
    date_part = value
    m = _DATEMATH_RE.match(value)
    if m:
        date_part, math = m.group("date"), m.group("math")

    try:
        greg = jalali.to_gregorian_string(date_part, today=today)
    except jalali.JalaliError as exc:
        if _BARE_NUMERIC_DATE_RE.match(jalali.normalize_digits(date_part.strip())):
            raise JtaskError(str(exc)) from exc
        # Not recognisably Jalali (an English keyword like "today", "eom",
        # "sow", a weekday name): hand it to Taskwarrior untouched.
        return value
    return greg + math


def rewrite_args(
    args: Iterable[str],
    *,
    date_udas: Iterable[str] = (),
    today: jdatetime.date | None = None,
) -> list[str]:
    """Return *args* with every date-bearing token converted to Gregorian."""
    date_attrs = DATE_ATTRS | set(date_udas)
    out: list[str] = []
    for arg in args:
        m = _TOKEN_RE.match(arg)
        if not m:
            out.append(arg)
            continue
        attr, mod, value = m.group(1), m.group(2), m.group(3)
        if attr not in date_attrs:
            out.append(arg)
            continue
        if mod is not None and mod not in _DATE_MODIFIERS:
            out.append(arg)
            continue
        converted = _convert_value(value, today)
        prefix = f"{attr}.{mod}:" if mod else f"{attr}:"
        out.append(prefix + converted)
    return out


def _display(value: str, fmt: str) -> str:
    if not value:
        return value
    return jalali.from_taskwarrior(value, fmt=fmt)


def rewrite_task_dates(
    task: dict,
    *,
    fmt: str = "short",
    date_udas: Iterable[str] = (),
    keep_gregorian: bool = False,
) -> dict:
    """Return a copy of *task* with date fields formatted as Jalali strings."""
    fields = DATE_ATTRS | set(date_udas)
    out = dict(task)
    for key in fields:
        raw = out.get(key)
        if not isinstance(raw, str) or not raw:
            continue
        if keep_gregorian:
            out[f"{key}_gregorian"] = raw
        out[key] = _display(raw, fmt)

    annotations = out.get("annotations")
    if isinstance(annotations, list):
        new_ann = []
        for ann in annotations:
            if isinstance(ann, dict) and isinstance(ann.get("entry"), str):
                ann = dict(ann)
                if keep_gregorian:
                    ann["entry_gregorian"] = ann["entry"]
                ann["entry"] = _display(ann["entry"], fmt)
            new_ann.append(ann)
        out["annotations"] = new_ann
    return out


def rewrite_export(
    tasks: Iterable[dict],
    *,
    fmt: str = "short",
    date_udas: Iterable[str] = (),
    keep_gregorian: bool = False,
) -> list[dict]:
    """Apply :func:`rewrite_task_dates` to every task in *tasks*."""
    date_udas = list(date_udas)
    return [
        rewrite_task_dates(
            t, fmt=fmt, date_udas=date_udas, keep_gregorian=keep_gregorian
        )
        for t in tasks
    ]
