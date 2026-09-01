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
# A *soft* dark theme: the base is a charcoal (not near-black) and the
# elevation ladder is gentle — surface sits a small step above the window, and
# borders / dividers are low-contrast against their surface so regions read by
# tone, not by hard lines (mirrors how the light theme separates).  n-mission
# re-tone: bg #0e1014 → #191c22, borders pulled in toward their surfaces.
_SHAB = {
    "bg": "#191c22",
    "bg_alt": "#1e222a",
    "surface": "#252a33",
    "elevated": "#2e3440",
    "on_danger": "#ffffff",
    "border": "#333945",
    "border_soft": "#2b313c",
    "hover": "#2b313c",
    "selection": "#2e4d59",
    "row_line": "#2c323d",
    "row_alt": "#292f39",
    "field": "#1c2027",
    "field_focus": "#232833",
    "text": "#e0e3ea",
    "text_muted": "#8f97a6",
    "primary": "#6cc7dd",
    "primary_hi": "#8ad6e8",
    "primary_fg": "#08222a",
    "primary_soft": "#22434e",
    "accent": "#b98cf0",
    "focus": "#6cc7dd",
    "overdue": "#ff7b7b",
    "due_soon": "#f5c451",
    "waiting": "#8891a0",
    "completed": "#767e8c",
    "blocked": "#f472b6",
    "success": "#4ade80",
    "chip_bg": "#26303c",
    "chip_border": "#38434f",
    "chip_fg": "#a9c7e8",
}

# --- روز (light) -----------------------------------------------------
# A *dimmed* light theme: the window base is a mid cool-grey and ``surface`` a
# soft off-white (not pure white), so it reads as daylight without the glare.
# The elevation ladder is deliberately wide — surface sits ~0.15 luminance
# above bg, bg ~0.07 above the sidebar — so cards, the nav rail and dialogs
# separate cleanly.  WCAG-AA contrast + palette parity stay enforced by
# tests/gui/test_theme.py.
_RUZ = {
    "bg": "#d9dee6",
    "bg_alt": "#ced4de",
    "surface": "#eef1f5",
    "elevated": "#f7f9fb",
    "on_danger": "#ffffff",
    "border": "#b7c0cc",
    "border_soft": "#c7ced9",
    "hover": "#e2e6ed",
    "selection": "#b0d6e3",
    "row_line": "#dce1e9",
    "row_alt": "#e6eaf0",
    "field": "#e3e7ee",
    "field_focus": "#f7f9fb",
    "text": "#1a1f27",
    "text_muted": "#4c5666",
    "primary": "#0a6e8f",
    "primary_hi": "#0c82a8",
    "primary_fg": "#ffffff",
    "primary_soft": "#cde4ec",
    "accent": "#7b41d8",
    "focus": "#0a6e8f",
    "overdue": "#d63b45",
    "due_soon": "#8a6000",
    "waiting": "#5e6978",
    "completed": "#808995",
    "blocked": "#c72e86",
    "success": "#187a3c",
    "chip_bg": "#dae5f4",
    "chip_border": "#bbcbde",
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
