"""Framework-agnostic report data shaping for the GUI (and anything else).

Every function here computes its result from ``task export`` JSON only — it
never parses Taskwarrior's ASCII report output.  Bucketing uses **Jalali**
period boundaries (weeks start Saturday) so downstream axes line up with the
rest of jtask.  Output date fields are Jalali strings with the raw Gregorian
kept alongside as ``<field>_gregorian``.

The GUI layer imports these; it must not shell out to ``task`` or do Jalali
math itself.
"""

from __future__ import annotations

import datetime
import re
from collections import Counter, defaultdict
from typing import Any

import jdatetime

from . import jalali, taskwarrior
from .rewrite import rewrite_export

__all__ = [
    "VIRTUAL_TAGS",
    "shape_task_list",
    "shape_projects",
    "shape_tags",
    "shape_summary",
    "shape_history",
    "shape_burndown",
    "shape_calendar",
    "report_list",
    "report_next",
    "report_waiting",
    "report_blocked",
    "report_blocking",
    "report_ready",
    "report_active",
    "report_completed",
    "report_projects",
    "report_tags",
    "report_summary",
    "report_history",
    "report_ghistory",
    "report_burndown",
    "report_calendar",
    "run_custom_report",
]

PERIODS = ("daily", "weekly", "monthly")

# Taskwarrior virtual tags — never shown as user tags.
VIRTUAL_TAGS = frozenset({
    "ACTIVE", "ANNOTATED", "BLOCKED", "BLOCKING", "CHILD", "COMPLETED", "DELETED",
    "DUE", "DUETODAY", "TODAY", "INSTANCE", "LATEST", "MONTH", "ORPHAN", "OVERDUE",
    "PARENT", "PENDING", "PRIORITY", "PROJECT", "QUARTER", "READY", "SCHEDULED",
    "TAGGED", "TEMPLATE", "UDA", "UNBLOCKED", "UNTIL", "WAITING", "WEEK", "YEAR",
    "YESTERDAY", "TOMORROW", "nocal", "nocolor", "nonag",
})


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _parse(ts: str | None) -> datetime.datetime | None:
    if not ts:
        return None
    m = jalali._TW_TS_RE.match(ts)
    if not m:
        return None
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    return datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)


def _jdate(dt: datetime.datetime) -> jdatetime.date:
    return jdatetime.date.fromgregorian(date=dt.astimezone(jalali.LOCAL_TZ).date())


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _is_overdue(task: dict) -> bool:
    due = _parse(task.get("due"))
    return bool(due and task.get("status") == "pending" and due < _now())


def _period_key(jd: jdatetime.date, period: str) -> tuple[Any, str]:
    """Return (sort_key, jalali_label) for the period containing *jd*."""
    if period == "monthly":
        return (jd.year, jd.month), f"{jalali.MONTH_NAMES[jd.month - 1]} {jd.year}"
    if period == "weekly":
        start = jd - datetime.timedelta(days=jalali.weekday_sat(jd))
        year_start = jdatetime.date(start.year, 1, 1).togregorian()
        week_no = (start.togregorian() - year_start).days // 7 + 1
        return (start.year, week_no), f"{start.year}-w{week_no:02d}"
    if period == "daily":
        return (jd.year, jd.month, jd.day), f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"
    raise ValueError(f"period نامعتبر است: {period!r} (daily|weekly|monthly)")


def _iter_period_starts(
    first: jdatetime.date, last: jdatetime.date, period: str
):
    """Yield jdate anchors covering [first, last] inclusive, by period."""
    if period == "daily":
        cur = first
        while cur <= last:
            yield cur
            cur += datetime.timedelta(days=1)
    elif period == "weekly":
        cur = first - datetime.timedelta(days=jalali.weekday_sat(first))
        while cur <= last:
            yield cur
            cur += datetime.timedelta(days=7)
    elif period == "monthly":
        y, m = first.year, first.month
        while (y, m) <= (last.year, last.month):
            yield jdatetime.date(y, m, 1)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    else:
        raise ValueError(f"period نامعتبر است: {period!r}")


# --------------------------------------------------------------------------
# pure shapers
# --------------------------------------------------------------------------

def shape_task_list(tasks: list[dict]) -> list[dict]:
    """Task dicts with Jalali date fields (+ ``*_gregorian``)."""
    return rewrite_export(
        tasks, fmt="short", date_udas=taskwarrior.date_uda_names(), keep_gregorian=True
    )


