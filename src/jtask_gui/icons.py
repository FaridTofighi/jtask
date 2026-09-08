"""Theme-aware icon registry (qtawesome).

Call :func:`set_theme` once at startup and on every theme switch; widgets fetch
icons by semantic name via :func:`icon` and get one tinted for the active theme.
Glyphs in ``_MIRRORED`` are flipped 180° **only** when the application layout
direction is RTL (fa); in LTR (en) they render un-mirrored.
"""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .theme import palette


def _is_rtl() -> bool:
    app = QApplication.instance()
    return app is not None and app.layoutDirection() == Qt.LayoutDirection.RightToLeft

# semantic name -> qtawesome id
_MAP = {
    # sidebar / views
    "today": "mdi.calendar-today",
    "week": "mdi.calendar-week",
    "overdue": "mdi.alert-circle-outline",
    "next": "mdi.flash-outline",
    "waiting": "mdi.timer-sand",
    "blocked": "mdi.lock-outline",
    "completed": "mdi.check-circle-outline",
    "projects": "mdi.folder-outline",
    "project": "mdi.folder-outline",
    "tags": "mdi.tag-multiple-outline",
    "tag": "mdi.tag-outline",
    "contexts": "mdi.layers-outline",
    "context": "mdi.circle-medium",
    "reports": "mdi.chart-box-outline",
    # toolbar
    "undo": "mdi.undo-variant",
    "settings": "mdi.cog-outline",
    "console": "mdi.console-line",
    "data": "mdi.database-outline",
    "manage": "mdi.tune-variant",
    "tools": "mdi.wrench-outline",
    "more": "mdi.dots-horizontal",
    "export": "mdi.database-export-outline",
    "import": "mdi.database-import-outline",
    "sync": "mdi.sync",
    "theme_dark": "mdi.weather-night",
    "theme_light": "mdi.white-balance-sunny",
    "group": "mdi.format-list-group",
    "view": "mdi.view-agenda-outline",
    "filter": "mdi.filter-variant",
    "search": "mdi.magnify",
    "star": "mdi.star",
    "star_outline": "mdi.star-outline",
    "folder": "mdi.folder-outline",
    "board": "mdi.view-column-outline",
    "review": "mdi.clipboard-check-outline",
    "triage": "mdi.filter-menu-outline",
    "sort": "mdi.sort",
    "add": "mdi.plus-circle-outline",
    "clear": "mdi.close-circle-outline",
    "calendar": "mdi.calendar-blank-outline",
    # row indicators
    "annotation": "mdi.note-text-outline",
    "recur": "mdi.repeat-variant",
    "depends": "mdi.link-variant",
    "start": "mdi.play-circle-outline",
    "stop": "mdi.stop-circle-outline",
    "delete": "mdi.trash-can-outline",
    # status-control transitions
    "done": "mdi.check-circle-outline",
    "reopen": "mdi.backup-restore",
    "unwait": "mdi.timer-off-outline",
    "pin": "mdi.pin",
    "pin_off": "mdi.pin-off-outline",
}

_MIRRORED = {"undo"}  # glyphs whose direction must flip for RTL

_theme = "dark"
_cache: dict[tuple[str, str], QIcon] = {}


def set_theme(name: str) -> None:
    global _theme
    if name != _theme:
        _theme = name
        _cache.clear()


def _colour(role: str) -> str:
    pal = palette(_theme)
    return pal.get(role, pal["text"])


def icon(name: str, role: str = "text") -> QIcon:
    """Return the icon for *name*, tinted with palette colour *role*."""
    key = (name, role)
    if key in _cache:
        return _cache[key]
    qid = _MAP.get(name, "mdi.help-circle-outline")
    opts: dict = {"color": _colour(role)}
    if name in _MIRRORED and _is_rtl():
        opts["rotated"] = 180
    try:
        result = qta.icon(qid, **opts)
    except Exception:  # noqa: BLE001 - never let a missing glyph crash the UI
        result = QIcon()
    _cache[key] = result
    return result
