"""Jalali date / datetime picker — a thin consumer of ``JalaliMonthGrid``.

Picker-level behaviour (typing, validation, "click a day → set value & close")
lives here, never in the grid engine.
"""

from __future__ import annotations

import jdatetime
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

from ..i18n import t
from .jalali_calendar import DayCellContext, JalaliMonthGrid


class _CalendarPopup(QDialog):
    datePicked = pyqtSignal(object)  # jdatetime.date

    def __init__(self, initial: jdatetime.date, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self._grid = JalaliMonthGrid(
            initial.year, initial.month, cell_factory=self._make_cell
        )
        self._grid.setMinimumSize(280, 240)
        lay.addWidget(self._grid)

    def _make_cell(self, ctx: DayCellContext) -> QWidget:
        btn = QPushButton(str(ctx.day))
        btn.setAutoDefault(False)
        btn.setFlat(True)
        if ctx.is_today:
            btn.setObjectName("Primary")
        btn.clicked.connect(
            lambda: self._pick(jdatetime.date(ctx.year, ctx.month, ctx.day))
        )
        return btn

    def _pick(self, d: jdatetime.date) -> None:
        self.datePicked.emit(d)
        self.accept()


class JalaliDatePicker(QWidget):
    """Line edit (typed Jalali / Persian-relative) + calendar-popup button.

    ``with_time=True`` adds a time spinner and the value is a datetime.
    """

    dateChanged = pyqtSignal(object)  # jdatetime.date | jdatetime.datetime | None

    def __init__(self, with_time: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._with_time = with_time
        self._value: jdatetime.date | jdatetime.datetime | None = None

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
        """Taskwarrior-facing string, or '' when empty."""
        if self._value is None:
            return ""
        if isinstance(self._value, jdatetime.datetime):
            return self._value.togregorian().strftime("%Y-%m-%dT%H:%M:%S")
        return self._value.togregorian().strftime("%Y-%m-%d")

    def set_value(self, value) -> None:
        self._value = value
        if value is None:
            self._edit.clear()
        else:
            self._edit.setText(
                jalali.to_persian_digits(value.strftime("%Y-%m-%d"))
            )
            if self._with_time and isinstance(value, jdatetime.datetime):
                self._time.setTime(
                    self._time.time().fromString(
                        f"{value.hour:02d}:{value.minute:02d}", "HH:mm"
                    )
                )
        self.dateChanged.emit(self._value)

    def set_from_taskwarrior(self, ts: str) -> None:
        """Populate from a raw Taskwarrior UTC timestamp."""
        if not ts:
            self.set_value(None)
            return
        shown = jalali.from_taskwarrior(ts, fmt="short")  # ۱۴۰۳-۰۷-۱۰
        try:
            self.set_value(jalali.parse_jalali(jalali.normalize_digits(shown)))
        except jalali.JalaliError:
            self.set_value(None)

    def clear(self) -> None:
        self.set_value(None)

    # --- internals ------------------------------------------------

    def _parse_text(self) -> None:
        text = self._edit.text().strip()
        if not text:
            self.set_value(None)
            return
        try:
            resolved = jalali.resolve(text)
        except jalali.JalaliError:
            self._edit.setStyleSheet("border: 1px solid #d1242f;")
            return
        self._edit.setStyleSheet("")
        if (
            self._with_time
            and not isinstance(resolved, jdatetime.datetime)
        ):
            t = self._time.time()
            resolved = jdatetime.datetime(
                resolved.year, resolved.month, resolved.day, t.hour(), t.minute()
            )
        self.set_value(resolved)

    def _on_time(self) -> None:
        if isinstance(self._value, jdatetime.date):
            base = self._value
            t = self._time.time()
            self.set_value(
                jdatetime.datetime(base.year, base.month, base.day, t.hour(), t.minute())
            )

    def _open_popup(self) -> None:
        initial = self._value or jdatetime.date.today()
        if isinstance(initial, jdatetime.datetime):
            initial = initial.date()
        popup = _CalendarPopup(initial, self)
        popup.datePicked.connect(self._picked_from_popup)
        pos = self.mapToGlobal(self._btn.geometry().bottomLeft())
        popup.move(pos)
        popup.exec()

    def _picked_from_popup(self, d: jdatetime.date) -> None:
        if self._with_time:
            t = self._time.time()
            self.set_value(
                jdatetime.datetime(d.year, d.month, d.day, t.hour(), t.minute())
            )
        else:
            self.set_value(d)
