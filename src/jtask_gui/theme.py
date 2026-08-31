"""Theme palettes + QSS rendering.

The palette dict is the single source of truth.  ``resources/themes/app.qss``
is a template with ``@token@`` placeholders that is filled with the active
palette, so QSS and the Python-side colour roles (table cell colours,
matplotlib figures in M2) can never drift apart.  Tests assert the token sets
stay in lockstep and that contrast ratios meet WCAG AA.
"""

from __future__ import annotations

from importlib import resources

from . import tokens

__all__ = [
    "THEMES", "DEFAULT_THEME", "palette", "render_qss", "template_text",
    "other_theme", "canonical_theme", "CHART_SERIES_ROLES",
]

# The GUI charts colour their series by semantic palette role (see
# widgets/charts/*), never from a flat list — this names that mapping so it is
# discoverable. The CLI keeps its own ``DEFAULT_CHART_PALETTE`` in
# ``jtask.themes`` for plotext, which has no palette roles to draw on.
CHART_SERIES_ROLES = ("primary", "completed", "overdue", "due_soon", "accent")

# The palette is organised as elevation layers — each surface sits visibly
# above the one behind it:  bg (window)  <  bg_alt (sidebar / recessed rail)
# <  surface (cards, rows, buttons)  <  elevated (dialogs, popovers, menus).
# Inputs use ``field`` (a recessed well) and the accent (``primary``) is used
# deliberately — selection, primary action, focus ring, active nav row.

# --- شب (dark) --------------------------------------------------------
_SHAB = {
    "bg": "#0e1014",
    "bg_alt": "#15181e",
    "surface": "#1b1f27",
    "elevated": "#232833",
    "on_danger": "#ffffff",
    "border": "#2c333f",
    "border_soft": "#20252e",
    "hover": "#20252f",
    "selection": "#273049",
    "row_line": "#242a34",
    "field": "#12151b",
    "field_focus": "#171b22",
    "text": "#e8eaef",
    "text_muted": "#8c94a3",
    "primary": "#6ea8fe",
    "primary_hi": "#8bbcff",
    "primary_fg": "#0a1a33",
    "primary_soft": "#1c2740",
    "accent": "#a78bfa",
    "focus": "#6ea8fe",
    "overdue": "#ff6b6b",
    "due_soon": "#f5c451",
    "waiting": "#7f8896",
    "completed": "#6b7280",
    "blocked": "#f472b6",
    "success": "#4ade80",
    "chip_bg": "#1e2733",
    "chip_border": "#2f3d4d",
    "chip_fg": "#a9c7e8",
}

# --- روز (light) -----------------------------------------------------
# The window base is a soft off-white so raised surfaces (cards / dialogs on
# ``surface`` = pure white) read as genuinely lifted.
_RUZ = {
    "bg": "#f4f6fa",
    "bg_alt": "#e9edf3",
    "surface": "#ffffff",
    "elevated": "#ffffff",
    "on_danger": "#ffffff",
    "border": "#dde2e9",
    "border_soft": "#e9edf2",
    "hover": "#eef1f6",
    "selection": "#e2ecff",
    "row_line": "#e7ebf1",
    "field": "#f1f4f8",
    "field_focus": "#ffffff",
    "text": "#1b2027",
    "text_muted": "#5b6472",
    "primary": "#3565d0",
    "primary_hi": "#2c56b8",
    "primary_fg": "#ffffff",
    "primary_soft": "#e6edfc",
    "accent": "#7c5cd6",
    "focus": "#3565d0",
    "overdue": "#d63b45",
    "due_soon": "#9a6b00",
    "waiting": "#6a7280",
    "completed": "#98a0ab",
    "blocked": "#c72e86",
    "success": "#1a8a42",
    "chip_bg": "#e8effb",
    "chip_border": "#cdd9ef",
    "chip_fg": "#2f5bb5",
}

# Stable theme keys (i2). Display labels come from the i18n catalog
# (``theme.dark`` / ``theme.light``). ``_LEGACY_THEME`` maps the pre-i2 Persian
# names a saved ``.conf`` might still hold — see ``Settings.theme``.
THEMES: dict[str, dict[str, str]] = {"dark": _SHAB, "light": _RUZ}
DEFAULT_THEME = "dark"
_LEGACY_THEME = {"شب": "dark", "روز": "light"}


def canonical_theme(name: str | None) -> str:
    """Map any stored value (incl. the pre-i2 Persian names) to a live key."""
    if name in THEMES:
        return name  # type: ignore[return-value]
    return _LEGACY_THEME.get(name or "", DEFAULT_THEME)

# State colours consumed by the Qt model rather than the QSS.
MODEL_COLOUR_KEYS = frozenset({"overdue", "due_soon", "waiting", "completed", "blocked"})


def palette(name: str) -> dict[str, str]:
    return dict(THEMES.get(name, _SHAB))


def other_theme(name: str) -> str:
    names = list(THEMES)
    return names[(names.index(name) + 1) % len(names)] if name in names else DEFAULT_THEME


def template_text() -> str:
    return (resources.files(__package__) / "resources/themes/app.qss").read_text(
        encoding="utf-8"
    )


def render_qss(name: str) -> str:
    qss = template_text()
    subs = {**tokens.qss_tokens(), **palette(name)}
    for key, value in subs.items():
        qss = qss.replace(f"@{key}@", value)
    return qss