def shape_projects(tasks: list[dict]) -> list[dict]:
    agg: dict[str, dict] = defaultdict(
        lambda: {"open": 0, "waiting": 0, "overdue": 0, "completed": 0, "total": 0}
    )
    for t in tasks:
        proj = t.get("project")
        if not proj:
            continue
        a = agg[proj]
        a["total"] += 1
        st = t.get("status")
        if st == "completed":
            a["completed"] += 1
        elif st == "waiting":
            a["waiting"] += 1
            a["open"] += 1
        elif st == "pending":
            a["open"] += 1
        if _is_overdue(t):
            a["overdue"] += 1
    out = []
    for proj in sorted(agg):
        a = agg[proj]
        pct = round(a["completed"] / a["total"] * 100, 1) if a["total"] else 0.0
        out.append({"project": proj, **a, "pct": pct})
    return out


def shape_tags(tasks: list[dict]) -> list[dict]:
    counter: Counter = Counter()
    for t in tasks:
        for tag in t.get("tags", []) or []:
            if tag not in VIRTUAL_TAGS:
                counter[tag] += 1
    return [{"tag": tag, "count": n} for tag, n in counter.most_common()]


def shape_summary(tasks: list[dict]) -> list[dict]:
    rows = shape_projects(tasks)
    for r in rows:
        r["done"] = r["completed"]
        r["pending"] = r["open"]
    return rows


def shape_history(tasks: list[dict], *, period: str = "monthly") -> dict:
    if period not in PERIODS:
        raise ValueError(f"period نامعتبر است: {period!r}")
    added: Counter = Counter()
    completed: Counter = Counter()
    deleted: Counter = Counter()
    labels: dict[Any, str] = {}

    def bump(counter: Counter, dt: datetime.datetime) -> None:
        key, label = _period_key(_jdate(dt), period)
        counter[key] += 1
        labels[key] = label

    for t in tasks:
        entry = _parse(t.get("entry"))
        if entry:
            bump(added, entry)
        end = _parse(t.get("end"))
        if end:
            if t.get("status") == "deleted":
                bump(deleted, end)
            else:
                bump(completed, end)

    keys = sorted(set(added) | set(completed) | set(deleted))
    buckets = [
        {
            "label": labels[k],
            "added": added.get(k, 0),
            "completed": completed.get(k, 0),
            "deleted": deleted.get(k, 0),
            "net": added.get(k, 0) - completed.get(k, 0) - deleted.get(k, 0),
        }
        for k in keys
    ]
    return {"period": period, "buckets": buckets}


def shape_burndown(
    tasks: list[dict],
    *,
    period: str = "daily",
    today: jdatetime.date | None = None,
) -> dict:
    if period not in PERIODS:
        raise ValueError(f"period نامعتبر است: {period!r}")
    today = today or jdatetime.date.today()

    spans = []
    for t in tasks:
        entry = _parse(t.get("entry"))
        if not entry:
            continue
        end = _parse(t.get("end"))
        spans.append((
            _jdate(entry),
            _jdate(end) if end else None,
            t.get("status"),
            bool(t.get("start")),
        ))
    if not spans:
        return {"period": period, "buckets": []}

    first = min(s[0] for s in spans)
    buckets = []
    for anchor in _iter_period_starts(first, today, period):
        if period == "daily":
            cutoff = anchor
        elif period == "weekly":
            cutoff = anchor + datetime.timedelta(days=6)
        else:
            cutoff = jdatetime.date(
                anchor.year, anchor.month, jalali.month_length(anchor.year, anchor.month)
            )
        cutoff = min(cutoff, today)
        pending = started = done = 0
        for e, end, status, has_start in spans:
            if e > cutoff:
                continue
            if end and end <= cutoff and status == "completed":
                done += 1
            elif end and end <= cutoff and status == "deleted":
                continue
            else:
                pending += 1
                if has_start:
                    started += 1
        _, label = _period_key(anchor, period)
        buckets.append(
            {"label": label, "pending": pending - started, "started": started, "done": done}
        )
    return {"period": period, "buckets": buckets}


