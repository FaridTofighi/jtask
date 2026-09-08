"""d4 — toolbar: grouped, every control has a real tooltip, overflow is flat.

Screenshots can't show tooltips, so this is the explicit check the audit asked
for.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QMenu, QToolButton


@pytest.fixture
def win(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    return w


def _toolbar_actions(w):
    seen = []
    for tb in w._toolbars:
        for act in tb.actions():
            if act.isSeparator():
                continue
            widget = tb.widgetForAction(act)
            if isinstance(widget, QToolButton) and widget.menu():
                # the button itself + its (flat) menu entries
                seen.append(("button", widget))
                for sub in widget.menu().actions():
                    if not sub.isSeparator():
                        seen.append(("menu", sub))
            elif widget is None:  # a real QAction shown as a toolbar button
                seen.append(("action", act))
    return seen


def test_every_toolbar_control_has_a_tooltip(win):
    missing = []
    for kind, obj in _toolbar_actions(win):
        tip = obj.toolTip().strip()
        if not tip:
            missing.append(f"{kind}: {obj.text() or obj!r}")
    assert not missing, f"toolbar controls without a tooltip: {missing}"


def test_descriptive_tooltips_are_not_just_the_label(win):
    """The gear + the merged view control must say what they do, not repeat
    their name."""
    assert win._settings_action.toolTip().strip()
    assert win._settings_action.toolTip().strip() != win._settings_action.text().strip()
    assert win._view_btn.toolTip().strip()
    assert win._view_btn.toolTip().strip() != win._view_btn.text().strip()


def test_overflow_menu_is_flat_and_miscellaneous(win):
    """The 'more' menu is one level and holds only odds and ends — the console
    toggle, the theme quick-toggle and the shortcut sheet."""
    menu = win._more_btn.menu()
    assert menu is not None
    for act in menu.actions():
        assert not isinstance(act.menu(), QMenu), f"{act.text()} opens a submenu"
    labels = {a.text() for a in menu.actions() if not a.isSeparator()}
    assert labels == {
        win._console_action.text(),
        win._theme_action.text(),
        win._shortcuts_action.text(),
    }


def test_overflow_actions_still_wired(win):
    """Relocating an action into the menu must not drop its callback."""
    assert win._console_action.receivers(win._console_action.toggled) >= 1
    assert win._theme_action.receivers(win._theme_action.triggered) >= 1
    assert win._shortcuts_action.receivers(win._shortcuts_action.triggered) >= 1
    for act in (win._console_action, win._theme_action, win._shortcuts_action):
        assert act.isEnabled()


def test_toolbar_is_visually_grouped(win):
    """Row two separates its clusters (create / undo / data / view / config)."""
    row2 = win._toolbars[1]
    separators = [a for a in row2.actions() if a.isSeparator()]
    assert len(separators) >= 4, "row-two clusters are not separated"
