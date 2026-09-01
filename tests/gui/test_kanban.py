"""N-D: the Kanban board — grouping, buckets, and drag→write mapping."""

from __future__ import annotations

import pytest


def _tasks():
    return [
        {"uuid": "t1", "description": "todo", "status": "pending",
         "project": "Work", "priority": "H"},
        {"uuid": "t2", "description": "doing", "status": "pending",
         "start": "20260901T000000Z", "project": "Work"},
        {"uuid": "t3", "description": "done", "status": "completed", "project": "Home"},
        {"uuid": "t4", "description": "waiting", "status": "waiting"},
    ]


def test_bucket_maps_to_real_taskwarrior_state():
    from jtask_gui.widgets.kanban_view import _bucket

    a, b, c, d = _tasks()
    assert _bucket(a, "status") == "todo"
    assert _bucket(b, "status") == "doing"       # has a `start` timestamp
    assert _bucket(c, "status") == "done"
    assert _bucket(d, "status") == "waiting"
    assert _bucket(a, "priority") == "H"
    assert _bucket(a, "project") == "Work"


@pytest.fixture
def board(qtbot):
    from jtask_gui.widgets.kanban_view import KanbanView

    kv = KanbanView("dark")
    qtbot.addWidget(kv)
    kv.set_tasks(_tasks())
    return kv


def test_status_board_has_four_columns_with_the_right_counts(board):
    got = {c.col_id: c._cards.count() - 1 for c in board._columns}
    assert got == {"todo": 1, "doing": 1, "done": 1, "waiting": 1}


def test_waiting_column_is_not_a_drop_target(board):
    waiting = next(c for c in board._columns if c.col_id == "waiting")
    assert not waiting.acceptDrops()
    todo = next(c for c in board._columns if c.col_id == "todo")
    assert todo.acceptDrops()


def test_grouping_switch_rebuilds_columns(board):
    board._on_grouping("priority")
    assert [c.col_id for c in board._columns] == ["", "L", "M", "H"]
    board._on_grouping("project")
    assert {c.col_id for c in board._columns} == {"", "Home", "Work"}


def test_drop_emits_taskmoved_only_on_a_real_change(board):
    moved = []
    board.taskMoved.connect(lambda *a: moved.append(a))
    board._on_dropped("t1", "doing")     # todo -> doing: a change
    board._on_dropped("t1", "todo")      # already todo: no-op
    assert moved == [(_tasks()[0], "status", "doing")]


@pytest.mark.parametrize(("cur", "target", "verb", "mods"), [
    ("todo", "doing", "start", []),
    ("todo", "done", "done", []),
    ("doing", "done", "done", []),
    ("doing", "todo", "stop", []),
    ("done", "todo", "modify", ["status:pending"]),
])
def test_status_move_mapping(qapp, qtbot, tw_env, cur, target, verb, mods, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    calls = []
    monkeypatch.setattr(w, "_write", lambda fn, msg: calls.append(fn))

    task = {"uuid": "x", "status": "completed" if cur == "done" else "pending"}
    if cur == "doing":
        task["start"] = "20260901T000000Z"
    w._kanban_move(task, "status", target)

    import functools

    from jtask import taskwarrior

    assert calls, "no write issued"
    f = calls[0]
    assert isinstance(f, functools.partial) and f.func is taskwarrior.command
    assert f.args == ([task["uuid"]], verb, mods)


def test_priority_and_project_moves_are_one_modify(qapp, qtbot, tw_env, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    calls = []
    monkeypatch.setattr(w, "_write", lambda fn, msg: calls.append(fn.args))

    w._kanban_move({"uuid": "x"}, "priority", "H")
    w._kanban_move({"uuid": "x"}, "project", "Work.Admin")
    assert calls == [
        (["x"], "modify", ["priority:H"]),
        (["x"], "modify", ["project:Work.Admin"]),
    ]


def test_board_toggle_switches_the_stacked_widget(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    assert w._content.currentIndex() == 0
    w._board_action.setChecked(True)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    assert w._content.currentIndex() == 2
    assert not w._group_combo.isEnabled()
    w._board_action.setChecked(False)
    qapp.processEvents()
    assert w._content.currentIndex() == 0
