"""In-terminal charts for task data (plotext + a couple of custom Rich grids).

All six chart types share the date pipeline (Jalali axis labels via
:mod:`jtask.jalali`), the theme palette, and Persian titles through
:func:`jtask.rtl.rtl`.  Insufficient data yields a Persian panel, never a crash.
"""

from __future__ import annotations

import datetime
from collections import Counter, defaultdict

import jdatetime
import plotext as plt

from .. import jalali, rewrite, taskwarrior
from ..rtl import num, rtl
from .tables import message_panel

__all__ = ["run_chart", "CHART_TYPES"]

CHART_TYPES = ("burndown", "projects", "status", "heatmap", "timeline", "velocity")

_BLOCKS = " ░▒▓█"


def _hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    try:
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def _parse_tw(ts: str | None) -> datetime.datetime | None:
    if not ts:
        return None
    m = jalali._TW_TS_RE.match(ts)
    if not m:
        return None
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    return datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)


def _to_jdate(dt: datetime.datetime) -> jdatetime.date:
    local = dt.astimezone(jalali.LOCAL_TZ)
    return jdatetime.date.fromgregorian(date=local.date())


def _end_jdate(task: dict) -> jdatetime.date | None:
    dt = _parse_tw(task.get("end"))
    return _to_jdate(dt) if dt else None


def _export_all(filter_args: list[str]) -> list[dict]:
    """Tasks matching *filter_args*, including completed ones (merged by uuid)."""
    seen: dict[str, dict] = {}
    for extra in ([], ["status:completed"]):
        for t in taskwarrior.export([*extra, *filter_args]):
            key = t.get("uuid") or str(t.get("id"))
            seen[key] = t
    return list(seen.values())


def _plt_theme(theme) -> str:
    return "dark" if theme.name == "شب" else "clear"


def _no_data(rt, msg: str = "داده کافی برای رسم نمودار وجود ندارد.") -> int:
    rt.out(message_panel(msg, rt.theme))
    return 0


# --------------------------------------------------------------------------

