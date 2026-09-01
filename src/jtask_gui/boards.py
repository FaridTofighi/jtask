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

    def to_dict(self) -> dict:
        return {"title": self.title, "filter": self.filter, "drop": dict(self.drop)}

    @classmethod
    def from_dict(cls, d: dict) -> Column:
        return cls(str(d.get("title", "")), str(d.get("filter", "")),
                   dict(d.get("drop") or {"type": "none"}))


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


def to_json(board: Board) -> str:
    return json.dumps(board.to_dict(), ensure_ascii=False, indent=2)


def from_json(text: str) -> Board:
    d = json.loads(text)
    validate(d)
    return Board.from_dict(d)


# --- built-in presets --------------------------------------------
# Column titles are i18n keys resolved at read time (see BoardStore.get).

_GTD = {
    "name": "board.preset.gtd",
    "columns": [
        {"title": "board.gtd.inbox",
         "filter": "status:pending -PROJECT -TAGGED",
         "drop": {"type": "none"}},
        {"title": "board.gtd.next",
         "filter": "status:pending -BLOCKED -waiting -someday ( +PROJECT or +TAGGED )",
         "drop": {"type": "tags", "add": [], "remove": ["waiting", "someday"]}},
        {"title": "board.gtd.waiting",
         "filter": "status:pending +waiting",
         "drop": {"type": "tags", "add": ["waiting"], "remove": ["someday"]}},
        {"title": "board.gtd.someday",
         "filter": "status:pending +someday",
         "drop": {"type": "tags", "add": ["someday"], "remove": ["waiting"]}},
        {"title": "board.gtd.done",
         "filter": "status:completed",
         "drop": {"type": "verb", "verb": "done"}},
    ],
}

_STATUS = {
    "name": "board.preset.status",
    "columns": [
        {"title": "kanban.col.todo", "filter": "status:pending -ACTIVE",
         "drop": {"type": "verb", "verb": "stop"}},
        {"title": "kanban.col.doing", "filter": "status:pending +ACTIVE",
         "drop": {"type": "verb", "verb": "start"}},
        {"title": "kanban.col.done", "filter": "status:completed",
         "drop": {"type": "verb", "verb": "done"}},
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
