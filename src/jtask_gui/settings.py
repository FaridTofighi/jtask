"""Typed wrapper over QSettings for jtask-gui preferences."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QCoreApplication, QSettings

from jtask import config as core_config

from .theme import DEFAULT_THEME, THEMES

_ORG = "jtask"
_APP = "jtask-gui"

# Set the identity as early as this module is imported, so *any* QSettings
# created anywhere (including a bare ``QSettings()``) lands in the same store
# regardless of import order.  ``Settings`` also always passes the pair
# explicitly, so this is belt-and-braces.
QCoreApplication.setOrganizationName(_ORG)
QCoreApplication.setApplicationName(_APP)


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

    # --- sync ---
    @property
    def last_sync(self) -> str:
        """ISO-8601 local timestamp of the last successful sync, or ''."""
        return self._s.value("sync/last", "", str)

    @last_sync.setter
    def last_sync(self, value: str) -> None:
        self._s.setValue("sync/last", str(value))
        self._s.sync()

    # --- notifications ---
    @property
    def notifications_enabled(self) -> bool:
        return self._s.value("notify/enabled", False, bool)

    @notifications_enabled.setter
    def notifications_enabled(self, value: bool) -> None:
        self._s.setValue("notify/enabled", bool(value))

    @property
    def notify_states(self) -> list[str]:
        raw = self._s.value("notify/states", ["overdue", "today"], list)
        return [str(x) for x in (raw or [])]

    @notify_states.setter
    def notify_states(self, value: list[str]) -> None:
        self._s.setValue("notify/states", list(value))

    @property
    def notify_interval_min(self) -> int:
        return int(self._s.value("notify/interval_min", 15, int))

    @notify_interval_min.setter
    def notify_interval_min(self, value: int) -> None:
        self._s.setValue("notify/interval_min", int(value))

    @property
    def quiet_hours(self) -> tuple[int, int]:
        start = int(self._s.value("notify/quiet_start", 22, int))
        end = int(self._s.value("notify/quiet_end", 7, int))
        return start, end

    @quiet_hours.setter
    def quiet_hours(self, value: tuple[int, int]) -> None:
        self._s.setValue("notify/quiet_start", int(value[0]))
        self._s.setValue("notify/quiet_end", int(value[1]))

    # --- first-run wizard ---
    @property
    def wizard_done(self) -> bool:
        return self._s.value("wizard/done", False, bool)

    @wizard_done.setter
    def wizard_done(self, value: bool) -> None:
        self._s.setValue("wizard/done", bool(value))
        self._s.sync()

    # --- saved filters (name -> raw filter string) ---
    def saved_filters(self) -> dict[str, str]:
        raw = self._s.value("filters/saved", {}, dict) or {}
        return {str(k): str(v) for k, v in raw.items()}

    def save_filter(self, name: str, raw: str) -> None:
        current = self.saved_filters()
        current[name] = raw
        self._s.setValue("filters/saved", current)
        self._s.sync()

    def delete_filter(self, name: str) -> None:
        current = self.saved_filters()
        current.pop(name, None)
        self._s.setValue("filters/saved", current)
        self._s.sync()

    def rename_filter(self, old: str, new: str) -> None:
        current = self.saved_filters()
        if old in current and new and new != old:
            current[new] = current.pop(old)
            self._s.setValue("filters/saved", current)
            self._s.sync()

    def sync(self) -> None:
        self._s.sync()
