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

# --- شب (dark) --------------------------------------------------------
_SHAB = {
    "bg": "#16181d",
    "bg_alt": "#1c1f26",
    "surface": "#232730",
    "elevated": "#1e222a",
    "on_danger": "#ffffff",
    "border": "#333844",
    "hover": "#262b34",
    "selection": "#2b3a4a",
    "row_line": "#22262e",
    "field": "#1c1f26",
    "field_focus": "#21252e",
    "text": "#e6e8ec",
    "text_muted": "#9aa2b1",
    "primary": "#6cc7dd",
    "primary_hi": "#8ad6e8",
    "primary_fg": "#08222a",
    "accent": "#b98cf0",
    "overdue": "#ff6b6b",
    "due_soon": "#f0c674",
    "waiting": "#8a93a4",
    "completed": "#7b828f",
    "blocked": "#ff7ac0",
    "success": "#5fbf80",
    "chip_bg": "#24303a",
    "chip_border": "#33475a",
    "chip_fg": "#b8dbe6",
}

# --- روز (light) -----------------------------------------------------
_RUZ = {
    "bg": "#ffffff",
    "bg_alt": "#f5f7fa",
    "surface": "#ffffff",
    "elevated": "#ffffff",
    "on_danger": "#ffffff",
    "border": "#dfe3e8",
    "hover": "#eef1f5",
    "selection": "#dbeeff",
    "row_line": "#eceff3",
    "field": "#f7f9fb",
    "field_focus": "#ffffff",
    "text": "#1c2128",
    "text_muted": "#5c6672",
    "primary": "#0a6e8f",
    "primary_hi": "#0c82a8",
    "primary_fg": "#ffffff",
    "accent": "#7b41d8",
    "overdue": "#cf2b3a",
    "due_soon": "#8a5d00",
    "waiting": "#6f7784",
    "completed": "#98a0aa",
    "blocked": "#c72e86",
    "success": "#1a7f37",
    "chip_bg": "#e5f1f6",
    "chip_border": "#b9d9e5",
    "chip_fg": "#0a5a75",
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
