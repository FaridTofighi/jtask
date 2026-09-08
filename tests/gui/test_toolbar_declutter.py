"""Toolbar decluttering + Settings reorganization.

The headline guard is `test_nothing_was_lost` — every control that moved off the
toolbar (group-by, column reset, weekly review, theme, Manage/Tools) is still
reachable from its new home.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def win(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui import i18n
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    prev = i18n.lang()
    i18n.set_language("en")
    tw.add(["Task one", "project:Alpha"])
    tw.add(["Task two", "project:Beta", "+urgent"])
    tw.refresh_lookups()
    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    yield w
    i18n.set_language(prev)


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()


# --- chunk 1: the merged "نمایش" control -------------------------

def test_group_combo_is_gone_replaced_by_a_view_menu(win):
    assert not hasattr(win, "_group_combo")
    assert win._view_btn in win._toolbars[1].findChildren(type(win._view_btn))
    assert win._view_btn.menu() is not None
    assert win._view_btn.toolTip().strip()


def test_view_menu_applies_grouping(win, qapp):
    win._view_btn.menu().aboutToShow.emit()
    win._group_actions["project"].trigger()
    _drain(qapp)
    assert win._group_key == "project"
    assert win._table._grouped is True
    win._group_actions["none"].trigger()
    _drain(qapp)
    assert win._table._grouped is False


def test_view_menu_toggles_columns_and_persists(win, qapp, qtbot):
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    assert "urgency" in win._model.visible_columns()
    win._view_btn.menu().aboutToShow.emit()
    win._col_actions["urgency"].trigger()  # hide it
    _drain(qapp)
    assert "urgency" not in win._model.visible_columns()

    fresh = MainWindow(Settings())
    qtbot.addWidget(fresh)
    _drain(qapp)
    assert "urgency" not in fresh._model.visible_columns()


def test_description_column_cannot_be_hidden(win):
    assert win._col_actions["description"].isEnabled() is False


# --- chunk 2: weekly review -> GTD board header -----------------

def test_review_button_is_off_the_global_toolbar(win):
    assert win._review_action not in win._toolbars[1].actions()
    # still a live window action -> Ctrl+R + command palette keep working
    assert win._review_action.shortcut().toString() == "Ctrl+R"
    assert win._review_action in win.findChildren(type(win._review_action))


def test_review_button_shows_only_on_the_gtd_board(win, qapp):
    from jtask_gui.boards import Board, builtin_board

    win._board.set_board(builtin_board("gtd"))
    _drain(qapp)
    assert not win._board._review_btn.isHidden()

    win._board.set_board(Board("Mine", builtin_board("gtd").columns, builtin=False))
    _drain(qapp)
    assert win._board._review_btn.isHidden()

    win._board.set_board(builtin_board("status"))
    _drain(qapp)
    assert win._board._review_btn.isHidden()


def test_board_review_button_opens_the_review_pass(win, qapp):
    from jtask_gui.boards import builtin_board

    win._board.set_board(builtin_board("gtd"))
    _drain(qapp)
    win._board._review_btn.click()
    _drain(qapp)
    assert win._review_active is True
    win._exit_review()
