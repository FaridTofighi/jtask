"""Theme loading and resolution.

A theme is a YAML file defining colors, table style, digit preference and the
default date format.  Built-in themes ship inside the package; users drop extra
``*.yaml`` files into ``~/.config/jtask/themes/`` with no code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from rich import box as rich_box

from . import config
from .errors import JtaskError

__all__ = ["Theme", "list_themes", "load_theme", "resolve", "DEFAULT_CHART_PALETTE"]

DEFAULT_CHART_PALETTE = [
    "#7fd1e0", "#c792ea", "#5af78e", "#f3f99d", "#57c7ff", "#ff6ac1",
]

_FALLBACK_COLORS = {
    "primary": "cyan",
    "secondary": "bright_black",
    "accent": "magenta",
    "overdue": "red",
    "due_soon": "yellow",
    "waiting": "blue",
    "completed": "green",
    "blocked": "bright_red",
    "header": "cyan",
    "muted": "bright_black",
}


@dataclass
class Theme:
    name: str
    colors: dict[str, str] = field(default_factory=lambda: dict(_FALLBACK_COLORS))
    box_name: str = "ROUNDED"
    persian_digits: bool = True
    date_format: str = "short"
    chart_palette: list[str] = field(default_factory=lambda: list(DEFAULT_CHART_PALETTE))
    description: str = ""

    def color(self, key: str) -> str:
        return self.colors.get(key, _FALLBACK_COLORS.get(key, "white"))

    @property
    def box(self) -> rich_box.Box:
        return getattr(rich_box, self.box_name.upper(), rich_box.ROUNDED)


def _builtin_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    pkg = resources.files(__package__) / "themes_data"
    for entry in pkg.iterdir():
        if entry.name.endswith(".yaml"):
            with resources.as_file(entry) as p:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            name = data.get("name") or entry.name[:-5]
            out[name] = Path(str(entry))
    return out


def _user_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    d = config.user_themes_dir()
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        name = data.get("name") or p.stem
        out[name] = p
    return out


def list_themes() -> dict[str, Path]:
    """Map theme name -> file path (user themes override built-ins by name)."""
    merged = _builtin_files()
    merged.update(_user_files())
    return merged


def _from_data(data: dict[str, Any], fallback_name: str) -> Theme:
    colors = dict(_FALLBACK_COLORS)
    colors.update(data.get("colors") or {})
    table = data.get("table") or {}
    return Theme(
        name=data.get("name") or fallback_name,
        colors=colors,
        box_name=str(table.get("box", "ROUNDED")),
        persian_digits=bool(data.get("persian_digits", True)),
        date_format=str(data.get("date_format", "short")),
        chart_palette=list(data.get("chart_palette") or DEFAULT_CHART_PALETTE),
        description=str(data.get("description", "")),
    )


def load_theme(name: str) -> Theme:
    themes = list_themes()
    if name not in themes:
        raise JtaskError(
            f"تم «{name}» پیدا نشد. تم‌های موجود: {'، '.join(themes) or '—'}"
        )
    path = themes[name]
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _from_data(data, name)


def resolve(
    cfg: dict[str, Any] | None = None,
    *,
    theme_override: str | None = None,
    digits_override: bool | None = None,
    date_format_override: str | None = None,
) -> Theme:
    """Resolve the active theme from config + CLI overrides."""
    cfg = cfg or config.load()
    name = theme_override or cfg.get("theme") or "شب"
    theme = load_theme(name)
    # config-level preferences win over the theme file's own defaults
    if "persian_digits" in cfg:
        theme.persian_digits = bool(cfg["persian_digits"])
    if cfg.get("date_format"):
        theme.date_format = cfg["date_format"]
    # explicit CLI flags win over everything
    if digits_override is not None:
        theme.persian_digits = digits_override
    if date_format_override:
        theme.date_format = date_format_override
    return theme
