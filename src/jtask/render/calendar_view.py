"""Jalali month / week calendar view of scheduled and due tasks."""

from __future__ import annotations

import datetime

import jdatetime
from rich.table import Table
from rich.text import Text

from .. import jalali, taskwarrior
from ..rtl import num, rtl
from .tables import message_panel

__all__ = ["show_calendar"]


def _parse_month_arg(arg: str | None) -> tuple[int, int]:
    today = jdatetime.date.today()
    if not arg:
        return today.year, today.month
    raw = jalali.normalize_digits(arg)
    parts = raw.replace("/", "-").replace(".", "-").split("-")
    try:
        if len(parts) == 1:
            return today.year, int(parts[0])
        return int(parts[0]), int(parts[1])
    except ValueError:
        return today.year, today.month


def _tasks_by_day() -> tuple[dict, dict]:
    due: dict = {}
    sched: dict = {}
    for t in taskwarrior.export(["status:pending"]):
        for field, bucket in (("due", due), ("scheduled", sched)):
            m = jalali._TW_TS_RE.match(t.get(field, "") or "")
            if not m:
                continue
            y, mo, d, hh, mi, ss = (int(x) for x in m.groups())
            dt = datetime.datetime(y, mo, d, hh, mi, ss, tzinfo=datetime.timezone.utc)
            jd = jdatetime.date.fromgregorian(date=dt.astimezone(jalali.LOCAL_TZ).date())
            bucket.setdefault((jd.year, jd.month, jd.day), []).append(t)
    return due, sched


def show_calendar(rt, args: list[str]) -> None:
    week_mode = "--week" in args
    positional = [a for a in args if not a.startswith("--")]
    year, month = _parse_month_arg(positional[0] if positional else None)
    if not 1 <= month <= 12:
        rt.out(message_panel("ماه نامعتبر است.", rt.theme))
        return

    due, sched = _tasks_by_day()
    today = jdatetime.date.today()

    table = Table(
        box=rt.theme.box,
        border_style=rt.theme.color("muted"),
        header_style=f"bold {rt.theme.color('header')}",
        title=rtl(f"{jalali.MONTH_NAMES[month - 1]} {num(year)}"),
        title_style=rt.theme.color("primary"),
        expand=False,
    )
    for name in reversed(jalali.WEEKDAY_NAMES):
        table.add_column(rtl(name), justify="right", width=12)

    if week_mode:
        start = jalali.week_range(today)[0]
        weeks = [[
            (start + datetime.timedelta(days=i)).day
            if (start + datetime.timedelta(days=i)).month == month else None
            for i in range(7)
        ]]
        grid_year_month = [(start + datetime.timedelta(days=i)) for i in range(7)]
    else:
        weeks = jalali.month_grid(year, month)
        grid_year_month = None

    for week in weeks:
        cells = []
        for di, day in enumerate(reversed(week)):
            if day is None:
                cells.append(Text(""))
                continue
            if grid_year_month is not None:
                real = grid_year_month[6 - di]
                y, m, d = real.year, real.month, real.day
            else:
                y, m, d = year, month, day
            key = (y, m, d)
            marks = ""
            if key in due:
                marks += " ●" + num(len(due[key]))
            if key in sched:
                marks += " ○" + num(len(sched[key]))
            label = num(d) + marks
            style = ""
            if (y, m, d) == (today.year, today.month, today.day):
                style = f"bold {rt.theme.color('accent')}"
            elif key in due:
                style = rt.theme.color("overdue" if any(
                    _is_overdue(t) for t in due[key]) else "due_soon")
            cells.append(Text(label, style=style))
        table.add_row(*cells)

    rt.out(table)
    rt.console.print(rtl("● سررسید   ○ زمان‌بندی"), style=rt.theme.color("muted"))


def _is_overdue(task: dict) -> bool:
    m = jalali._TW_TS_RE.match(task.get("due", "") or "")
    if not m:
        return False
    y, mo, d, hh, mi, ss = (int(x) for x in m.groups())
    dt = datetime.datetime(y, mo, d, hh, mi, ss, tzinfo=datetime.timezone.utc)
    return dt < datetime.datetime.now(datetime.timezone.utc)
