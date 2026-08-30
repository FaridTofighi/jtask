"""Date / datetime picker — calendar-system agnostic (§ i4).

A line edit (typed absolute or relative date) plus a calendar-popup button.
Renders and parses through the active ``CalendarSystem`` (Jalali or Gregorian);
its output (``gregorian_string``) is always a Taskwarrior-ready string.

``JalaliDatePicker`` is kept as the class name (many imports); it now takes an
optional ``calendar`` argument.
"""

from __future__ import annotations

import datetime as _dt

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali

from ..calendar_system import CalendarSystem, active
from ..i18n import t
from .jalali_calendar import DayCellContext, JalaliMonthGrid


class _CalendarPopup(QDialog):
    datePicked = pyqtSignal(object)  # datetime.date (Gregorian)

    def __init__(
        self, initial: _dt.date, cal: CalendarSystem, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self._cal = cal
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        y, m, _d = cal.from_gregorian_date(initial)
        self._grid = JalaliMonthGrid(y, m, cell_factory=self._make_cell, calendar=cal)
        self._grid.setMinimumSize(280, 240)
        lay.addWidget(self._grid)

    def _make_cell(self, ctx: DayCellContext) -> QWidget:
        btn = QPushButton(str(ctx.day))
        btn.setAutoDefault(False)
        btn.setFlat(True)
        if ctx.is_today:
            btn.setObjectName("Primary")
        btn.clicked.connect(
            lambda: self._pick(
                self._cal.to_gregorian_date(ctx.year, ctx.month, ctx.day)
            )
        )
        return btn

    def _pick(self, d: _dt.date) -> None:
        self.datePicked.emit(d)
        self.accept()


class JalaliDatePicker(QWidget):
    """Line edit + calendar popup. ``with_time=True`` makes the value a datetime."""

    dateChanged = pyqtSignal(object)  # datetime.date | datetime.datetime | None

    def __init__(
        self,
        with_time: bool = False,
        parent: QWidget | None = None,
        calendar: CalendarSystem | None = None,
    ) -> None:
        super().__init__(parent)
        self._cal = calendar or active()
        self._with_time = with_time
        self._value: _dt.date | _dt.datetime | None = None  # Gregorian

        from .. import icons

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(t("datepicker.placeholder"))
        self._edit.setClearButtonEnabled(True)
        self._edit.setMinimumWidth(120)
        self._edit.editingFinished.connect(self._parse_text)
        self._edit.textChanged.connect(self._maybe_cleared)
        row.addWidget(self._edit, 1)

        if with_time:
            self._time = QTimeEdit()
            self._time.setDisplayFormat("HH:mm")
            self._time.setButtonSymbols(QTimeEdit.ButtonSymbols.NoButtons)
            self._time.setFixedWidth(66)
            self._time.setProperty("compact", True)
            self._time.timeChanged.connect(self._on_time)
            row.addWidget(self._time)

        self._btn = QToolButton()
        self._btn.setIcon(icons.icon("calendar", "text_muted"))
        self._btn.setToolTip(t("datepicker.calendar_tip"))
        self._btn.clicked.connect(self._open_popup)
        row.addWidget(self._btn)

    def _maybe_cleared(self, text: str) -> None:
        if not text.strip() and self._value is not None:
            self._value = None
            self.dateChanged.emit(None)

    # --- value API -------------------------------------------------

    def value(self):
        return self._value

    def gregorian_string(self) -> str:
        if self._value is None:
            return ""
        if isinstance(self._value, _dt.datetime):
            return self._value.strftime("%Y-%m-%dT%H:%M:%S")
        return self._value.strftime("%Y-%m-%d")

    def _display_text(self) -> str:
        if self._value is None:
            return ""
        if isinstance(self._value, _dt.datetime):
            return self._cal.format_local(
                self._value.strftime("%Y-%m-%d %H:%M:%S"), "datetime"
            )
        return self._cal.format_local(self._value.strftime("%Y-%m-%d"), "short")

    def set_value(self, value) -> None:
        """*value* may be a Gregorian ``date``/``datetime`` or (compat) a
        ``jdatetime`` object."""
        if value is not None and hasattr(value, "togregorian"):
            value = value.togregorian()
        self._value = value
        if value is None:
            self._edit.clear()
        else:
            self._edit.setText(self._display_text())
            if self._with_time and isinstance(value, _dt.datetime):
                self._time.setTime(
                    self._time.time().fromString(
                        f"{value.hour:02d}:{value.minute:02d}", "HH:mm"
                    )
                )
        self.dateChanged.emit(self._value)

    def set_from_taskwarrior(self, ts: str) -> None:
        if not ts:
            self.set_value(None)
            return
        m = jalali._TW_TS_RE.match(ts.strip())
        if not m:
            self.set_value(None)
            return
        y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
        local = _dt.datetime(
            y, mo, d, hh, mm, ss, tzinfo=_dt.timezone.utc
        ).astimezone(jalali.LOCAL_TZ)
        self.set_value(local.date())

    def clear(self) -> None:
        self.set_value(None)

    # --- internals ------------------------------------------------

    def _parse_text(self) -> None:
        text = self._edit.text().strip()
        if not text:
            self.set_value(None)
            return
        tw = self._cal.to_taskwarrior(text)
        parsed = _parse_tw_string(tw)
        if parsed is None:
            self._edit.setStyleSheet("border: 1px solid #d1242f;")
            return
        self._edit.setStyleSheet("")
        if self._with_time and not isinstance(parsed, _dt.datetime):
            time = self._time.time()
            parsed = _dt.datetime(
                parsed.year, parsed.month, parsed.day, time.hour(), time.minute()
            )
        self.set_value(parsed)

    def _on_time(self) -> None:
        if isinstance(self._value, _dt.date) and not isinstance(
            self._value, _dt.datetime
        ):
            time = self._time.time()
            self.set_value(
                _dt.datetime(
                    self._value.year, self._value.month, self._value.day,
                    time.hour(), time.minute(),
                )
            )

    def _open_popup(self) -> None:
        initial = self._value or _dt.date.today()
        if isinstance(initial, _dt.datetime):
            initial = initial.date()
        popup = _CalendarPopup(initial, self._cal, self)
        popup.datePicked.connect(self._picked_from_popup)
        pos = self.mapToGlobal(self._btn.geometry().bottomLeft())
        popup.move(pos)
        popup.exec()

    def _picked_from_popup(self, d: _dt.date) -> None:
        if self._with_time:
            time = self._time.time()
            self.set_value(
                _dt.datetime(d.year, d.month, d.day, time.hour(), time.minute())
            )
        else:
            self.set_value(d)


def _parse_tw_string(s: str) -> _dt.date | _dt.datetime | None:
    """A Taskwarrior date string we produced → a Gregorian date/datetime.
    Relative words we didn't resolve (``tomorrow`` …) return None → the field
    shows an error rather than a wrong value; use the picker for those."""
    s = s.strip()
    for fmt_ in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            v = _dt.datetime.strptime(s, fmt_)
            return v if "T" in s else v.date()
        except ValueError:
            pass
    return None
