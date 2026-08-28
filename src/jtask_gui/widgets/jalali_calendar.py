"""Reusable Saturday-first Jalali month-grid engine.

``JalaliMonthGrid`` knows only how to lay out a Jalali month.  It does not
decide what a day cell shows or what clicking it does — the caller supplies a
``cell_factory(ctx) -> QWidget``.  This lets the date picker (plain selectable
numbers, click returns a date) and the M2 calendar report (task-density cells,
click opens that day's task list) share one grid with zero duplication.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import jdatetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali

from .. import fmt


@dataclass(frozen=True)
class DayCellContext:
    year: int
    month: int
    day: int
    is_today: bool
    is_current_month: bool
    weekday_index: int  # 0 = Saturday


CellFactory = Callable[[DayCellContext], QWidget]


def _default_cell(ctx: DayCellContext) -> QWidget:
    lbl = QLabel(fmt.digits(str(ctx.day)))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


class JalaliMonthGrid(QWidget):
    """A 7-column (Saturday-first) Jalali month grid with month navigation."""

    monthChanged = pyqtSignal(int, int)  # year, month

    def __init__(
        self,
        year: int | None = None,
        month: int | None = None,
        cell_factory: CellFactory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        today = jdatetime.date.today()
        self._year = year or today.year
        self._month = month or today.month
        self._factory: CellFactory = cell_factory or _default_cell

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # --- header: « month year » (RTL: prev on the right, next on the left) ---
        header = QHBoxLayout()
        self._prev = QPushButton("»")   # earlier month — points right
        self._next = QPushButton("«")   # later month — points left
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
        # RTL: "next" (advance) sits on the left, "prev" on the right
        header.addWidget(self._next)
        header.addWidget(self._title, 1)
        header.addWidget(self._prev)
        root.addLayout(header)

        self._prev.clicked.connect(lambda: self._step(-1))
        self._next.clicked.connect(lambda: self._step(+1))

        # --- weekday header row ---
        self._grid = QGridLayout()
        self._grid.setSpacing(4)
        for col, name in enumerate(jalali.WEEKDAY_NAMES_SHORT):
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
        self._title.setText(
            fmt.digits(f"{jalali.MONTH_NAMES[self._month - 1]} {self._year}")
        )
        self._clear_day_cells()

        today = jdatetime.date.today()
        grid = jalali.month_grid(self._year, self._month)
        for r, week in enumerate(grid, start=1):
            for c, day in enumerate(week):
                if day is None:
                    continue
                ctx = DayCellContext(
                    year=self._year,
                    month=self._month,
                    day=day,
                    is_today=(today.year, today.month, today.day)
                    == (self._year, self._month, day),
                    is_current_month=True,
                    weekday_index=c,
                )
                cell = self._factory(ctx)
                cell.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                )
                self._grid.addWidget(cell, r, c)
