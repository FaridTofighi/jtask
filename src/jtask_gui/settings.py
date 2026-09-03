"""Typed wrapper over QSettings for jtask-gui preferences."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QCoreApplication, QSettings

from jtask import config as core_config

from .theme import DEFAULT_THEME, THEMES, canonical_theme

_ORG = "jtask"
_APP = "jtask-gui"

# Set the identity as early as this module is imported, so *any* QSettings
# created anywhere (including a bare ``QSettings()``) lands in the same store
# regardless of import order.  ``Settings`` also always passes the pair
# explicitly, so this is belt-and-braces.
#
# Only set what isn't set yet: re-setting the application name *after* a
# QApplication exists makes Qt re-register the app-id with the desktop portal
# ("Connection already associated with an application ID"). ``app.py`` sets
# these before construction; here we just fill gaps.
if not QCoreApplication.organizationName():
    QCoreApplication.setOrganizationName(_ORG)
if not QCoreApplication.applicationName():
    QCoreApplication.setApplicationName(_APP)


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(_ORG, _APP)

    # --- theme ---
    @property
    def theme(self) -> str:
        stored = self._s.value("theme", DEFAULT_THEME, str)
        name = canonical_theme(stored)
        if name != stored:  # one-time migration of the pre-i2 Persian names
            self._s.setValue("theme", name)
            self._s.sync()
        return name if name in THEMES else DEFAULT_THEME

    @theme.setter
    def theme(self, name: str) -> None:
        self._s.setValue("theme", canonical_theme(name))

    # --- calendar system ---
    @property
    def calendar(self) -> str:
        v = self._s.value("calendar", "jalali", str)
        return v if v in ("jalali", "gregorian") else "jalali"

    @calendar.setter
    def calendar(self, value: str) -> None:
        self._s.setValue(
            "calendar", value if value in ("jalali", "gregorian") else "jalali"
        )
        self._s.sync()

    # --- language ---
    @property
    def language(self) -> str:
        v = self._s.value("language", "fa", str)
        return v if v in ("fa", "en") else "fa"

    @language.setter
    def language(self, value: str) -> None:
        self._s.setValue("language", value if value in ("fa", "en") else "fa")
        self._s.sync()

    # --- digits ---
    @property
    def persian_digits(self) -> bool:
        # Until the user picks a digit mode explicitly (Resolution 1), the
        # default follows the UI language: English → ASCII, Persian → the
        # core-config default. Any stored value is honoured only after an
        # explicit choice.
        if not self.digit_mode_user_overridden:
            if self.language == "en":
                return False
            return bool(core_config.load().get("persian_digits", True))
        default = bool(core_config.load().get("persian_digits", True))
        return self._s.value("persian_digits", default, bool)

    @persian_digits.setter
    def persian_digits(self, value: bool) -> None:
        self._s.setValue("persian_digits", bool(value))

    @property
    def digit_mode_user_overridden(self) -> bool:
        """True once the user has explicitly chosen a digit mode in Settings.

        A separate flag (Resolution 1) — never inferred from the stored value,
        since an explicit choice can coincide with a language's default.
        """
        return self._s.value("digit_mode_user_overridden", False, bool)

    @digit_mode_user_overridden.setter
    def digit_mode_user_overridden(self, value: bool) -> None:
        self._s.setValue("digit_mode_user_overridden", bool(value))
        self._s.sync()

    # --- table density (live toggle) ---
    @property
    def density(self) -> str:
        v = self._s.value("density", "comfortable", str)
        return v if v in ("comfortable", "compact") else "comfortable"

    @density.setter
    def density(self, value: str) -> None:
        self._s.setValue(
            "density", value if value in ("comfortable", "compact") else "comfortable"
        )
        self._s.sync()

    # --- weekly-review wizard resume state ---
    @property
    def review_step(self) -> int:
        try:
            return max(0, int(self._s.value("review/step", 0)))
        except (TypeError, ValueError):
            return 0

    @review_step.setter
    def review_step(self, value: int) -> None:
        self._s.setValue("review/step", int(value))
        self._s.sync()

    @property
    def review_started(self) -> str:
        return self._s.value("review/started", "", str) or ""

    @review_started.setter
    def review_started(self, value: str) -> None:
        self._s.setValue("review/started", value)
        self._s.sync()

    # --- colour-coding threshold ---
    @property
    def due_soon_days(self) -> int:
        return int(self._s.value("due_soon_days", 3, int))

    @due_soon_days.setter
    def due_soon_days(self, value: int) -> None:
        self._s.setValue("due_soon_days", int(value))

    # --- window / layout ---
    # Dock layout ("state") is layout-direction-dependent, so it is namespaced by
    # language — an fa (sidebar right) layout must not be restored into an en
    # (sidebar left) window. Geometry (size/position) is direction-agnostic.
    def _state_key(self, language: str | None = None) -> str:
        return f"win/state_{language or self.language}"

    def save_window(
        self, geometry: QByteArray, state: QByteArray, language: str | None = None
    ) -> None:
        self._s.setValue("win/geometry", geometry)
        self._s.setValue(self._state_key(language), state)

    def window_geometry(self) -> QByteArray | None:
        return self._s.value("win/geometry")

    def window_state(self) -> QByteArray | None:
        val = self._s.value(self._state_key())
        if val is None and self.language == "fa":
            val = self._s.value("win/state")  # pre-i3 store was fa-only
        return val

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

    def reset_columns(self) -> None:
        """Forget any persisted column order / visibility / widths."""
        for key in ("cols/order", "cols/hidden", "cols/widths"):
            self._s.remove(key)
        self._s.sync()

    # --- Taskwarrior binary / data location overrides ---
    # Empty string = "use the ambient environment / PATH". When set, applied to
    # os.environ in app.build_application() *before* the first `task` call.
    # Changing any of these needs a restart (like language / calendar).
    @property
    def task_bin(self) -> str:
        return self._s.value("tw/bin", "", str)

    @task_bin.setter
    def task_bin(self, value: str) -> None:
        self._s.setValue("tw/bin", str(value or ""))
        self._s.sync()

    @property
    def taskdata(self) -> str:
        return self._s.value("tw/data", "", str)

    @taskdata.setter
    def taskdata(self, value: str) -> None:
        self._s.setValue("tw/data", str(value or ""))
        self._s.sync()

    @property
    def taskrc(self) -> str:
        return self._s.value("tw/rc", "", str)

    @taskrc.setter
    def taskrc(self, value: str) -> None:
        self._s.setValue("tw/rc", str(value or ""))
        self._s.sync()

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

    # --- task templates (reusable one-off task shapes; GUI concept, like
    #     saved filters — no schedule, distinct from recurrence) ---
    def templates(self) -> dict[str, dict]:
        raw = self._s.value("templates/saved", {}, dict) or {}
        return {str(k): dict(v) for k, v in raw.items()}

    def save_template(self, name: str, spec: dict) -> None:
        current = self.templates()
        current[name] = spec
        self._s.setValue("templates/saved", current)
        self._s.sync()

    def delete_template(self, name: str) -> None:
        current = self.templates()
        current.pop(name, None)
        self._s.setValue("templates/saved", current)
        self._s.sync()

    # --- custom boards (the board engine) ---
    def boards(self) -> dict[str, dict]:
        raw = self._s.value("boards/user", {}, dict) or {}
        return {str(k): dict(v) for k, v in raw.items()}

    def board_order(self) -> list[str]:
        raw = self._s.value("boards/order", [], list) or []
        return [str(x) for x in raw]

    def save_board(self, name: str, spec: dict) -> None:
        current = self.boards()
        current[name] = spec
        self._s.setValue("boards/user", current)
        order = self.board_order()
        if name not in order:
            order.append(name)
        self._s.setValue("boards/order", order)
        self._s.sync()

    def delete_board(self, name: str) -> None:
        current = self.boards()
        current.pop(name, None)
        self._s.setValue("boards/user", current)
        self._s.setValue("boards/order", [x for x in self.board_order() if x != name])
        self._s.sync()

    def set_board_order(self, order: list[str]) -> None:
        self._s.setValue("boards/order", list(order))
        self._s.sync()

    def sync(self) -> None:
        self._s.sync()
