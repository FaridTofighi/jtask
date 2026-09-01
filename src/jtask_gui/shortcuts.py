"""The single registry of every keyboard shortcut in jtask-gui.

Both the ``?`` cheat-sheet overlay and the Settings "Keyboard shortcuts"
section render from this list, and ``tests/gui/test_shortcuts_registry.py``
asserts every live ``QShortcut`` / action shortcut is listed here and that no
key sequence is bound twice.

Bindings are deliberately layout-independent — modifier combos or non-letter
keys (arrows, Enter, ``?``) — never bare vim-style letters, which a Persian
keyboard layout would not produce (the physical J key types «ب»).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Shortcut:
    keys: str        # portable QKeySequence string
    desc_key: str    # i18n key for the description
    cat_key: str     # i18n key for the category heading


SHORTCUTS: list[Shortcut] = [
    # -- create / capture --
    Shortcut("Ctrl+N", "sc.quick_add", "sc.cat.create"),
    Shortcut("Ctrl+Shift+N", "sc.add_full", "sc.cat.create"),
    # -- navigate --
    Shortcut("Ctrl+K", "sc.command_palette", "sc.cat.navigate"),
    Shortcut("Ctrl+F", "sc.focus_filter", "sc.cat.navigate"),
    Shortcut("Ctrl+B", "sc.board", "sc.cat.navigate"),
    Shortcut("Ctrl+1", "sc.view_today", "sc.cat.navigate"),
    Shortcut("Ctrl+2", "sc.view_next", "sc.cat.navigate"),
    Shortcut("Ctrl+3", "sc.view_completed", "sc.cat.navigate"),
    Shortcut("Up", "sc.row_up", "sc.cat.navigate"),
    Shortcut("Down", "sc.row_down", "sc.cat.navigate"),
    # -- the selected task --
    Shortcut("Return", "sc.open_detail", "sc.cat.task"),
    Shortcut("Ctrl+E", "sc.open_detail", "sc.cat.task"),
    Shortcut("Ctrl+D", "sc.mark_done", "sc.cat.task"),
    Shortcut("Ctrl+S", "sc.timer_start", "sc.cat.task"),
    Shortcut("Ctrl+Shift+S", "sc.timer_stop", "sc.cat.task"),
    Shortcut("Del", "sc.delete", "sc.cat.task"),
    Shortcut("Ctrl+.", "sc.toggle_star", "sc.cat.task"),
    # -- everywhere --
    Shortcut("Ctrl+Z", "sc.undo", "sc.cat.general"),
    Shortcut("?", "sc.cheat_sheet", "sc.cat.general"),
    Shortcut("Esc", "sc.close_panel", "sc.cat.general"),
]

# The category display order for the cheat sheet.
CATEGORY_ORDER = [
    "sc.cat.create",
    "sc.cat.navigate",
    "sc.cat.task",
    "sc.cat.general",
]


def by_category() -> list[tuple[str, list[Shortcut]]]:
    groups: dict[str, list[Shortcut]] = {}
    for sc in SHORTCUTS:
        groups.setdefault(sc.cat_key, []).append(sc)
    return [(c, groups[c]) for c in CATEGORY_ORDER if c in groups]
