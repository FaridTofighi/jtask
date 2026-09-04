"""Keyboard shortcuts on the selected task(s): timer start/stop, delete."""

from __future__ import annotations

import pytest


@pytest.fixture
def table(qtbot):
    from jtask_gui.models.task_model import TaskTableModel
    from jtask_gui.widgets.task_table import TaskTable

    m = TaskTableModel()
    m.set_tasks([
        {"id": 1, "uuid": "u1", "description": "one", "status": "pending"},
        {"id": 2, "uuid": "u2", "description": "two", "status": "pending"},
    ])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    tbl.resize(600, 200)
    return tbl


def test_ctrl_s_starts_and_ctrl_shift_s_stops_the_selected_task(table):
    events: list = []
    table.startStopRequested.connect(lambda u, s: events.append((u, s)))
    table.selectRow(0)
    sel = table.selected_uuids()[0]

    table._timer_shortcut(True)
    table._timer_shortcut(False)
    assert events == [(sel, True), (sel, False)]


def test_delete_key_asks_to_delete_the_selection(table):
    events: list = []
    table.deleteRequested.connect(events.append)
    table.selectRow(0)
    sel = table.selected_uuids()
    table._delete_shortcut()
    assert events == [sel]


def test_shortcuts_are_a_noop_with_no_selection(table):
    ss, dele = [], []
    table.startStopRequested.connect(lambda u, s: ss.append(u))
    table.deleteRequested.connect(dele.append)
    table.clearSelection()
    table._timer_shortcut(True)
    table._delete_shortcut()
    assert ss == [] and dele == []


def test_key_bindings_are_registered(table):
    from PyQt6.QtGui import QKeySequence, QShortcut

    seqs = {sc.key().toString() for sc in table.findChildren(QShortcut)}
    assert QKeySequence("Ctrl+S").toString() in seqs
    assert QKeySequence("Ctrl+Shift+S").toString() in seqs
    assert QKeySequence(QKeySequence.StandardKey.Delete).toString() in seqs


def test_delete_via_shortcut_goes_through_the_confirm_dialog(qapp, qtbot, tw_env, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["shortcut delete me"])
    seen = {}
    # _delete lives in mixins/task_lifecycle.py (MainWindow decomposition)
    monkeypatch.setattr(
        "jtask_gui.mixins.task_lifecycle.confirm",
        lambda *a, **k: seen.setdefault("asked", True) or True,
    )

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    w.show()
    for _ in range(40):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
        if w._table.model() and w._table.model().rowCount():
            break
    assert w._table.model().rowCount() >= 1

    from PyQt6.QtCore import QItemSelectionModel

    idx = w._table.model().index(0, 0)
    w._table.setCurrentIndex(idx)
    w._table.selectionModel().select(
        idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    )
    qapp.processEvents()
    assert w._table.selected_uuids()
    w._table._delete_shortcut()
    for _ in range(20):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    assert seen.get("asked") is True                       # confirm dialog shown
    rows = tw.export(["description:shortcut"])
    assert rows and rows[0]["status"] == "deleted"
