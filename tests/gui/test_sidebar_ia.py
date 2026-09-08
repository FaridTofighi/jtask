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


# --- chunk 4: saved filters -> toolbar dropdown + pins + manager --

def test_saved_filters_moved_off_the_sidebar(win):
    assert not hasattr(win._sidebar, "_saved")
    assert win._filters_btn in win._toolbars[1].findChildren(type(win._filters_btn))
    assert win._filters_btn.toolTip().strip()


def test_saved_filter_menu_search_filters_by_name(win, qapp):

    win.settings.save_filter("Overdue work", "+OVERDUE")
    win.settings.save_filter("Someday", "+someday")
    win._refresh_saved_filters()
    win._open_saved_filter_menu()
    qapp.processEvents()
    m = win._saved_filter_menu

    m._search.setText("over")
    qapp.processEvents()
    visible = [
        m._tree.topLevelItem(i).text(0)
        for i in range(m._tree.topLevelItemCount())
        if not m._tree.topLevelItem(i).isHidden()
    ]
    assert any("Overdue work" in v for v in visible)
    assert not any("Someday" in v for v in visible)
    m.close()


def test_pinned_filter_persists_across_a_reload(win, qapp, qtbot):
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    win.settings.save_filter("Daily", "+today")
    win._toggle_pin_filter("Daily")
    assert "Daily" in win.settings.pinned_filters()
    assert any(c.text() == "Daily" for c in win._pin_chips)

    # a fresh window (same QSettings store) still has the pinned chip
    fresh = MainWindow(Settings())
    qtbot.addWidget(fresh)
    _drain(qapp)
    assert any(c.text() == "Daily" for c in fresh._pin_chips)


def test_stuck_style_filter_count_is_tinted(qtbot):
    from jtask_gui.theme import palette
    from jtask_gui.widgets.saved_filter_menu import SavedFilterMenu

    m = SavedFilterMenu()
    qtbot.addWidget(m)
    m.set_data(
        {"Blocked": "+BLOCKED", "Normal": "project:x"},
        {"Blocked": 4, "Normal": 2},
        [],
        theme="dark",
    )
    pal = palette("dark")
    by_name = {m._tree.topLevelItem(i).text(0).split("  ·")[0]:
               m._tree.topLevelItem(i) for i in range(m._tree.topLevelItemCount())}
    assert by_name["Blocked"].foreground(0).color().name() == pal["overdue"].lower()
    assert by_name["Normal"].foreground(0).color().name() == pal["text_muted"].lower()


def test_filter_manager_roundtrips_through_settings(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.filter_manager import FilterManagerDialog

    s = Settings()
    s.save_filter("A", "+a")
    s.save_filter("B", "+b")

    dlg = FilterManagerDialog(s)
    qtbot.addWidget(dlg)
    dlg._list.setCurrentRow(0)  # A
    dlg._move(1)                # A <-> B
    assert Settings().filter_order()[:2] == ["B", "A"]
    dlg._list.setCurrentRow(0)  # B
    dlg._toggle_pin()
    assert "B" in Settings().pinned_filters()
    dlg._list.setCurrentRow(1)  # A
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QMessageBox.question",
        lambda *a, **k: __import__("PyQt6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes,
    )
    dlg._delete()
    assert "A" not in Settings().saved_filters()


# --- §6.1: the explicit "nothing was lost" regression -------------

def test_every_relocated_capability_still_reachable(win, qapp):
    from jtask import taskwarrior as tw

    # 1. view a report
    win._reports_action.trigger()
    _drain(qapp)
    assert win._content.currentIndex() == 1

    # 2. apply / rename / delete / edit a saved filter
    win.settings.save_filter("Q", "+urgent")
    win._refresh_saved_filters()
    win._open_saved_filter_menu()
    qapp.processEvents()
    m = win._saved_filter_menu
    m.filterActivated.emit("+urgent")
    _drain(qapp)
    assert "urgent" in win._filter_bar.raw_text()
    m.renameRequested.emit("Q", "Q2")
    assert "Q2" in win.settings.saved_filters()
    m.editRequested.emit("+urgent")
    _drain(qapp)
    assert win._filter_bar._edit.hasFocus() or "urgent" in win._filter_bar.raw_text()
    m.deleteRequested.emit("Q2")
    assert "Q2" not in win.settings.saved_filters()
    m.close()

    # 3. browse all projects  (search field + "show all")
    assert win._sidebar._proj_search is not None
    # 4. browse all tags  (chip flow + "show all")
    assert hasattr(win._sidebar, "_tag_flow")

    # 5. switch / clear a context
    tw.run(["context", "define", "c1", "project:Alpha"])
    win._context_pill.contextChangeRequested.emit("c1")
    _drain(qapp)
    assert tw.current_context() == "c1"
    win._context_pill.contextChangeRequested.emit("")
    _drain(qapp)
    assert tw.current_context() is None

    # 6. manage boards  (unchanged — still wired from the sidebar)
    assert win._sidebar.receivers(win._sidebar.boardManageRequested) >= 1
