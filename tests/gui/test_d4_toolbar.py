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
    """The frequently-confused ones (Settings, Manage, Tools) must say what they
    do, not repeat their name."""
    for name in ("_settings_action", "_manage_action", "_tools_action"):
        act = getattr(win, name)
        assert act.toolTip().strip() and act.toolTip().strip() != act.text().strip(), name


def test_overflow_menu_is_flat(win):
    """Resolution 3: the 'more' menu is one level — no nested submenus."""
    menu = win._more_btn.menu()
    assert menu is not None
    for act in menu.actions():
        assert not isinstance(act.menu(), QMenu), f"{act.text()} opens a submenu"
    # and it holds exactly the rarely-used entry points
    labels = {a.text() for a in menu.actions() if not a.isSeparator()}
    assert labels == {win._manage_action.text(), win._tools_action.text()}


def test_overflow_actions_still_wired(win):
    """Relocating an action into the menu must not drop its callback (checked
    without firing the modal dialogs)."""
    for act in (win._manage_action, win._tools_action):
        assert act.receivers(act.triggered) >= 1, f"{act.text()} has no handler"
        assert act.isEnabled()


def test_toolbar_is_visually_grouped(win):
    """Row two separates its clusters (create / undo / data / view / config)."""
    row2 = win._toolbars[1]
    separators = [a for a in row2.actions() if a.isSeparator()]
    assert len(separators) >= 4, "row-two clusters are not separated"
