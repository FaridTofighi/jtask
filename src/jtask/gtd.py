"""GTD helpers: project summary and the guided weekly review."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass

import jdatetime
from rich.table import Table
from rich.text import Text

from . import jalali, taskwarrior
from .render.tables import message_panel, task_table
from .rtl import num, rtl

__all__ = [
    "project_summary", "weekly_review", "stuck_project_names", "stuck_projects",
    "REVIEW_STEPS", "ReviewStep", "review_step",
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


# --- weekly review: one step definition, two surfaces -------------
# `jtask review` (CLI) and the GUI Weekly Review Wizard both iterate REVIEW_STEPS
# so the sequence and the per-step data live in exactly one place.

def _week_window() -> list[str]:
    ws, we = jalali.week_range(jdatetime.date.today())
    lo = (ws - datetime.timedelta(days=1)).togregorian()
    hi = (we + datetime.timedelta(days=1)).togregorian()
    return [f"due.after:{lo:%Y-%m-%d}", f"due.before:{hi:%Y-%m-%d}"]


@dataclass(frozen=True)
class ReviewStep:
    key: str
    #: the live Taskwarrior filter this step maps to (``None`` for the
    #: aggregate-only ``stuck_projects`` step, which has no single filter).
    filter_fn: Callable[[], list[str]] | None

    def filter(self) -> list[str] | None:
        return list(self.filter_fn()) if self.filter_fn else None

    def gather(self) -> list[dict]:
        """The rows for this step — real tasks, or synthetic project rows for
        ``stuck_projects``."""
        if self.key == "stuck_projects":
            return [
                {"description": f"پروژهٔ «{p}» گام بعدی مشخص ندارد",
                 "project": p, "status": "pending"}
                for p in stuck_projects()
            ]
        return taskwarrior.export(self.filter() or [])


REVIEW_STEPS: list[ReviewStep] = [
    ReviewStep("inbox", lambda: ["status:pending", "-PROJECT", "-TAGGED"]),
    ReviewStep("overdue", lambda: ["status:pending", "+OVERDUE"]),
    ReviewStep("due_this_week", lambda: ["status:pending", *_week_window()]),
    ReviewStep("next_actions", lambda: [
        "status:pending", "-BLOCKED", "-waiting", "-someday",
        "(", "+PROJECT", "or", "+TAGGED", ")",
    ]),
    ReviewStep("waiting_for", lambda: ["status:pending", "+waiting"]),
    ReviewStep("stuck_projects", None),
    ReviewStep("someday", lambda: ["status:pending", "+someday"]),
    ReviewStep("stale", lambda: ["status:pending", "modified.before:now-30d"]),
]


def review_step(key: str) -> ReviewStep:
    return next(s for s in REVIEW_STEPS if s.key == key)


_REVIEW_TITLES = {
    "inbox": "۱) صندوق ورودی — پروژه یا برچسب بدهید، یا حذف کنید",
    "overdue": "۲) کارهای عقب‌افتاده — سررسید را به‌روز کنید یا انجام دهید",
    "due_this_week": "۳) سررسید در همین هفته",
    "next_actions": "۴) اقدامات بعدی — آیا هرکدام واقعاً گام بعدی است؟",
    "waiting_for": "۵) در انتظارِ دیگران (Waiting-For) — پیگیری کنید",
    "stuck_projects": "۶) پروژه‌های بدون گام بعدی",
    "someday": "۷) یک‌روزی/شاید (Someday-Maybe) — آیا وقتش رسیده؟",
    "stale": "۸) کارهای راکد (بیش از ۳۰ روز بدون تغییر)",
}


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

    for step in REVIEW_STEPS:
        title = _REVIEW_TITLES[step.key]
        items = step.gather()
        rt.console.print()
        rt.console.print(rtl(title), style=f"bold {rt.theme.color('accent')}")
        if not items:
            rt.console.print(rtl("  — موردی نیست ✔"), style=rt.theme.color("completed"))
            continue
        from .rewrite import rewrite_export

        prepared = rewrite_export(items, fmt=rt.theme.date_format, date_udas=rt.date_udas,
                                  keep_gregorian=True)
        rt.out(task_table(prepared, rt.theme))
