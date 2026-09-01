"""Mission n1 — shell restructure: surfaces, header, selection, status bar.

These lock the P0 visual-structure decisions so a later refactor can't quietly
flatten the app back into one plane.
"""

from __future__ import annotations

import re

import pytest

from jtask_gui import theme


@pytest.fixture
def win(qapp, qtbot, tw_env):
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
    return w


def _qss() -> str:
    return re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)


def test_content_sits_in_a_framed_card(win):
    frame = win.centralWidget()
    assert frame.objectName() == "ContentFrame"
    m = frame.layout().contentsMargins()
    # a real gutter of window background on every side
    assert min(m.left(), m.top(), m.right(), m.bottom()) >= 8
    assert "QWidget#ContentFrame" in _qss()


def test_sidebar_has_a_separating_edge():
    m = re.search(r"QTreeWidget#Sidebar\s*\{([^}]*)\}", _qss())
    assert m and "border-right" in m.group(1)


def test_status_binary_is_not_loud_when_healthy():
    m = re.search(r"QLabel#StatusOk\s*\{([^}]*)\}", _qss())
    assert m and "@success@" not in m.group(1)  # version string reads as muted
    assert "QLabel#StatusCount" in _qss()


def test_filter_field_has_a_leading_search_affordance(win):
    acts = win._filter_bar._edit.actions()
    assert acts, "filter field has no leading action"
    assert win._filter_bar._search_action in acts


def test_new_task_is_the_one_emphasised_toolbar_action(win):
    btn = win._toolbars[1].widgetForAction(win._add_full_action)
    assert btn is not None and btn.objectName() == "PrimaryAction"
    assert "QToolButton#PrimaryAction" in _qss()


def test_quick_add_preview_is_hidden_at_rest(win):
    assert win._quick_add._preview.isHidden()
    win._quick_add._edit.setText("buy milk +errand")
    assert not win._quick_add._preview.isHidden()
    win._quick_add._edit.clear()
    assert win._quick_add._preview.isHidden()
