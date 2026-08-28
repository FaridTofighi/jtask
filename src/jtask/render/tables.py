"""Rich-based right-to-left task tables and panels.

Rich renders columns left-to-right, so to make a table read naturally for a
Persian reader we append columns in reverse (logical-first ends up rightmost)
and right-align every cell.  All Persian text goes through :func:`jtask.rtl.rtl`.
"""

from __future__ import annotations

import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import jalali
from ..rtl import num, rtl
from ..themes import Theme

__all__ = ["task_table", "message_panel", "make_console"]

_HEADERS = {
    "id": "شناسه",
    "uuid": "شناسهٔ یکتا",
    "description": "شرح",
    "project": "پروژه",
    "due": "سررسید",
    "scheduled": "زمان‌بندی",
    "wait": "انتظار",
    "until": "مهلت",
    "tags": "برچسب‌ها",
    "urgency": "فوریت",
    "status": "وضعیت",
    "priority": "اولویت",
    "start": "شروع",
}

_STATUS_FA = {
    "pending": "در جریان",
    "completed": "انجام‌شده",
    "waiting": "در انتظار",
    "deleted": "حذف‌شده",
    "recurring": "تکرارشونده",
}

_PRIORITY_FA = {"H": "زیاد", "M": "متوسط", "L": "کم"}

_DEFAULT_COLUMNS = ["id", "description", "project", "due", "tags", "priority", "urgency"]


def make_console() -> Console:
    return Console()


def _due_style(task: dict[str, Any], theme: Theme) -> str | None:
    raw = task.get("due_gregorian") or task.get("_due_raw")
    if not raw:
        return None
    try:
        m = jalali._TW_TS_RE.match(raw)
        if not m:
            return None
        y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
        due = datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    if task.get("status") in {"completed", "deleted"}:
        return None
    if due < now:
        return theme.color("overdue")
    if due - now <= datetime.timedelta(days=3):
        return theme.color("due_soon")
    return None


def _cell(key: str, task: dict[str, Any], theme: Theme) -> Text:
    value = task.get(key)
    style = None

    if key == "id":
        text = num(value, is_id=True) if value else "—"
    elif key == "urgency":
        text = num(f"{float(value):.1f}") if value is not None else ""
    elif key == "tags":
        tags = value or []
        text = " ".join(f"#{t}" for t in tags)
    elif key == "status":
        sval = str(value or "")
        text = rtl(_STATUS_FA.get(sval, sval))
        if value == "waiting":
            style = theme.color("waiting")
        elif value == "completed":
            style = theme.color("completed")
    elif key == "priority":
        pval = str(value or "")
        text = rtl(_PRIORITY_FA.get(pval, pval))
    elif key in {"due", "scheduled", "wait", "until", "start"}:
        text = num(value) if value else ""
        if key == "due":
            style = _due_style(task, theme)
    elif key == "description":
        text = rtl(str(value or ""))
        if task.get("status") == "completed":
            style = theme.color("completed")
    else:
        text = rtl(str(value)) if value else ""

    return Text(text, style=style or "")


def task_table(
    tasks: list[dict[str, Any]],
    theme: Theme,
    *,
    columns: list[str] | None = None,
    title: str | None = None,
) -> Table:
    """Build an RTL Rich table for *tasks*."""
    cols = columns or _DEFAULT_COLUMNS
    present = [c for c in cols if any(c in t for t in tasks)] or cols

    table = Table(
        box=theme.box,
        border_style=theme.color("muted"),
        header_style=f"bold {theme.color('header')}",
        title=rtl(title) if title else None,
        title_style=theme.color("primary"),
        expand=False,
    )
    # reverse so the logical first column sits on the right
    for key in reversed(present):
        table.add_column(rtl(_HEADERS.get(key, key)), justify="right", no_wrap=(key == "id"))

    for task in tasks:
        cells = [_cell(key, task, theme) for key in reversed(present)]
        table.add_row(*cells)
    return table


def message_panel(text: str, theme: Theme, *, style: str = "primary") -> Panel:
    """A single-line Persian message in a themed panel (for errors / empty states)."""
    return Panel(
        Text(rtl(text), justify="right"),
        border_style=theme.color(style if style in theme.colors else "primary"),
        expand=False,
    )
