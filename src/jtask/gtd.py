"""GTD helpers: project summary and the guided weekly review."""

from __future__ import annotations

import datetime

import jdatetime
from rich.table import Table
from rich.text import Text

from . import jalali, taskwarrior
from .render.tables import message_panel, task_table
from .rtl import num, rtl

__all__ = ["project_summary", "weekly_review"]


def _overdue(task: dict) -> bool:
    m = jalali._TW_TS_RE.match(task.get("due", "") or "")
    if not m:
        return False
    y, mo, d, hh, mi, ss = (int(x) for x in m.groups())
    return datetime.datetime(y, mo, d, hh, mi, ss, tzinfo=datetime.timezone.utc) < \
        datetime.datetime.now(datetime.timezone.utc)


def project_summary(rt, args: list[str]) -> None:
    tasks = taskwarrior.export(["status:pending", *args])
    if not tasks:
        rt.out(message_panel("هیچ کار بازی وجود ندارد.", rt.theme))
        return
    pending_uuids = {t.get("uuid") for t in tasks}
    rows: dict[str, dict[str, int]] = {}
    for t in tasks:
        proj = t.get("project") or "بدون پروژه"
        r = rows.setdefault(proj, {"open": 0, "blocked": 0, "overdue": 0})
        r["open"] += 1
        deps = t.get("depends") or []
        if isinstance(deps, str):
            deps = deps.split(",")
        if any(d in pending_uuids for d in deps):
            r["blocked"] += 1
        if _overdue(t):
            r["overdue"] += 1

    table = Table(
        box=rt.theme.box,
        border_style=rt.theme.color("muted"),
        header_style=f"bold {rt.theme.color('header')}",
        title=rtl("خلاصهٔ پروژه‌ها"),
        title_style=rt.theme.color("primary"),
        expand=False,
    )
    for head in reversed(["پروژه", "باز", "مسدود", "عقب‌افتاده"]):
        table.add_column(rtl(head), justify="right")
    for proj, r in sorted(rows.items(), key=lambda x: -x[1]["open"]):
        table.add_row(
            Text(num(r["overdue"]), style=rt.theme.color("overdue") if r["overdue"] else ""),
            Text(num(r["blocked"]), style=rt.theme.color("waiting") if r["blocked"] else ""),
            Text(num(r["open"])),
            Text(rtl(proj)),
        )
    rt.out(table)


def weekly_review(rt, args: list[str]) -> None:
    """A GTD weekly-review walkthrough, rendered as ordered sections."""
    today = jdatetime.date.today()
    ws, we = jalali.week_range(today)
    rt.console.print(
        rtl(f"مرور هفتگی — هفتهٔ {num(ws.strftime('%Y-%m-%d'))} تا {num(we.strftime('%Y-%m-%d'))}"),
        style=f"bold {rt.theme.color('primary')}",
    )

    sections = [
        ("۱) کارهای عقب‌افتاده — سررسید را به‌روز کنید یا انجام دهید",
         [t for t in taskwarrior.export(["status:pending"]) if _overdue(t)]),
        ("۲) سررسید در همین هفته",
         taskwarrior.export([
             "status:pending",
             f"due.after:{(ws - datetime.timedelta(days=1)).togregorian():%Y-%m-%d}",
             f"due.before:{(we + datetime.timedelta(days=1)).togregorian():%Y-%m-%d}",
         ])),
        ("۳) در انتظارِ دیگران (Waiting-For) — پیگیری کنید",
         taskwarrior.export(["status:pending", "+WAITING"])),
        ("۴) روزی/شاید (Someday-Maybe) — آیا وقتش رسیده؟",
         taskwarrior.export(["status:pending", "+someday"])),
        ("۵) پروژه‌های بدون گام بعدی",
         _projects_without_next_action(rt)),
        ("۶) کارهای راکد (بیش از ۳۰ روز بدون تغییر)",
         _stale(rt)),
    ]

    for title, items in sections:
        rt.console.print()
        rt.console.print(rtl(title), style=f"bold {rt.theme.color('accent')}")
        if not items:
            rt.console.print(rtl("  — موردی نیست ✔"), style=rt.theme.color("completed"))
            continue
        from .rewrite import rewrite_export

        prepared = rewrite_export(items, fmt=rt.theme.date_format, date_udas=rt.date_udas,
                                  keep_gregorian=True)
        rt.out(task_table(prepared, rt.theme))


def _projects_without_next_action(rt) -> list[dict]:
    tasks = taskwarrior.export(["status:pending"])
    by_project: dict[str, list[dict]] = {}
    for t in tasks:
        if t.get("project"):
            by_project.setdefault(t["project"], []).append(t)
    flagged = []
    for proj, items in by_project.items():
        if not any("next" in (t.get("tags") or []) for t in items):
            flagged.append({"description": f"پروژهٔ «{proj}» گام بعدی مشخص ندارد",
                            "project": proj, "status": "pending"})
    return flagged


def _stale(rt) -> list[dict]:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    out = []
    for t in taskwarrior.export(["status:pending"]):
        m = jalali._TW_TS_RE.match(t.get("modified", "") or "")
        if not m:
            continue
        y, mo, d, hh, mi, ss = (int(x) for x in m.groups())
        if datetime.datetime(y, mo, d, hh, mi, ss, tzinfo=datetime.timezone.utc) < cutoff:
            out.append(t)
    return out
