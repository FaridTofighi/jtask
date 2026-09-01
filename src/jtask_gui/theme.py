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
# Inputs use ``field`` (a recessed well). The accent is teal (the mission-d
# baseline — the mission-m blue re-tone was reverted): selection wash
# (``primary_soft`` / ``selection``), primary action, focus ring (``focus`` ==
# ``primary``), the selected-row accent bar. ``accent`` (violet) is the
# press-state flash and the 5th chart-series colour.

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
    "selection": "#294a58",
    "row_line": "#242a34",
    "row_alt": "#21262f",
    "field": "#12151b",
    "field_focus": "#171b22",
    "text": "#e8eaef",
    "text_muted": "#8c94a3",
    "primary": "#6cc7dd",
    "primary_hi": "#8ad6e8",
    "primary_fg": "#08222a",
    "primary_soft": "#18333d",
    "accent": "#b98cf0",
    "focus": "#6cc7dd",
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
# The window base is a cool grey (not near-white) so raised surfaces
# (cards / dialogs on ``surface`` = pure white) read as genuinely lifted and
# borders have something to sit against.  n2 widened these steps — the old
# ladder was ~4% luminance apart and elevation did not read.
_RUZ = {
    "bg": "#eaeef4",
    "bg_alt": "#e2e7f0",
    "surface": "#ffffff",
    "elevated": "#ffffff",
    "on_danger": "#ffffff",
    "border": "#ccd4e0",
    "border_soft": "#dde3ec",
    "hover": "#e5eaf2",
    "selection": "#b6dde8",
    "row_line": "#e6ebf2",
    "row_alt": "#f3f6fa",
    "field": "#eef1f7",
    "field_focus": "#ffffff",
    "text": "#1b2027",
    "text_muted": "#556070",
    "primary": "#0a6e8f",
    "primary_hi": "#0c82a8",
    "primary_fg": "#ffffff",
    "primary_soft": "#d3ecf3",
    "accent": "#7b41d8",
    "focus": "#0a6e8f",
    "overdue": "#d63b45",
    "due_soon": "#8a6000",
    "waiting": "#66707e",
    "completed": "#8b93a0",
    "blocked": "#c72e86",
    "success": "#1a8a42",
    "chip_bg": "#e4ecfa",
    "chip_border": "#c7d5ec",
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
