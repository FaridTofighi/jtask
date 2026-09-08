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


# --- chunk 3: Settings reorg + theme off the toolbar -----------

def test_theme_is_off_the_toolbar_but_in_two_places(win, qapp):
    from jtask_gui.settings_dialog import SettingsDialog

    assert win._theme_action not in win._toolbars[1].actions()
    # (a) the overflow quick-toggle
    before = win.settings.theme
    win._theme_action.trigger()
    _drain(qapp)
    assert win.settings.theme != before
    # (b) the Settings › Interface control — same setting
    dlg = SettingsDialog(win.settings, win)
    assert dlg._theme.currentData() == win.settings.theme
    idx = dlg._theme.findData(before)
    dlg._theme.setCurrentIndex(idx)
    dlg._accept()
    assert win.settings.theme == before


def test_settings_has_two_sections_with_every_relocated_tool(win, qapp):
    from jtask_gui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(win.settings, win)
    dlg.show()
    for i in range(dlg._tw_stack.count()):
        dlg._load_tw_panel(i)
    _drain(qapp)

    assert dlg._tabs.count() == 2
    # 5 managers + 3 tools = 8 panels, one click each
    assert dlg._tw_stack.count() == 8
    assert len(dlg._tw_managers) == 5
    # the tool panels exist and populate
    assert "task" in dlg._diag._text.toPlainText().lower()
    assert dlg._help._table.rowCount() > 0
    dlg._calc._in.setText("2 + 2")
    dlg._calc._go()
    _drain(qapp)
    assert "4" in dlg._calc._out.text()


def test_manage_and_tools_dialogs_are_gone(win):
    assert not hasattr(win, "_manage_action")
    assert not hasattr(win, "_tools_action")
    assert not hasattr(win, "_open_manager")
    assert not hasattr(win, "_open_tools")
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("jtask_gui.widgets.manager_dialog")
