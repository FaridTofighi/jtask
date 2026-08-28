"""The reusable Jalali month-grid engine."""

import pytest
from PyQt6.QtWidgets import QLabel

from jtask_gui.widgets.jalali_calendar import DayCellContext, JalaliMonthGrid


@pytest.fixture
def grid(qtbot):
    w = JalaliMonthGrid(1403, 7)
    qtbot.addWidget(w)
    return w


def test_saturday_first_weekday_headers(grid):
    headers = [
        grid._grid.itemAtPosition(0, c).widget().text() for c in range(7)
    ]
    assert headers[0] == "ش"  # Saturday
    assert headers[-1] == "ج"  # Friday


def test_cell_factory_called_once_per_real_day_with_context(qtbot):
    seen: list[DayCellContext] = []

    def factory(ctx):
        seen.append(ctx)
        return QLabel(str(ctx.day))

    w = JalaliMonthGrid(1403, 7, cell_factory=factory)
    qtbot.addWidget(w)
    # Mehr 1403 has 30 days
    assert len(seen) == 30
    assert {c.day for c in seen} == set(range(1, 31))
    assert all(c.year == 1403 and c.month == 7 for c in seen)


def test_leading_blanks_match_first_weekday(qtbot):
    # 1403-07-01 is a Sunday -> weekday index 1 -> exactly one leading blank
    positions = []

    def factory(ctx):
        positions.append(ctx.weekday_index)
        return QLabel()

    w = JalaliMonthGrid(1403, 7, cell_factory=factory)
    qtbot.addWidget(w)
    assert positions[0] == 1  # day 1 sits in column 1 (Sunday), one leading blank


def test_leap_esfand_has_30_days_in_1403_and_29_in_1404(qtbot):
    for year, expected in ((1403, 30), (1404, 29)):
        seen: list[int] = []

        def factory(ctx, sink=seen):
            sink.append(ctx.day)
            return QLabel()

        w = JalaliMonthGrid(year, 12, cell_factory=factory)
        qtbot.addWidget(w)
        assert max(seen) == expected


def test_month_navigation_wraps_year(grid, qtbot):
    changes = []
    grid.monthChanged.connect(lambda y, m: changes.append((y, m)))
    grid.set_month(1403, 13)  # -> 1404-01
    assert grid.year == 1404 and grid.month == 1
    assert changes[-1] == (1404, 1)


def test_set_month_noop_does_not_emit(grid):
    changes = []
    grid.monthChanged.connect(lambda y, m: changes.append((y, m)))
    grid.set_month(1403, 7)
    assert changes == []
