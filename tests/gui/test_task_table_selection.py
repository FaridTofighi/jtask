"""Selected-row rendering: one continuous band, a single leading-edge accent
bar, bounded exactly to the visible columns (no per-cell boxes, no overflow
past the last column)."""

from __future__ import annotations

import re

import pytest
from PyQt6.QtCore import Qt

from jtask_gui import theme
from jtask_gui.models.column_spec import COLUMNS
from jtask_gui.models.task_model import TaskTableModel
from jtask_gui.widgets.task_table import TaskTable

# --- Bug 1: no per-cell border on the selected row -----------------------

def test_selection_qss_rule_has_no_border():
    """Selection must be background-only — a per-item ``border`` draws a line
    on every cell edge and produces the boxed-grid look."""
    for name in theme.THEMES:
        qss = theme.render_qss(name)
        m = re.search(r"QTableView::item:selected\s*\{([^}]*)\}", qss)
        assert m, f"{name}: no QTableView::item:selected rule"
        assert "border" not in m.group(1), \
            f"{name}: selection rule still has a border → {m.group(1).strip()}"


def test_accent_bar_is_on_the_leading_edge(qtbot):
    m = TaskTableModel()
    m.set_tasks([{"id": 1, "description": "x", "status": "pending"}])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    tbl.resize(600, 120)

    tbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    assert tbl._bar_x() == 0

    tbl.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    assert tbl._bar_x() == tbl.viewport().width() - tbl._SELECTION_BAR_W
    assert 2 <= tbl._SELECTION_BAR_W <= 3


def test_paintevent_runs_with_a_selection(qtbot):
    m = TaskTableModel()
    m.set_tasks([{"id": i, "description": f"t{i}", "status": "pending"} for i in range(3)])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    tbl.resize(700, 200)
    tbl.selectRow(1)
    for direction in (Qt.LayoutDirection.LeftToRight, Qt.LayoutDirection.RightToLeft):
        tbl.setLayoutDirection(direction)
        tbl.viewport().repaint()          # must not raise


# --- Bug 2: selection bounded to the visible columns --------------------

def test_status_is_the_last_column_no_blank_trailing_cells():
    """The three per-task markers share ONE column placed *before* status, so
    nothing renders past the last real column."""
    vis = TaskTableModel().visible_columns()
    assert vis[-1] == "status"

    empty_header_visible = [c.key for c in COLUMNS if c.header == "" and c.default_visible]
    assert empty_header_visible == ["indicators"]           # exactly one
    assert vis.index("indicators") < len(vis) - 1           # and it is not last


@pytest.mark.parametrize("cols", [None, ["id", "description", "priority", "due"]])
def test_selection_extent_matches_the_visible_column_range(qtbot, cols):
    m = TaskTableModel()
    if cols:
        m.set_columns(cols)
    m.set_tasks([{
        "id": 1, "description": "hi", "status": "pending",
        "annotations": [{"description": "n"}], "recur": "weekly",
    }])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    tbl.resize(900, 150)
    tbl.selectRow(0)

    n = m.columnCount()
    rects = [tbl.visualRect(m.index(0, c)) for c in range(n)]
    span_left = min(r.left() for r in rects)
    span_right = max(r.right() for r in rects)

    # the selected band spans exactly first-column-left .. last-column-right
    assert span_left == tbl.visualRect(m.index(0, 0)).left()
    assert span_right == tbl.visualRect(m.index(0, n - 1)).right()

    # no phantom empty-header column sits at the trailing edge
    headers = [m.headerData(c, Qt.Orientation.Horizontal) for c in range(n)]
    assert headers[-1] != "", f"trailing column has an empty header: {headers}"


def test_indicators_column_paints_markers(qtbot):
    m = TaskTableModel()
    m.set_tasks([{
        "id": 1, "description": "x", "status": "pending",
        "annotations": [{"description": "n"}], "recur": "weekly", "depends": ["u"],
    }])
    col = m.visible_columns().index("indicators")
    deco = m.data(m.index(0, col), Qt.ItemDataRole.DecorationRole)
    assert deco is not None and not deco.isNull()           # a composited pixmap

    m.set_tasks([{"id": 2, "description": "y", "status": "pending"}])
    assert m.data(m.index(0, col), Qt.ItemDataRole.DecorationRole) is None
