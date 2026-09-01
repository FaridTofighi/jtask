"""Column definitions for the task table."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..i18n import t


@dataclass(frozen=True)
class Column:
    key: str
    header: str
    width: int = 120
    default_visible: bool = True
    numeric: bool = False
    is_id: bool = False
    indicator: bool = False
    star: bool = False  # the ⭐ toggle column — click flips the `starred` tag
    formatter: Callable[[dict], str] | None = field(default=None, compare=False)


def _tags(task: dict) -> str:
    # keep Taskwarrior's own "+tag" / "#tag" convention — shown with the leading #.
    # "starred" is jtask's ⭐ flag — it has its own column, never a chip here.
    return "  ".join(
        f"#{x}" for x in (task.get("tags") or [])
        if not x.isupper() and x != "starred"
    )


def _priority(task: dict) -> str:
    return {
        "H": t("col.priority.h"), "M": t("col.priority.m"), "L": t("col.priority.l"),
    }.get(task.get("priority", ""), "")


def _status(task: dict) -> str:
    st = task.get("status", "")
    return {
        "pending": t("col.status.pending"), "completed": t("col.status.completed"),
        "waiting": t("col.status.waiting"), "deleted": t("col.status.deleted"),
        "recurring": t("col.status.recurring"),
    }.get(st, st)


# The three per-task markers (annotation / recurrence / dependency) share ONE
# narrow column, placed right after the description so `status` stays the last
# visible column — the model paints 1-3 tinted icons into it via DecorationRole.
INDICATOR_MARKS = ("annotations", "recur", "depends")


COLUMNS: list[Column] = [
    Column("starred", "", 30, star=True),
    Column("id", t("col.id"), 56, is_id=True),
    Column("description", t("col.description"), 320),
    Column("indicators", "", 60, indicator=True),
    Column("project", t("col.project"), 130),
    Column("tags", t("col.tags"), 130, formatter=_tags),
    Column("priority", t("col.priority"), 96, formatter=_priority),
    Column("due", t("col.due"), 116),
    Column("scheduled", t("col.scheduled"), 110, default_visible=False),
    Column("wait", t("col.wait"), 110, default_visible=False),
    Column("urgency", t("col.urgency"), 84, numeric=True),
    Column("status", t("col.status"), 96, formatter=_status),
]

INDICATOR_TOOLTIP = {
    "indicators": t("col.indicators"),
}

BY_KEY = {c.key: c for c in COLUMNS}
