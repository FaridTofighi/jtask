"""Persistent configuration for jtask.

Settings live in ``$XDG_CONFIG_HOME/jtask/config.yaml`` (``~/.config/jtask`` by
default).  Every setting can be overridden per-invocation by a CLI flag.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .errors import JtaskError

__all__ = [
    "config_dir",
    "config_path",
    "user_themes_dir",
    "DEFAULTS",
    "load",
    "save",
    "get",
    "set_value",
    "is_first_run",
    "mark_first_run_done",
]

DEFAULTS: dict[str, Any] = {
    "theme": "شب",
    "persian_digits": True,
    "date_format": "short",  # "short" | "long"
}

_VALID_DATE_FORMATS = {"short", "long"}


def config_dir() -> Path:
    override = os.environ.get("JTASK_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "jtask"


def config_path() -> Path:
    return config_dir() / "config.yaml"


def user_themes_dir() -> Path:
    return config_dir() / "themes"


def _ensure_dirs() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    user_themes_dir().mkdir(parents=True, exist_ok=True)


def load() -> dict[str, Any]:
    """Return the merged configuration (defaults + user file)."""
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise JtaskError(f"فایل پیکربندی خراب است ({path}): {exc}") from exc
        if not isinstance(data, dict):
            raise JtaskError(f"فایل پیکربندی باید یک نگاشت باشد: {path}")
        cfg.update(data)
    return cfg


def save(cfg: dict[str, Any]) -> None:
    _ensure_dirs()
    stored = {k: v for k, v in cfg.items() if k in DEFAULTS}
    config_path().write_text(
        yaml.safe_dump(stored, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )


def get(key: str) -> Any:
    return load().get(key)


def set_value(key: str, value: Any) -> None:
    if key not in DEFAULTS:
        raise JtaskError(
            f"کلید پیکربندی ناشناخته: «{key}». کلیدهای مجاز: {', '.join(DEFAULTS)}"
        )
    if key == "persian_digits":
        value = str(value).strip().lower() in {"1", "true", "yes", "on", "بله"}
    if key == "date_format" and value not in _VALID_DATE_FORMATS:
        raise JtaskError("قالب تاریخ باید «short» یا «long» باشد.")
    cfg = load()
    cfg[key] = value
    save(cfg)


def _flag_path() -> Path:
    return config_dir() / ".first_run_done"


def is_first_run() -> bool:
    return not _flag_path().exists()


def mark_first_run_done() -> None:
    _ensure_dirs()
    _flag_path().touch()
