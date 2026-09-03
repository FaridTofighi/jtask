"""GTD helpers: project summary and the guided weekly review."""

from __future__ import annotations

import datetime

import jdatetime
from rich.table import Table
from rich.text import Text

from . import jalali, taskwarrior
from .render.tables import message_panel, task_table
from .rtl import num, rtl

__all__ = [
    "project_summary", "weekly_review", "stuck_project_names", "stuck_projects",
]


def _dep_list(task: dict) -> list[str]:
    deps = task.get("depends") or []
    if isinstance(deps, str):
        return [d for d in deps.split(",") if d]
    return list(deps)


def stuck_project_names(tasks: list[dict]) -> set[str]:
    """Projects with pending work but **no next action you could pick up now** —
    nothing pending that isn't blocked, ``+waiting`` or ``+someday``. This is the
    GTD board's *Next Actions* definition; the sidebar badge and the wizard both
    use it, computed from an already-fetched task list so it costs no extra
    ``task export``.
    """
    pending = [t for t in tasks if t.get("status") == "pending"]
    pending_uuids = {t.get("uuid") for t in pending}
    with_project: set[str] = set()
    has_next: set[str] = set()
    for t in pending:
        proj = t.get("project")
        if not proj:
            continue
        with_project.add(proj)
        tags = t.get("tags") or []
        if "waiting" in tags or "someday" in tags:
            continue
        if any(d in pending_uuids for d in _dep_list(t)):   # blocked
            continue
        has_next.add(proj)
    return with_project - has_next


def stuck_projects() -> list[str]:
    """Sorted names of the stuck projects (does its own ``task export``)."""
    return sorted(stuck_project_names(taskwarrior.export(["status:pending"])))


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
    # A project is "stuck" when it has pending work but nothing you could pick
    # up now (not blocked / +waiting / +someday) — the GTD board's Next-Actions
    # rule, shared with the GUI sidebar badge and the review wizard.
    tasks = taskwarrior.export(["status:pending"])
    return [
        {"description": f"پروژهٔ «{proj}» گام بعدی مشخص ندارد",
         "project": proj, "status": "pending"}
        for proj in sorted(stuck_project_names(tasks))
    ]


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
