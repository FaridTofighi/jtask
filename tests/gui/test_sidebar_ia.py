"""Sidebar information-architecture redesign — Reports & Charts, Saved filters
and Contexts move to the toolbar; Projects and Tags stay in the sidebar but
compress (search + capped list / chip flow + "show all").

The headline guard is `test_every_relocated_capability_still_reachable` — an
explicit "nothing was lost" check: every action previously reachable from the
sidebar must still be reachable from its new home.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def win(qapp, qtbot, tw_env):
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


# --- chunk 1: Reports & Charts -------------------------------------

def test_reports_moved_to_a_toolbar_action(win, qapp):
    # gone from the sidebar
    assert not hasattr(win._sidebar, "_reports")
    # reachable from the toolbar, opening the same reports page
    assert win._reports_action in win._toolbars[1].actions()
    assert win._reports_action.toolTip().strip()
    assert win._reports_action.toolTip().strip() != win._reports_action.text().strip()
    win._reports_action.trigger()
    _drain(qapp)
    assert win._content.currentIndex() == 1
    # command palette enumerates every enabled QAction with text -> included
    assert win._reports_action.isEnabled() and win._reports_action.text().strip()
    cmds = win._collect_commands()
    assert any("chart" in c.label.lower() for c in cmds)
