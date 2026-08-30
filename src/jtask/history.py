"""Parse ``task <id> information`` — the only first-party source of per-field
task history and retroactive time-tracking sessions.

Taskwarrior renders this report in **local time**.  The ``Date | Modification``
section lists one timestamp per transaction (blank on continuation lines) with
its property changes in chronological order.  Every :class:`ChangeEntry` keeps
the exact line Taskwarrior emitted (``raw``) — nothing is fabricated.

Time-tracking sessions are reconstructed from the ``Start set to '<ts>'`` /
``Start deleted (duration: <d>)`` pairs in that same log (see
``docs/taskwarrior-feature-matrix.md`` → Timesheet).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

__all__ = [
    "ChangeEntry",
    "Session",
    "InformationReport",
    "parse_information",
    "parse_duration",
]

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$")
_TS_FMT = "%Y-%m-%d %H:%M:%S"

_CHANGED = re.compile(r"^(.+?) changed from '(.*)' to '(.*)'\.?$")
_SET = re.compile(r"^(.+?) set to '(.*)'\.?$")
_DELETED_DUR = re.compile(r"^(.+?) deleted \(duration: (.*?)\)\.?$")
_DELETED = re.compile(r"^(.+?) deleted\.?$")
_ANN_ADD = re.compile(r"^Annotation of '(.*)' added\.?$")
_ANN_DEL = re.compile(r"^Annotation of '(.*)' deleted\.?$")
_TAG_ADD = re.compile(r"^Tag '(.*)' added\.?$")
_TAG_DEL = re.compile(r"^Tag '(.*)' deleted\.?$")

_DUR_RE = re.compile(
    r"(?:(\d+)\s*days?,\s*)?(\d+):(\d{2}):(\d{2})"
)


def parse_duration(text: str) -> dt.timedelta:
    """``'2 days, 1:00:00'`` / ``'0:30:00'`` → :class:`datetime.timedelta`."""
    m = _DUR_RE.search(text.strip())
    if not m:
        return dt.timedelta(0)
    days, hh, mm, ss = m.groups()
    return dt.timedelta(
        days=int(days or 0), hours=int(hh), minutes=int(mm), seconds=int(ss)
    )


def _parse_ts(text: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(text.strip(), _TS_FMT)
    except ValueError:
        return None


@dataclass(frozen=True)
class ChangeEntry:
    when: dt.datetime
    kind: str  # set | changed | deleted | annotation_added/deleted | tag_added/deleted | other
    attr: str  # "Priority", "Due", … or "" for tag/annotation
    old: str | None
    new: str | None
    raw: str
    duration: dt.timedelta | None = None


@dataclass(frozen=True)
class Session:
    start: dt.datetime
    end: dt.datetime | None
    duration: dt.timedelta

    @property
    def running(self) -> bool:
        return self.end is None


@dataclass
class InformationReport:
    attributes: dict[str, str] = field(default_factory=dict)
    annotations: list[tuple[dt.datetime | None, str]] = field(default_factory=list)
    changes: list[ChangeEntry] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)


def _classify(when: dt.datetime, line: str) -> ChangeEntry:
    for rx, kind in ((_ANN_ADD, "annotation_added"), (_ANN_DEL, "annotation_deleted")):
        m = rx.match(line)
        if m:
            return ChangeEntry(when, kind, "", None, m.group(1), line)
    for rx, kind in ((_TAG_ADD, "tag_added"), (_TAG_DEL, "tag_deleted")):
        m = rx.match(line)
        if m:
            new = m.group(1) if kind == "tag_added" else None
            old = m.group(1) if kind == "tag_deleted" else None
            return ChangeEntry(when, kind, "", old, new, line)
    m = _CHANGED.match(line)
    if m:
        return ChangeEntry(when, "changed", m.group(1), m.group(2), m.group(3), line)
    m = _DELETED_DUR.match(line)
    if m:
        return ChangeEntry(
            when, "deleted", m.group(1), None, None, line, parse_duration(m.group(2))
        )
    m = _SET.match(line)
    if m:
        return ChangeEntry(when, "set", m.group(1), None, m.group(2), line)
    m = _DELETED.match(line)
    if m:
        return ChangeEntry(when, "deleted", m.group(1), None, None, line)
    return ChangeEntry(when, "other", "", None, None, line)


def _sessions(changes: list[ChangeEntry]) -> list[Session]:
    sessions: list[Session] = []
    open_start: dt.datetime | None = None
    for ch in changes:
        if ch.attr == "Start" and ch.kind == "set":
            open_start = _parse_ts(ch.new or "") or ch.when
        elif ch.attr == "Start" and ch.kind == "deleted":
            if open_start is None:
                continue
            dur = ch.duration or (ch.when - open_start)
            sessions.append(Session(open_start, open_start + dur, dur))
            open_start = None
    if open_start is not None:
        sessions.append(Session(open_start, None, dt.timedelta(0)))
    return sessions


def parse_information(text: str) -> InformationReport:
    rep = InformationReport()
    lines = text.splitlines()

    # ---- attribute table: "Name  Value" until a blank line ----
    in_attrs = False
    for line in lines:
        if re.match(r"^Name\s+Value\s*$", line):
            in_attrs = True
            continue
        if in_attrs:
            if not line.strip() or set(line.strip()) <= {"-", " "}:
                if not line.strip():
                    break
                continue
            m = re.match(r"^(\S.*?\S)\s{2,}(.*)$", line)
            if m and not line.startswith(" "):
                rep.attributes[m.group(1).strip()] = m.group(2).strip()

    # ---- modification log ----
    in_log = False
    current: dt.datetime | None = None
    for line in lines:
        if re.match(r"^Date\s+Modification\s*$", line):
            in_log = True
            continue
        if not in_log:
            continue
        if not line.strip():
            if rep.changes:  # blank line after the log ends it
                break
            continue
        if set(line.strip()) <= {"-", " "}:
            continue
        m = _TS.match(line)
        if m:
            current = _parse_ts(m.group(1))
            body = m.group(2).strip()
        else:
            body = line.strip()
        if current is None or not body:
            continue
        rep.changes.append(_classify(current, body))

    rep.sessions = _sessions(rep.changes)
    return rep
