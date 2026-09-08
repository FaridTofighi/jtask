"""The board engine — schema, drop-action vocabulary, built-in presets.

A *board* is a named, ordered list of *columns*. A column is a raw Taskwarrior
filter string (the exact form the M3 ``FilterBuilder`` produces) plus an
optional *drop action* from the bounded vocabulary below. There is no board-
specific engine code — the GTD preset is just the first entry in
:data:`BUILTIN_BOARDS`.

Persistence is via :class:`jtask_gui.settings.Settings` (``boards/user`` +
``boards/order``), the same path as saved filters and templates.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

from .i18n import t

# --- drop-action vocabulary ------------------------------------------
# Every shape compiles to one `task <uuid> modify …` (or a lifecycle verb).
DROP_TYPES = ("none", "tags", "attr", "uda", "verb")
ATTR_FIELDS = ("project", "priority")
VERBS = ("start", "stop", "done", "reopen")

# --- column accent colours ------------------------------------------
# A curated set of *theme roles* (not raw hex): each already resolves per
# theme and passes the WCAG-AA contrast gate in `tests/gui/test_theme.py`, so a
# colour chosen in dark mode stays correct in light mode. Rendered as a thin
# strip on the column header (`QFrame#BoardColAccent[accent="<role>"]`).
COLUMN_ACCENT_ROLES = (
    "primary", "accent", "success", "due_soon", "overdue", "blocked", "waiting",
)


def normalize_color(value: object) -> str | None:
    """A known accent role, or ``None`` (no accent) for anything else."""
    return value if value in COLUMN_ACCENT_ROLES else None


# --- per-column card sort ------------------------------------------
# Taskwarrior's own convention: trailing "-" = descending, "+" = ascending.
# The keys ("urgency" / "entry") come straight off the shaped `task export`
# rows the board already loads — the same `urgency` the main table shows and
# the same `entry` creation date — no separate computation, no extra `task`
# call. `sort=` in a `.taskrc` report never reaches `task export`, so the board
# does its own sort in Python.
SORT_ORDERS = ("urgency-", "urgency+", "entry-", "entry+")
DEFAULT_SORT = "urgency-"          # highest urgency first
SORT_LABEL_KEYS = {
    "urgency-": "board.sort.urgency_desc",
    "urgency+": "board.sort.urgency_asc",
    "entry-": "board.sort.newest",
    "entry+": "board.sort.oldest",
}


def normalize_sort(value: object) -> str:
    """A known sort order, or the default for anything else."""
    return value if value in SORT_ORDERS else DEFAULT_SORT


def sort_rows(rows: list[dict], order: str) -> list[dict]:
    """Order shaped ``reports.report_list`` rows for a board column.

    Reuses each row's own ``urgency`` (the exact value the main task table
    shows) and ``entry_gregorian`` (the task's creation date) — no separate
    calculation. Stable: equal keys keep their ``task export`` order.
    """
    order = normalize_sort(order)
    if order.startswith("urgency"):
        def key(r: dict) -> float:
            try:
                return float(r.get("urgency") or 0)
            except (TypeError, ValueError):
                return 0.0
    else:  # "entry" — the ISO YYYYMMDDTHHMMSSZ string sorts chronologically
        def key(r: dict) -> str:
            return r.get("entry_gregorian") or r.get("entry") or ""

    return sorted(rows, key=key, reverse=order.endswith("-"))


def drop_label(drop: dict) -> str:
    """A short human description of a drop action, for the column subtitle."""
    dt = drop.get("type", "none")
    if dt == "none":
        return t("board.drop.none")
    if dt == "tags":
        parts = [f"+{x}" for x in drop.get("add", [])] + [
            f"-{x}" for x in drop.get("remove", [])
        ]
        return " ".join(parts) or t("board.drop.none")
    if dt == "attr":
        return f"{drop.get('field', '')}:{drop.get('value', '')}"
    if dt == "uda":
        return f"{drop.get('name', '')}:{drop.get('value', '')}"
    if dt == "verb":
        return t(f"board.verb.{drop.get('verb', '')}")
    return ""


def compile_drop(drop: dict) -> tuple[str, list[str]] | None:
    """``(verb, mods)`` for ``taskwarrior.command([uuid], verb, mods)``, or
    ``None`` when the column takes no drop."""
    dt = drop.get("type", "none")
    if dt == "none":
        return None
    if dt == "tags":
        mods = [f"+{x}" for x in drop.get("add", []) if x] + [
            f"-{x}" for x in drop.get("remove", []) if x
        ]
        return ("modify", mods) if mods else None
    if dt == "attr":
        return ("modify", [f"{drop['field']}:{drop.get('value', '')}"])
    if dt == "uda":
        return ("modify", [f"{drop['name']}:{drop.get('value', '')}"])
    if dt == "verb":
        v = drop.get("verb")
        if v == "reopen":
            return ("modify", ["status:pending"])
        if v in VERBS:
            return (v, [])
    return None


# --- schema --------------------------------------------------------

@dataclass
class Column:
    title: str
    filter: str = ""
    drop: dict = field(default_factory=lambda: {"type": "none"})
    color: str | None = None          # an accent role, or None for the neutral look
    sort: str = DEFAULT_SORT          # card order within the column

    def to_dict(self) -> dict:
        d = {"title": self.title, "filter": self.filter, "drop": dict(self.drop)}
        if self.color:                # omitted when unset — existing boards stay identical
            d["color"] = self.color
        if self.sort != DEFAULT_SORT:  # ditto — the new default needs no migration
            d["sort"] = self.sort
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Column:
        return cls(str(d.get("title", "")), str(d.get("filter", "")),
                   dict(d.get("drop") or {"type": "none"}),
                   normalize_color(d.get("color")),
                   normalize_sort(d.get("sort")))


@dataclass
class Board:
    name: str
    columns: list[Column] = field(default_factory=list)
    builtin: bool = False

    def to_dict(self) -> dict:
        return {"name": self.name, "columns": [c.to_dict() for c in self.columns]}

    @classmethod
    def from_dict(cls, d: dict, *, builtin: bool = False) -> Board:
        return cls(
            str(d.get("name", "")),
            [Column.from_dict(c) for c in (d.get("columns") or [])],
            builtin=builtin,
        )


class BoardValidationError(ValueError):
    pass


def validate(d: dict) -> None:
    """Raise :class:`BoardValidationError` if *d* is not a usable board dict."""
    if not isinstance(d, dict) or not str(d.get("name", "")).strip():
        raise BoardValidationError(t("board.err.name"))
    cols = d.get("columns")
    if not isinstance(cols, list) or not cols:
        raise BoardValidationError(t("board.err.columns"))
    for c in cols:
        if not isinstance(c, dict) or not str(c.get("title", "")).strip():
            raise BoardValidationError(t("board.err.col_title"))
        drop = c.get("drop") or {"type": "none"}
        if drop.get("type", "none") not in DROP_TYPES:
            raise BoardValidationError(t("board.err.drop_type"))
        color = c.get("color")
        if color is not None and color not in COLUMN_ACCENT_ROLES:
            raise BoardValidationError(t("board.err.color"))
        sort = c.get("sort")
        if sort is not None and sort not in SORT_ORDERS:
            raise BoardValidationError(t("board.err.sort"))


def to_json(board: Board) -> str:
    return json.dumps(board.to_dict(), ensure_ascii=False, indent=2)


def from_json(text: str) -> Board:
    d = json.loads(text)
    validate(d)
    return Board.from_dict(d)


# --- built-in presets --------------------------------------------
# Column titles are i18n keys resolved at read time (see BoardStore.get).

# Preset colours are just defaults — a "New ▾ → from preset" copy carries them
# into an editable board where the swatch picker can override them.
_GTD = {
    "name": "board.preset.gtd",
    "columns": [
        {"title": "board.gtd.inbox",
         "filter": "status:pending -PROJECT -TAGGED",
         "drop": {"type": "none"}},
        {"title": "board.gtd.next",
         "filter": "status:pending -BLOCKED -waiting -someday ( +PROJECT or +TAGGED )",
         "drop": {"type": "tags", "add": [], "remove": ["waiting", "someday"]},
         "color": "primary"},
        {"title": "board.gtd.waiting",
         "filter": "status:pending +waiting",
         "drop": {"type": "tags", "add": ["waiting"], "remove": ["someday"]},
         "color": "waiting"},
        {"title": "board.gtd.someday",
         "filter": "status:pending +someday",
         "drop": {"type": "tags", "add": ["someday"], "remove": ["waiting"]},
         "color": "accent"},
        {"title": "board.gtd.done",
         "filter": "status:completed",
         "drop": {"type": "verb", "verb": "done"},
         "color": "success"},
    ],
}

_STATUS = {
    "name": "board.preset.status",
    "columns": [
        {"title": "kanban.col.todo", "filter": "status:pending -ACTIVE",
         "drop": {"type": "verb", "verb": "stop"}},
        {"title": "kanban.col.doing", "filter": "status:pending +ACTIVE",
         "drop": {"type": "verb", "verb": "start"}, "color": "primary"},
        {"title": "kanban.col.done", "filter": "status:completed",
         "drop": {"type": "verb", "verb": "done"}, "color": "success"},
    ],
}

BUILTIN_BOARDS: dict[str, dict] = {"gtd": _GTD, "status": _STATUS}


def builtin_board(key: str) -> Board | None:
    raw = BUILTIN_BOARDS.get(key)
    if raw is None:
        return None
    b = Board.from_dict(copy.deepcopy(raw), builtin=True)
    b.name = t(b.name)
    for col in b.columns:
        col.title = t(col.title)
    return b


def all_builtins() -> list[Board]:
    return [builtin_board(k) for k in BUILTIN_BOARDS]


def is_review_capable(board: Board | None) -> bool:
    """Whether *board* offers the GTD weekly-review pass. Review steps are a
    single global list (:data:`jtask.gtd.REVIEW_STEPS`) with no per-board
    configuration, so only the built-in GTD preset qualifies."""
    gtd = builtin_board("gtd")
    return bool(board and board.builtin and gtd is not None and board.name == gtd.name)
