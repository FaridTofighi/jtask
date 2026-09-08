"""N-B: starred tasks (+starred tag) + sidebar folders & counts."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

# --- starred: the +starred tag round-trips through plain `task` --------

def test_starred_tag_roundtrips_through_the_cli(tw_env):
    from jtask import taskwarrior as tw

    tw.add(["important thing", "+starred", "project:Work"])
    tw.add(["ordinary thing", "project:Work"])
    tw.refresh_lookups()

    starred = [t["description"] for t in tw.export(["+starred"])]
    assert starred == ["important thing"]

    # un-star from the CLI, jtask sees it gone
    uuid = tw.export(["+starred"])[0]["uuid"]
    tw.command([uuid], "modify", ["-starred"])
    assert tw.export(["+starred"]) == []


def test_starred_is_hidden_from_the_tag_surfaces():
    from jtask import reports
    from jtask_gui.models.column_spec import _tags

    tasks = [{"tags": ["starred", "work", "ACTIVE"]}]
    assert [r["tag"] for r in reports.shape_tags(tasks)] == ["work"]
    assert _tags(tasks[0]) == "#work"          # no #starred chip


# --- the star column -------------------------------------------------

@pytest.fixture
def table(qtbot):
    from jtask_gui.models.task_model import TaskTableModel
    from jtask_gui.widgets.task_table import TaskTable

    m = TaskTableModel()
    m.set_tasks([
        {"id": 1, "uuid": "u1", "description": "a", "status": "pending", "tags": ["starred"]},
        {"id": 2, "uuid": "u2", "description": "b", "status": "pending", "tags": []},
    ])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    return tbl, m


def test_star_column_click_toggles(table):
    tbl, m = table
    si = m.visible_columns().index("starred")
    assert not m.data(m.index(0, si), Qt.ItemDataRole.DecorationRole).isNull()

    got = []
    m.starToggled.connect(lambda *a: got.append(a))
    tbl._on_click(m.index(0, si))   # currently starred -> request unstar
    tbl._on_click(m.index(1, si))   # currently not -> request star
    assert got == [("u1", False), ("u2", True)]


def test_ctrl_dot_toggles_star_on_the_selection(table):
    tbl, m = table
    got = []
    m.starToggled.connect(lambda *a: got.append(a))
    tbl.selectRow(0)
    sel = tbl.selected_uuids()[0]
    tbl.toggle_star_on_selection()
    assert got and got[0][0] == sel


def test_detail_panel_star_reflects_and_emits(qtbot):
    from jtask_gui.widgets.detail_panel import DetailPanel

    d = DetailPanel()
    qtbot.addWidget(d)
    d.load_task({"uuid": "u9", "id": 9, "description": "x", "tags": ["starred"]})
    assert d._star.isChecked()

    got = []
    d.starToggled.connect(lambda *a: got.append(a))
    d._star.setChecked(False)
    d._on_star(False)
    assert got == [("u9", False)]


def test_starred_quick_view_exists():
    from jtask_gui.widgets.sidebar import QUICK_VIEWS

    keys = {spec["key"]: spec for _l, _g, spec in QUICK_VIEWS}
    assert "starred" in keys
    assert keys["starred"]["filter"] == ["+starred", "status:pending"]


# --- saved-filter dropdown: folders + counts ----------------------

def test_saved_filter_names_with_a_slash_nest_in_a_folder(qtbot):
    from jtask_gui.widgets.saved_filter_menu import SavedFilterMenu

    m = SavedFilterMenu()
    qtbot.addWidget(m)
    m.set_data({
        "Work/Urgent": "+urgent project:Work",
        "Work/Review": "+review",
        "Personal": "project:Home",
    }, {}, [])
    tree = m._tree
    top = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
    assert "Work" in top and "Personal" in top
    work = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
               if tree.topLevelItem(i).text(0) == "Work")
    assert {work.child(i).text(0) for i in range(work.childCount())} == {"Urgent", "Review"}


def test_saved_filter_menu_shows_counts(qtbot):
    from jtask_gui import fmt
    from jtask_gui.widgets.saved_filter_menu import SavedFilterMenu

    m = SavedFilterMenu()
    qtbot.addWidget(m)
    m.set_data({"Personal": "project:Home"}, {"Personal": 7}, [])
    leaf = m._tree.topLevelItem(0)
    assert f"·  {fmt.num(7)}" in leaf.text(0)


def test_quick_view_counts_still_append(qtbot):
    from jtask_gui import fmt
    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.set_view_counts({"today": 3, "starred": 1})

    def label(needle):
        for it in sb._iter_items(sb._quick):
            if needle in it.text(0):
                return it.text(0)
        return ""

    row = label("امروز") or label("Today")
    assert f"·  {fmt.num(3)}" in row


def test_view_counts_worker_returns_ints(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["due today thing", "due:today"])
    tw.add(["starred thing", "+starred"])
    w = MainWindow(Settings())
    w.settings.save_filter("Mine", "+starred")
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    counts = w._view_counts()
    assert counts["starred"] == 1
    assert counts["Mine"] == 1
    assert all(isinstance(v, int) for v in counts.values())
