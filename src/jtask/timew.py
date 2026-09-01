"""The only subprocess wrapper for the ``timew`` (Timewarrior) binary.

Timewarrior is **optional** — always gate on :func:`available` first. When it is
installed jtask can source the Timesheet view from real tracked intervals
instead of reconstructing sessions from Taskwarrior's modification log
(``jtask.timesheet``). Intervals are grouped by their Timewarrior tags (jtask
does not assume any particular ``on-modify`` hook mapping back to task uuids).
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from dataclasses import dataclass, field

_TS = "%Y%m%dT%H%M%SZ"


def available() -> bool:
    return shutil.which("timew") is not None


def _run(args: list[str]) -> str:
    proc = subprocess.run(
        ["timew", *args], capture_output=True, text=True, check=False
    )
    return proc.stdout if proc.returncode == 0 else ""


def _parse_ts(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, _TS).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


@dataclass
class Interval:
    start: dt.datetime
    end: dt.datetime | None
    tags: list[str]

    @property
    def duration(self) -> dt.timedelta:
        end = self.end or dt.datetime.now(dt.timezone.utc)
        return end - self.start


@dataclass
class Summary:
    total: dt.timedelta = dt.timedelta()
    by_tag: dict[str, dt.timedelta] = field(default_factory=dict)
    by_day: dict[dt.date, dt.timedelta] = field(default_factory=dict)
    intervals: list[Interval] = field(default_factory=list)


def intervals(since: dt.date, until: dt.date) -> list[Interval]:
    """Tracked intervals overlapping ``[since, until]`` (inclusive days)."""
    if not available():
        return []
    lo = since.strftime("%Y-%m-%d")
    hi = (until + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    raw = _run(["export", lo, "-", hi])
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[Interval] = []
    for row in data:
        start = _parse_ts(row.get("start"))
        if start is None:
            continue
        out.append(Interval(start, _parse_ts(row.get("end")), list(row.get("tags") or [])))
    return out


def summary(since: dt.date, until: dt.date, *, local_tz: dt.tzinfo | None = None) -> Summary:
    tz = local_tz or dt.datetime.now().astimezone().tzinfo
    s = Summary()
    for iv in intervals(since, until):
        d = iv.duration
        s.total += d
        day = iv.start.astimezone(tz).date()
        s.by_day[day] = s.by_day.get(day, dt.timedelta()) + d
        for tag in iv.tags or ["—"]:
            s.by_tag[tag] = s.by_tag.get(tag, dt.timedelta()) + d
        s.intervals.append(iv)
    return s
