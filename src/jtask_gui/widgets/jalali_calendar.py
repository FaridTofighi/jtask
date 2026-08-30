"""Reusable month-grid engine — calendar-system agnostic (§ i4).

The grid knows only how to lay out *a* month for whatever ``CalendarSystem`` it
is given (Jalali or Gregorian). It does not decide what a day cell shows or what
clicking it does — the caller supplies ``cell_factory(ctx) -> QWidget``. The
date picker and the calendar report share this one engine for both systems.

``JalaliMonthGrid`` is kept as the class name (many imports); it now takes an
optional ``calendar`` argument and defaults to the active system.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import fmt
from .. import tokens as tok
from ..calendar_system import CalendarSystem, active


@dataclass(frozen=True)
class DayCellContext:
    year: int
    month: int
    day: int
    is_today: bool
    is_current_month: bool
    weekday_index: int  # 0 = first column of the active system's week


CellFactory = Callable[[DayCellContext], QWidget]


def _default_cell(ctx: DayCellContext) -> QWidget:
    lbl = QLabel(fmt.digits(str(ctx.day)))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


class JalaliMonthGrid(QWidget):
    """A 7-column month grid with month navigation, for any calendar system."""

    monthChanged = pyqtSignal(int, int)  # year, month

    def __init__(
        self,
        year: int | None = None,
        month: int | None = None,
        cell_factory: CellFactory | None = None,
        parent: QWidget | None = None,
        calendar: CalendarSystem | None = None,
    ) -> None:
        super().__init__(parent)
        self._cal = calendar or active()
        today = self._cal.today()
        self._year = year or today.year
        self._month = month or today.month
        self._factory: CellFactory = cell_factory or _default_cell

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(tok.SP_6)

        rtl = QApplication.instance() is not None and (
            QApplication.instance().layoutDirection() == Qt.LayoutDirection.RightToLeft
        )
        # earlier / later month — glyphs chosen for the reading direction
        self._prev = QPushButton("›" if rtl else "‹")
        self._next = QPushButton("‹" if rtl else "›")
        for b in (self._prev, self._next):
            b.setFixedWidth(38)
            b.setAutoDefault(False)
            b.setFlat(True)
            f = b.font()
            f.setPointSizeF(f.pointSizeF() + 3)
            b.setFont(f)
        self._title = QLabel()
        self._title.setObjectName("H2")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header = QHBoxLayout()
        header.addWidget(self._prev)      # Qt positions by layout direction
        header.addWidget(self._title, 1)
        header.addWidget(self._next)
        root.addLayout(header)

        self._prev.clicked.connect(lambda: self._step(-1))
        self._next.clicked.connect(lambda: self._step(+1))

        self._grid = QGridLayout()
        self._grid.setSpacing(tok.SP_4)
        for col, name in enumerate(self._cal.weekday_names_short()):
            lbl = QLabel(name)
            lbl.setObjectName("Muted")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(lbl, 0, col)
        root.addLayout(self._grid)
        root.addStretch(1)

        self._rebuild()

    # --- public API -------------------------------------------------

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    def set_month(self, year: int, month: int) -> None:
        year, month = self._normalise(year, month)
        if (year, month) == (self._year, self._month):
            return
        self._year, self._month = year, month
        self._rebuild()
        self.monthChanged.emit(year, month)

    def set_cell_factory(self, factory: CellFactory) -> None:
        self._factory = factory
        self._rebuild()

    def refresh(self) -> None:
        self._rebuild()

    # --- internals -------------------------------------------------

    @staticmethod
    def _normalise(year: int, month: int) -> tuple[int, int]:
        year += (month - 1) // 12
        month = (month - 1) % 12 + 1
        return year, month

    def _step(self, delta: int) -> None:
        self.set_month(*self._normalise(self._year, self._month + delta))

    def _clear_day_cells(self) -> None:
        for i in reversed(range(self._grid.count())):
            item = self._grid.itemAt(i)
            row, _, _, _ = self._grid.getItemPosition(i)
            if row == 0:
                continue
            w = item.widget()
            self._grid.removeItem(item)
            if w is not None:
                w.deleteLater()

    def _rebuild(self) -> None:
        self._title.setText(self._cal.label_ym(self._year, self._month))
        self._clear_day_cells()

        grid = self._cal.month_grid(self._year, self._month)
        for r, week in enumerate(grid, start=1):
            for c, day in enumerate(week):
                if day is None:
                    continue
                ctx = DayCellContext(
                    year=self._year,
                    month=self._month,
                    day=day,
                    is_today=self._cal.is_today(self._year, self._month, day),
                    is_current_month=True,
                    weekday_index=c,
                )
                cell = self._factory(ctx)
                cell.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                )
                self._grid.addWidget(cell, r, c)


MonthGrid = JalaliMonthGrid  # the honest name; both are the same engine
