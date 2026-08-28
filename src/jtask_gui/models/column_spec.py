"""Column definitions for the task table."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    key: str
    header: str          # Persian
    width: int = 120
    default_visible: bool = True
    numeric: bool = False
    is_id: bool = False
    indicator: bool = False
    formatter: Callable[[dict], str] | None = field(default=None, compare=False)


def _tags(task: dict) -> str:
    return "  ".join(f"#{t}" for t in (task.get("tags") or []) if not t.isupper())


def _priority(task: dict) -> str:
    return {"H": "زیاد", "M": "متوسط", "L": "کم"}.get(task.get("priority", ""), "")


def _status(task: dict) -> str:
    return {
        "pending": "در جریان",
        "completed": "انجام‌شده",
        "waiting": "در انتظار",
        "deleted": "حذف‌شده",
        "recurring": "تکرارشونده",
    }.get(task.get("status", ""), task.get("status", ""))


def _annot(task: dict) -> str:
    return "✎" if task.get("annotations") else ""


def _recur(task: dict) -> str:
    return "↻" if task.get("recur") else ""


def _dep(task: dict) -> str:
    return "⛓" if task.get("depends") else ""


COLUMNS: list[Column] = [
    Column("id", "شناسه", 60, is_id=True),
    Column("description", "شرح", 320),
    Column("project", "پروژه", 140),
    Column("tags", "برچسب‌ها", 140, formatter=_tags),
    Column("priority", "اولویت", 80, formatter=_priority),
    Column("due", "سررسید", 110),
    Column("scheduled", "زمان‌بندی", 110, default_visible=False),
    Column("wait", "انتظار", 110, default_visible=False),
    Column("urgency", "فوریت", 80, numeric=True),
    Column("status", "وضعیت", 90, formatter=_status),
    Column("annotations", "ی", 34, indicator=True, formatter=_annot),
    Column("recur", "ت", 34, indicator=True, formatter=_recur),
    Column("depends", "و", 34, indicator=True, formatter=_dep),
]

BY_KEY = {c.key: c for c in COLUMNS}
