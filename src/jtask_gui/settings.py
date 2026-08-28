"""Typed wrapper over QSettings for jtask-gui preferences."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QSettings

from jtask import config as core_config

from .theme import DEFAULT_THEME, THEMES

_ORG = "jtask"
_APP = "jtask-gui"


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(_ORG, _APP)

    # --- theme ---
    @property
    def theme(self) -> str:
        name = self._s.value("theme", DEFAULT_THEME, str)
        return name if name in THEMES else DEFAULT_THEME

    @theme.setter
    def theme(self, name: str) -> None:
        self._s.setValue("theme", name)

    # --- digits ---
    @property
    def persian_digits(self) -> bool:
        default = bool(core_config.load().get("persian_digits", True))
        return self._s.value("persian_digits", default, bool)

    @persian_digits.setter
    def persian_digits(self, value: bool) -> None:
        self._s.setValue("persian_digits", bool(value))

    # --- colour-coding threshold ---
    @property
    def due_soon_days(self) -> int:
        return int(self._s.value("due_soon_days", 3, int))

    @due_soon_days.setter
    def due_soon_days(self, value: int) -> None:
        self._s.setValue("due_soon_days", int(value))

    # --- window / layout ---
    def save_window(self, geometry: QByteArray, state: QByteArray) -> None:
        self._s.setValue("win/geometry", geometry)
        self._s.setValue("win/state", state)

    def window_geometry(self) -> QByteArray | None:
        return self._s.value("win/geometry")

    def window_state(self) -> QByteArray | None:
        return self._s.value("win/state")

    # --- columns ---
    def save_columns(self, order: list[str], hidden: list[str], widths: dict[str, int]) -> None:
        self._s.setValue("cols/order", order)
        self._s.setValue("cols/hidden", hidden)
        self._s.setValue("cols/widths", widths)

    def columns(self) -> tuple[list[str], list[str], dict[str, int]]:
        order = self._s.value("cols/order", [], list) or []
        hidden = self._s.value("cols/hidden", [], list) or []
        widths = self._s.value("cols/widths", {}, dict) or {}
        return list(order), list(hidden), {k: int(v) for k, v in widths.items()}

    # --- console dock ---
    @property
    def console_visible(self) -> bool:
        return self._s.value("console/visible", False, bool)

    @console_visible.setter
    def console_visible(self, value: bool) -> None:
        self._s.setValue("console/visible", bool(value))

    def sync(self) -> None:
        self._s.sync()
