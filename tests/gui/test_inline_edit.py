"""N-A: inline cell editing for project / priority / due."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

from jtask_gui.models.task_model import TaskTableModel


@pytest.fixture
def model():
    m = TaskTableModel()
    m.set_tasks([{
        "id": 1, "uuid": "u1", "description": "x", "status": "pending",
        "project": "Work", "priority": "M",
        "due": "۱۴۰۵-۰۶-۱۰", "due_gregorian": "20260901T000000Z",
    }])
    return m


def _idx(m, key):
    return m.index(0, m.visible_columns().index(key))


@pytest.mark.parametrize("key", ["project", "priority", "due"])
def test_only_the_three_columns_are_editable(model, key):
    assert model.flags(_idx(model, key)) & Qt.ItemFlag.ItemIsEditable
    for other in ("description", "id", "urgency", "status", "tags"):
        assert not (model.flags(_idx(model, other)) & Qt.ItemFlag.ItemIsEditable)


def test_edit_role_returns_the_raw_value(model):
    assert model.data(_idx(model, "project"), Qt.ItemDataRole.EditRole) == "Work"
    assert model.data(_idx(model, "priority"), Qt.ItemDataRole.EditRole) == "M"
    assert model.data(_idx(model, "due"), Qt.ItemDataRole.EditRole) == "20260901T000000Z"


@pytest.mark.parametrize(("key", "value", "current"), [
    ("project", "Home", "Work"),
    ("priority", "H", "M"),
    ("due", "2026-09-15", "20260901T000000Z"),
])
def test_setdata_emits_celledited_only_on_a_real_change(model, key, value, current):
    seen = []
    model.cellEdited.connect(lambda *a: seen.append(a))
    assert model.setData(_idx(model, key), value, Qt.ItemDataRole.EditRole) is True
    assert seen == [("u1", key, value)]
    # committing the value the cell already holds is a no-op
    seen.clear()
    assert model.setData(_idx(model, key), current, Qt.ItemDataRole.EditRole) is False
    assert seen == []


def test_delegates_reuse_existing_widgets(qtbot):
    from jtask_gui.widgets.jalali_date_picker import JalaliDatePicker
    from jtask_gui.widgets.table_delegates import (
        _DueDelegate,
        _PriorityDelegate,
        _ProjectDelegate,
    )
    from jtask_gui.widgets.task_table import TaskTable

    m = TaskTableModel()
    m.set_tasks([])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    cols = m.visible_columns()
    assert isinstance(tbl.itemDelegateForColumn(cols.index("project")), _ProjectDelegate)
    assert isinstance(tbl.itemDelegateForColumn(cols.index("priority")), _PriorityDelegate)
    d = tbl.itemDelegateForColumn(cols.index("due"))
    assert isinstance(d, _DueDelegate)
    ed = d.createEditor(tbl, None, m.index(0, 0))
    assert isinstance(ed, JalaliDatePicker)          # the calendar-system widget
    assert ed._edit.property("invalid") in (None, False)   # no premature error


def test_main_window_inline_edit_runs_one_modify(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["inline edit target", "project:Work"])
    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    w._inline_edit(tw.export(["1"])[0]["uuid"], "priority", "H")
    for _ in range(20):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    assert tw.export(["description:inline"])[0]["priority"] == "H"
