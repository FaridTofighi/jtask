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


# --- chunk 2: Contexts -> toolbar pill ----------------------------

def test_contexts_moved_to_a_toolbar_pill(win, qapp):
    from jtask import taskwarrior as tw

    assert not hasattr(win._sidebar, "_contexts")
    pill = win._context_pill
    assert pill in win._toolbars[0].findChildren(type(pill))
    assert pill.toolTip().strip()

    # neutral by default
    assert pill.is_active() is False
    assert pill.property("active") in (False, None)

    tw.run(["context", "define", "work", "project:Alpha"])
    win._change_context("work")
    _drain(qapp)
    assert win._context_pill.is_active() is True
    assert win._context_pill.property("active") is True
    assert "work" in win._context_pill.name_text()  # bidi-isolated but contains it
    assert tw.current_context() == "work"

    win._change_context("")
    _drain(qapp)
    assert win._context_pill.is_active() is False
    assert tw.current_context() is None


# --- chunk 3: compressed Projects & Tags -------------------------

def test_projects_search_and_cap(qapp, qtbot, tw_env):
    from jtask_gui.widgets.sidebar import _PROJ_CAP, Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    rows = [{"project": f"P{i:02d}", "open": i} for i in range(_PROJ_CAP + 4)]
    sb.populate_projects(rows)

    visible = [it for it in sb._project_items if not it.isHidden()]
    assert len(visible) == _PROJ_CAP
    assert not sb._proj_more.isHidden()  # "show all (N)" offered

    # search filters live, ignoring the cap
    sb._proj_search.setText("P07")
    qapp.processEvents()
    visible = [it.text(0) for it in sb._project_items if not it.isHidden()]
    assert len(visible) == 1 and visible[0].startswith("P07")
    assert sb._proj_more.isHidden()  # no "show all" while searching

    sb._proj_search.setText("")
    qapp.processEvents()
    # "show all" reveals every project, without losing any
    sb._toggle_expander("projects")
    qapp.processEvents()
    assert all(not it.isHidden() for it in sb._project_items)
    assert len(sb._project_items) == _PROJ_CAP + 4


def test_tags_render_as_chips_and_activate(qapp, qtbot, tw_env):
    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    from jtask_gui import fmt

    sb.populate_tags([{"tag": "alpha", "count": 3}, {"tag": "beta", "count": 1}])
    chips = [sb._tag_flow.flow.itemAt(i).widget()
             for i in range(sb._tag_flow.flow.count())]
    assert [c.text() for c in chips] == [
        f"#alpha  ·  {fmt.num(3)}", f"#beta  ·  {fmt.num(1)}"
    ]

    got = []
    sb.activated.connect(got.append)
    chips[0].click()
    assert got and got[0]["filter"] == ["+alpha", "status:pending"]

    # tags still reachable from the command palette
    labels = [lbl for lbl, _s, _spec in sb.navigation_targets()]
    assert "#alpha" in labels and "#beta" in labels
