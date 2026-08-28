"""Theme palettes + QSS rendering.

The palette dict is the single source of truth.  ``resources/themes/app.qss``
is a template with ``{token}`` placeholders that is ``str.format``-ed with the
active palette, so QSS and the Python-side colour roles (table cell colours,
matplotlib figures in M2) can never drift apart.  A test asserts every palette
key is referenced by the template and vice-versa.
"""

from __future__ import annotations

from importlib import resources

__all__ = ["THEMES", "palette", "render_qss", "template_text"]

# --- palettes -----------------------------------------------------------

_SHAB = {
    "bg": "#1e2127",
    "bg_alt": "#252932",
    "surface": "#2b3038",
    "border": "#3b4048",
    "text": "#d5d8dd",
    "text_muted": "#8b93a0",
    "primary": "#7fd1e0",
    "primary_fg": "#12252b",
    "accent": "#c792ea",
    "overdue": "#ff5c57",
    "due_soon": "#e5c07b",
    "waiting": "#8b93a0",
    "completed": "#6b7280",
    "blocked": "#ff6ac1",
    "selection": "#2f4858",
    "hover": "#313742",
}

_RUZ = {
    "bg": "#ffffff",
    "bg_alt": "#f6f8fa",
    "surface": "#ffffff",
    "border": "#d0d7de",
    "text": "#1f2328",
    "text_muted": "#656d76",
    "primary": "#0b6e99",
    "primary_fg": "#ffffff",
    "accent": "#8250df",
    "overdue": "#d1242f",
    "due_soon": "#9a6700",
    "waiting": "#8c959f",
    "completed": "#a0a6ad",
    "blocked": "#cf222e",
    "selection": "#ddf4ff",
    "hover": "#eef1f4",
}

THEMES: dict[str, dict[str, str]] = {"شب": _SHAB, "روز": _RUZ}
DEFAULT_THEME = "شب"


def palette(name: str) -> dict[str, str]:
    return dict(THEMES.get(name, _SHAB))


def template_text() -> str:
    return (resources.files(__package__) / "resources/themes/app.qss").read_text(
        encoding="utf-8"
    )


def render_qss(name: str) -> str:
    """The full stylesheet for theme *name*."""
    qss = template_text()
    for key, value in palette(name).items():
        qss = qss.replace(f"@{key}@", value)
    return qss