def run_chart(rt, args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        rt.console.print(
            rtl("انواع نمودار: " + "، ".join(CHART_TYPES))
            + "\n"
            + rtl("مثال:  jtask chart burndown project:Website")
        )
        return 0
    ctype = args[0]
    rest = args[1:]
    opts = {a for a in rest if a.startswith("--")}
    filter_args = rewrite.rewrite_args(
        [a for a in rest if not a.startswith("--")], date_udas=rt.date_udas
    )
    if ctype not in CHART_TYPES:
        rt.error(f"نمودار «{ctype}» ناشناخته است. انواع: {'، '.join(CHART_TYPES)}")
        return 2

    dispatch = {
        "burndown": _burndown,
        "projects": _by_project,
        "status": _by_status,
        "heatmap": _heatmap,
        "timeline": _timeline,
        "velocity": _velocity,
    }
    return dispatch[ctype](rt, filter_args, opts)


# --------------------------------------------------------------------------

def _burndown(rt, filter_args, opts) -> int:
    tasks = _export_all(filter_args)
    if not tasks:
        return _no_data(rt)
    days = 30
    for o in opts:
        if o.startswith("--days="):
            days = max(5, int(o.split("=")[1]))
    today = datetime.datetime.now(datetime.timezone.utc)
    span = [today.date() - datetime.timedelta(days=days - 1 - i) for i in range(days)]

    entries = [(_parse_tw(t.get("entry")), _parse_tw(t.get("end")), t.get("status")) for t in tasks]
    open_counts, done_counts = [], []
    for d in span:
        opn = sum(
            1
            for e, end, _ in entries
            if e and e.date() <= d and (end is None or end.date() > d)
        )
        done = sum(1 for _, end, _ in entries if end and end.date() <= d)
        open_counts.append(opn)
        done_counts.append(done)

    if not any(open_counts) and not any(done_counts):
        return _no_data(rt)

    labels, positions = [], []
    step = max(1, days // 6)
    for i, d in enumerate(span):
        if i % step == 0:
            jd = jdatetime.date.fromgregorian(date=d)
            labels.append(rtl(f"{jalali.MONTH_NAMES[jd.month - 1][:3]} {jd.day}"))
            positions.append(i)

    plt.clear_figure()
    plt.theme(_plt_theme(rt.theme))
    plt.plot(range(days), open_counts, label=rtl("باز"),
             color=_hex_rgb(rt.theme.color("waiting")))
    plt.plot(range(days), done_counts, label=rtl("انجام‌شده"),
             color=_hex_rgb(rt.theme.color("completed")))
    plt.xticks(positions, labels)
    plt.title(rtl("نمودار سوختن (Burndown)"))
    plt.plotsize(min(100, rt.console.width - 2), 20)
    plt.show()
    return 0


def _by_project(rt, filter_args, opts) -> int:
    tasks = taskwarrior.export(["status:pending", *filter_args])
    if not tasks:
        return _no_data(rt)
    counts = Counter(t.get("project") or "بدون پروژه" for t in tasks)
    items = counts.most_common()
    labels = [rtl(k) for k, _ in items]
    values = [v for _, v in items]
    plt.clear_figure()
    plt.theme(_plt_theme(rt.theme))
    plt.bar(labels, values, color=_hex_rgb(rt.theme.color("primary")), orientation="horizontal")
    plt.title(rtl("کارهای باز به تفکیک پروژه"))
    plt.plotsize(min(100, rt.console.width - 2), max(8, len(items) * 2 + 3))
    plt.show()
    return 0


def _by_status(rt, filter_args, opts) -> int:
    if "--priority" in opts:
        tasks = taskwarrior.export(["status:pending", *filter_args])
        if not tasks:
            return _no_data(rt)
        fa = {"H": "زیاد", "M": "متوسط", "L": "کم", "": "بدون اولویت"}
        counts = Counter(fa[t.get("priority", "")] for t in tasks)
        order = ["زیاد", "متوسط", "کم", "بدون اولویت"]
        title = "کارهای باز به تفکیک اولویت"
    else:
        counts = Counter()
        status_labels = (
            ("pending", "در جریان"),
            ("waiting", "در انتظار"),
            ("completed", "انجام‌شده"),
        )
        for st, key in status_labels:
            counts[key] = len(taskwarrior.export([f"status:{st}", *filter_args]))
        order = ["در جریان", "در انتظار", "انجام‌شده"]
        title = "کارها به تفکیک وضعیت"
    labels = [rtl(k) for k in order if counts.get(k)]
    values = [counts[k] for k in order if counts.get(k)]
    if not values:
        return _no_data(rt)
    palette = [_hex_rgb(c) for c in rt.theme.chart_palette]
    plt.clear_figure()
    plt.theme(_plt_theme(rt.theme))
    plt.bar(labels, values, color=palette)
    plt.title(rtl(title))
    plt.plotsize(min(90, rt.console.width - 2), 16)
    plt.show()
    return 0


def _velocity(rt, filter_args, opts) -> int:
    weeks = 8
    for o in opts:
        if o.startswith("--weeks="):
            weeks = max(2, int(o.split("=")[1]))
    done_dates = [d for d in (_end_jdate(t) for t in _export_all(filter_args)) if d]
    if not done_dates:
        return _no_data(rt, "هنوز کاری انجام نشده است.")
    today_j = jdatetime.date.today()
    this_week_start = jalali.week_range(today_j)[0]
    buckets = []
    labels = []
    for w in range(weeks - 1, -1, -1):
        start = this_week_start - datetime.timedelta(days=7 * w)
        end = start + datetime.timedelta(days=7)
        n = sum(1 for d in done_dates if start <= d < end)
        buckets.append(n)
        labels.append(rtl(f"{jalali.MONTH_NAMES[start.month - 1][:3]} {start.day}"))
    if not any(buckets):
        return _no_data(rt, "هنوز کاری انجام نشده است.")
    plt.clear_figure()
    plt.theme(_plt_theme(rt.theme))
    plt.bar(labels, buckets, color=_hex_rgb(rt.theme.color("completed")))
    plt.title(rtl(f"سرعت هفتگی — {weeks} هفتهٔ اخیر"))
    plt.plotsize(min(100, rt.console.width - 2), 16)
    plt.show()
    return 0


def _heatmap(rt, filter_args, opts) -> int:
    weeks = 13
    for o in opts:
        if o.startswith("--weeks="):
            weeks = max(4, int(o.split("=")[1]))
    per_day: Counter = Counter()
    for t in _export_all(filter_args):
        d = _end_jdate(t)
        if d:
            per_day[d] += 1
    if not per_day:
        return _no_data(rt, "هنوز کاری انجام نشده است.")

    today_j = jdatetime.date.today()
    week_start = jalali.week_range(today_j)[0] - datetime.timedelta(days=7 * (weeks - 1))
    grid = [[0] * weeks for _ in range(7)]
    for wi in range(weeks):
        for di in range(7):
            day = week_start + datetime.timedelta(days=7 * wi + di)
            grid[di][wi] = per_day.get(day, 0)

    hi = max(max(row) for row in grid) or 1
    from rich.text import Text

    color = rt.theme.color("completed")
    out = Text()
    for di in range(7):
        out.append(rtl(jalali.WEEKDAY_NAMES_SHORT[di]) + " ", style=rt.theme.color("muted"))
        for wi in range(weeks):
            n = grid[di][wi]
            ch = _BLOCKS[min(4, round(n / hi * 4))] if n else "·"
            out.append(ch + ch, style=color if n else rt.theme.color("muted"))
        out.append("\n")
    total = sum(per_day.values())
    out.append(rtl(f"مجموع انجام‌شده در بازه: {num(total)}"), style=rt.theme.color("primary"))
    from rich.panel import Panel

    rt.out(Panel(
        out,
        title=rtl("نقشهٔ حرارتی انجام کارها"),
        border_style=rt.theme.color("muted"),
        expand=False,
    ))
    return 0


def _timeline(rt, filter_args, opts) -> int:
    tasks = _export_all(filter_args)
    spans = []
    for t in tasks:
        start = _parse_tw(t.get("entry"))
        finish = _parse_tw(t.get("due")) or _parse_tw(t.get("end"))
        if not start:
            continue
        if not finish:
            finish = datetime.datetime.now(datetime.timezone.utc)
        if finish < start:
            finish = start
        spans.append((t.get("description", ""), start, finish, t.get("status")))
    if not spans:
        return _no_data(rt)

    lo = min(s for _, s, _, _ in spans)
    hi = max(e for _, _, e, _ in spans)
    total = max((hi - lo).days, 1)
    width = max(20, min(60, rt.console.width - 30))

    from rich.table import Table

    tbl = Table(box=rt.theme.box, border_style=rt.theme.color("muted"), expand=False,
                header_style=f"bold {rt.theme.color('header')}")
    tbl.add_column(rtl("بازهٔ زمانی"), justify="right")
    tbl.add_column(rtl("کار"), justify="right")
    for desc, s, e, status in sorted(spans, key=lambda x: x[1]):
        off = round((s - lo).days / total * width)
        length = max(1, round((e - s).days / total * width))
        bar = " " * off + "█" * length
        col = rt.theme.color("completed") if status == "completed" else rt.theme.color("primary")
        from rich.text import Text

        tbl.add_row(Text(bar, style=col), rtl(desc))
    lo_j = jdatetime.date.fromgregorian(date=lo.astimezone(jalali.LOCAL_TZ).date())
    hi_j = jdatetime.date.fromgregorian(date=hi.astimezone(jalali.LOCAL_TZ).date())
    tbl.title = rtl(
        f"خط زمانی: {num(lo_j.strftime('%Y-%m-%d'))} تا {num(hi_j.strftime('%Y-%m-%d'))}"
    )
    tbl.title_style = rt.theme.color("primary")
    rt.out(tbl)
    _ = defaultdict
    return 0
