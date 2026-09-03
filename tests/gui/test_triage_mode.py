"""gtd-T: Triage Mode — one card at a time, reusing the board's drop actions."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings


@pytest.fixture(autouse=True)
def _en():
    from jtask_gui import i18n

    prev = i18n.lang()
    i18n.set_language("en")
    QSettings("jtask", "jtask-gui").clear()
    yield
    QSettings("jtask", "jtask-gui").clear()
    i18n.set_language(prev)


# --- the widget in isolation ---------------------------------

def test_column_buttons_are_the_boards_droppable_columns(qtbot):
    from jtask_gui.boards import builtin_board
    from jtask_gui.widgets.triage_view import TriageView

    tv = TriageView()
    qtbot.addWidget(tv)
    tv.start(builtin_board("gtd"), [{"uuid": "u1", "description": "x"}])
    labels = [b.text() for b in tv._col_buttons]
    assert labels == ["Next Actions", "Waiting For", "Someday / Maybe", "Done"]
    # Inbox (drop: none) is not offered as a target


def test_a_column_button_emits_the_compiled_drop_and_advances(qtbot):
    from jtask_gui.boards import builtin_board
    from jtask_gui.widgets.triage_view import TriageView

    tv = TriageView()
    qtbot.addWidget(tv)
    tv.start(builtin_board("gtd"),
             [{"uuid": "u1", "description": "a"}, {"uuid": "u2", "description": "b"}])
    got = []
    tv.decision.connect(lambda *a: got.append(a))
    next(b for b in tv._col_buttons if b.text() == "Someday / Maybe").click()
    assert got == [("u1", "modify", ["+someday", "-waiting"])]
    tv.advance()                                  # MainWindow does this after the write
    assert tv._counter.text() == "۲ of ۲"


def test_skip_advances_without_a_write(qtbot):
    from jtask_gui.boards import builtin_board
    from jtask_gui.widgets.triage_view import TriageView

    tv = TriageView()
    qtbot.addWidget(tv)
    tv.start(builtin_board("gtd"),
             [{"uuid": "u1", "description": "a"}, {"uuid": "u2", "description": "b"}])
    fired = []
    tv.decision.connect(lambda *a: fired.append(a))
    tv._skip.click()
    assert not fired and tv._counter.text() == "۲ of ۲"


def test_project_field_emits_the_assignment(qtbot):
    from jtask_gui.boards import builtin_board
    from jtask_gui.widgets.triage_view import TriageView

    tv = TriageView()
    qtbot.addWidget(tv)
    tv.start(builtin_board("gtd"), [{"uuid": "u1", "description": "a"}])
    got = []
    tv.projectAssigned.connect(lambda *a: got.append(a))
    tv._project.setText("Home.Kitchen")
    tv._project.returnPressed.emit()
    assert got == [("u1", "Home.Kitchen")]


def test_empty_queue_shows_the_completion_state(qtbot):
    from jtask_gui.boards import builtin_board
    from jtask_gui.widgets.triage_view import TriageView

    tv = TriageView()
    qtbot.addWidget(tv)
    tv.start(builtin_board("gtd"), [])
    assert tv.remaining() == 0
    assert not tv._card.isVisibleTo(tv)
    assert tv._done.isVisibleTo(tv)


def test_finishing_the_last_card_lands_on_the_completion_state(qtbot):
    from jtask_gui.boards import builtin_board
    from jtask_gui.widgets.triage_view import TriageView

    tv = TriageView()
    qtbot.addWidget(tv)
    tv.start(builtin_board("gtd"), [{"uuid": "u1", "description": "only one"}])
    tv.advance()
    assert tv._done.isVisibleTo(tv) and not tv._card.isVisibleTo(tv)


# --- wired into MainWindow ----------------------------------

@pytest.fixture
def win(qapp, qtbot, tw_env):
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    for x in ("reply to landlord", "buy milk", "call the bank"):
        tw.add([x])                                # all Inbox: no project, no tag
    tw.refresh_lookups()

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    return w


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()


def test_start_triage_loads_the_inbox(win, qapp):
    win._start_triage()
    _drain(qapp)
    assert win._content.currentIndex() == 3
    assert len(win._triage._queue) == 3


def test_a_decision_writes_through_the_undo_path_and_advances(win, qapp):
    from jtask import taskwarrior as tw

    win._start_triage()
    _drain(qapp)
    uuid = win._triage._uuid()
    next(b for b in win._triage._col_buttons if b.text() == "Waiting For").click()
    _drain(qapp)

    after = tw.export([uuid])[0]
    assert "waiting" in (after.get("tags") or [])
    assert win._triage._counter.text() == "۲ of ۳"     # advanced


def test_the_project_field_moves_a_card_out_of_the_inbox(win, qapp):
    from jtask import taskwarrior as tw

    win._start_triage()
    _drain(qapp)
    uuid = win._triage._uuid()
    win._triage._project.setText("Admin")
    win._triage._project.returnPressed.emit()
    _drain(qapp)
    assert tw.export([uuid])[0].get("project") == "Admin"


def test_exit_returns_to_the_previous_view(win, qapp):
    win._start_triage()
    _drain(qapp)
    win._triage.exited.emit()
    _drain(qapp)
    assert win._content.currentIndex() == 0


def test_board_column_triage_button_starts_triage_for_that_column(win, qapp, qtbot):
    from jtask_gui.boards import builtin_board

    win._board.set_board(builtin_board("gtd"))
    _drain(qapp)
    # the Inbox column (index 0) button
    win._board.triageRequested.emit(0)
    _drain(qapp)
    assert win._content.currentIndex() == 3