def _greg_month_grid(year: int, month: int, week_start: int = 0) -> list[list[int | None]]:
    """Gregorian month as weeks of 7 (``None`` pads). ``week_start``: Mon=0..Sun=6."""
    import calendar as _cal

    first = datetime.date(year, month, 1)
    lead = (first.weekday() - week_start) % 7
    length = _cal.monthrange(year, month)[1]
    cells: list[int | None] = [None] * lead + list(range(1, length + 1))
    while len(cells) % 7:
        cells.append(None)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def shape_calendar(
    tasks: list[dict], year: int, month: int, *, gregorian: bool = False,
    week_start: int = 0,
) -> dict:
    """Month grid + per-day task buckets.

    Default: *year*/*month* are Jalali, days keyed in Jalali. With
    ``gregorian=True`` they are Gregorian and days are keyed in Gregorian
    (``week_start`` then controls the leading weekday, Mon=0..Sun=6).
    """
    if gregorian:
        grid = _greg_month_grid(year, month, week_start)
    else:
        grid = jalali.month_grid(year, month)
    days: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    shaped = shape_task_list(tasks)
    for t in shaped:
        for field in ("due", "scheduled"):
            raw = t.get(f"{field}_gregorian")
            dt = _parse(raw)
            if not dt:
                continue
            local = dt.astimezone(jalali.LOCAL_TZ).date()
            if gregorian:
                ky, km, kd = local.year, local.month, local.day
            else:
                jd = jdatetime.date.fromgregorian(date=local)
                ky, km, kd = jd.year, jd.month, jd.day
            if (ky, km) == (year, month):
                days[(ky, km, kd)].append(t)
    return {"year": year, "month": month, "grid": grid, "days": dict(days)}


# --------------------------------------------------------------------------
# public API (fetch + shape)
# --------------------------------------------------------------------------

def _all(filter_args: list[str] | None) -> list[dict]:
    """Everything matching *filter_args*, pending + completed + deleted, by uuid."""
    seen: dict[str, dict] = {}
    for extra in ([], ["status:completed"], ["status:deleted"]):
        for t in taskwarrior.export([*(filter_args or []), *extra]):
            seen[t.get("uuid") or str(t.get("id"))] = t
    return list(seen.values())


def _list(report_filter: list[str], filter_args: list[str] | None) -> list[dict]:
    combined = [*report_filter, *(filter_args or [])]
    return shape_task_list(taskwarrior.export(combined))


def report_list(filter_args=None):      return _list([], filter_args)
def report_next(filter_args=None):      return _list(["status:pending"], filter_args)
def report_waiting(filter_args=None):   return _list(["+WAITING"], filter_args)
def report_blocked(filter_args=None):   return _list(["+BLOCKED"], filter_args)
def report_blocking(filter_args=None):  return _list(["+BLOCKING"], filter_args)
def report_ready(filter_args=None):     return _list(["+READY"], filter_args)
def report_active(filter_args=None):    return _list(["+ACTIVE"], filter_args)
def report_completed(filter_args=None): return _list(["status:completed"], filter_args)


def report_projects(filter_args=None) -> list[dict]:
    return shape_projects(_all(filter_args))


def report_tags(filter_args=None) -> list[dict]:
    return shape_tags(_all(filter_args))


def report_summary(filter_args=None) -> list[dict]:
    return shape_summary(_all(filter_args))


def report_history(period="monthly", filter_args=None) -> dict:
    return shape_history(_all(filter_args), period=period)


# ghistory is the same data; the GUI renders it as a chart rather than a table.
report_ghistory = report_history


def report_burndown(period="daily", filter_args=None) -> dict:
    return shape_burndown(_all(filter_args), period=period)


def report_calendar(
    year: int, month: int, filter_args=None, *, gregorian: bool = False,
    week_start: int = 0,
) -> dict:
    return shape_calendar(
        _all(filter_args), year, month, gregorian=gregorian, week_start=week_start
    )


_MODIFIER_RE = re.compile(r"\.(age|relative|countdown|remaining|indicator)$")


def run_custom_report(name: str, filter_args=None) -> dict:
    """Render a user-defined ``.taskrc`` report as ``{columns, labels, rows}``.

    Column *values* are the plain attribute (dates in Jalali); Taskwarrior's
    display modifiers (``due.relative`` etc.) are stripped to the base attribute.
    """
    specs = taskwarrior.report_specs()
    spec = specs.get(name)
    if not spec:
        raise ValueError(f"گزارش سفارشی «{name}» تعریف نشده است.")

    cols = [c.strip() for c in spec.get("columns", "").split(",") if c.strip()]
    labels = [x.strip() for x in spec.get("labels", "").split(",")] or cols
    if len(labels) < len(cols):
        labels += cols[len(labels):]

    rep_filter = [
        tok for tok in spec.get("filter", "").split()
        if not tok.startswith("limit:")
    ]
    tasks = shape_task_list(taskwarrior.export([*rep_filter, *(filter_args or [])]))

    rows = []
    for t in tasks:
        row = []
        for col in cols:
            attr = _MODIFIER_RE.sub("", col)
            value = t.get(attr, "")
            if attr == "tags" and isinstance(value, list):
                value = " ".join(value)
            elif attr == "depends" and isinstance(value, list):
                value = ",".join(str(x) for x in value)
            row.append("" if value is None else str(value))
        rows.append(row)

    return {
        "name": name,
        "description": spec.get("description", name),
        "columns": cols,
        "labels": labels[: len(cols)],
        "rows": rows,
    }
