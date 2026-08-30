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
    formatter: Callable[[dict], str] | None = field(default=None, compare=False)


def _tags(task: dict) -> str:
    return "  ".join(f"#{x}" for x in (task.get("tags") or []) if not x.isupper())


def _priority(task: dict) -> str:
    return {
        "H": t("col.priority.h"), "M": t("col.priority.m"), "L": t("col.priority.l"),
    }.get(task.get("priority", ""), "")


def _status(task: dict) -> str:
    return {
        "pending": t("col.status.pending"), "completed": t("col.status.completed"),
        "waiting": t("col.status.waiting"), "deleted": t("col.status.deleted"),
        "recurring": t("col.status.recurring"),
    }.get(task.get("status", ""), task.get("status", ""))


def _annot(task: dict) -> str:
    return "✎" if task.get("annotations") else ""


def _recur(task: dict) -> str:
    return "↻" if task.get("recur") else ""


def _dep(task: dict) -> str:
    return "⛓" if task.get("depends") else ""


COLUMNS: list[Column] = [
    Column("id", t("col.id"), 60, is_id=True),
    Column("description", t("col.description"), 320),
    Column("project", t("col.project"), 140),
    Column("tags", t("col.tags"), 140, formatter=_tags),
    Column("priority", t("col.priority"), 80, formatter=_priority),
    Column("due", t("col.due"), 110),
    Column("scheduled", t("col.scheduled"), 110, default_visible=False),
    Column("wait", t("col.wait"), 110, default_visible=False),
    Column("urgency", t("col.urgency"), 80, numeric=True),
    Column("status", t("col.status"), 90, formatter=_status),
    Column("annotations", "", 36, indicator=True, formatter=_annot),
    Column("recur", "", 36, indicator=True, formatter=_recur),
    Column("depends", "", 36, indicator=True, formatter=_dep),
]

INDICATOR_TOOLTIP = {
    "annotations": t("col.has_annotation"),
    "recur": t("col.is_recurring"),
    "depends": t("col.has_dependency"),
}

BY_KEY = {c.key: c for c in COLUMNS}
