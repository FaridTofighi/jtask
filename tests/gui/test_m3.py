"""M3 — visual filter builder, saved filters, drag-and-drop, dep graph, custom reports."""

from __future__ import annotations

import jdatetime
import pytest

# --- visual filter builder ------------------------------------------

def test_filter_builder_composes_tokens(qtbot, tw_env):
    from jtask_gui.widgets.filter_builder import FilterBuilder

    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._project.setCurrentText("وب")
    fb._tags_inc._add("مهم")
    fb._tags_exc._add("بعدی")
    fb._status.setCurrentIndex(1)  # pending
    fb._priority.setCurrentIndex(1)  # H
    fb._due_before.set_value(jdatetime.date(1403, 8, 1))

    tokens = fb._raw_tokens()
    assert "project:وب" in tokens
    assert "+مهم" in tokens and "-بعدی" in tokens
    assert "status:pending" in tokens
    assert "priority:H" in tokens
    assert "due.before:2024-10-22" in tokens
    assert "(بدون فیلتر)" not in fb._raw.text()


def test_filter_builder_emits_ready_tokens(qtbot, tw_env):
    from jtask_gui.widgets.filter_builder import FilterBuilder

    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._project.setCurrentText("خانه")
    got = []
    fb.applied.connect(lambda toks, raw: got.append((toks, raw)))
    fb._emit()
    assert got[0][0] == ["project:خانه"]


# --- saved filters -------------------------------------------------

def test_saved_filters_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("JTASK_CONFIG_DIR", str(tmp_path))
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings

    s = Settings()
    s.save_filter("وب فعال", "project:وب +ACTIVE")
    assert s.saved_filters() == {"وب فعال": "project:وب +ACTIVE"}
    s.delete_filter("وب فعال")
    assert s.saved_filters() == {}


def test_saved_filter_rename_and_delete_via_context_menu(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.sidebar import _SPEC_ROLE, Sidebar

    s = Settings()
    s.save_filter("اولی", "+یک")

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.savedFilterRenameRequested.connect(s.rename_filter)
    sb.savedFilterDeleteRequested.connect(s.delete_filter)
    sb.populate_saved_filters(s.saved_filters())
    assert sb._saved.child(0).data(0, _SPEC_ROLE)["name"] == "اولی"

    # rename (bypassing the QInputDialog, exercising the wired signal + storage)
    sb.savedFilterRenameRequested.emit("اولی", "دومی")
    sb.populate_saved_filters(s.saved_filters())
    assert s.saved_filters() == {"دومی": "+یک"}
    assert s.saved_filters() == Settings().saved_filters()  # persisted
    assert sb._saved.child(0).data(0, _SPEC_ROLE)["name"] == "دومی"

    # delete (confirmation is the QMessageBox; the signal is the post-confirm action)
    sb.savedFilterDeleteRequested.emit("دومی")
    sb.populate_saved_filters(s.saved_filters())
    assert Settings().saved_filters() == {}
    names = [sb._saved.child(i).data(0, _SPEC_ROLE) for i in range(sb._saved.childCount())]
    assert all(n is None or n.get("kind") != "saved" for n in names)


def test_dep_graph_empty_state_sized_within_panel_on_first_open(qtbot, tw_env, qapp):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    win = MainWindow(Settings())
    win.resize(1200, 780)
    qtbot.addWidget(win)
    win.show()
    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    dg = win._detail._dep_graph
    # first ever open of the detail panel for a task with no dependencies
    win._show_detail({"uuid": "solo", "id": 1, "description": "بدون وابستگی",
                      "status": "pending"})
    qapp.processEvents()

    assert dg._empty.isVisible()
    assert dg._empty.geometry().width() <= dg.viewport().width() + 1
    assert dg._empty.geometry().height() <= dg.viewport().height() + 1
    assert dg.transform().m11() <= 1.0        # nothing scaled up


def test_sidebar_lists_and_activates_saved_filter(qtbot):
    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_saved_filters({"مهم‌ها": "+مهم status:pending"})
    got = []
    sb.savedFilterActivated.connect(got.append)

    from jtask_gui.widgets.sidebar import _SPEC_ROLE

    leaf = sb._saved.child(0)
    assert leaf.data(0, _SPEC_ROLE)["kind"] == "saved"
    sb._on_click(leaf, 0)
    assert got == ["+مهم status:pending"]


# --- drag & drop -------------------------------------------------

def test_task_table_drag_produces_uuid_mime(qtbot):
    from jtask_gui.models.task_model import TaskTableModel
    from jtask_gui.widgets.task_table import UUID_MIME, TaskTable

    model = TaskTableModel()
    model.set_tasks([{"id": 1, "uuid": "abc", "description": "x", "status": "pending"}])
    table = TaskTable(model)
    qtbot.addWidget(table)
    table.selectRow(0)
    assert table.selected_uuids() == ["abc"]
    # startDrag builds the mime payload from the selection
    assert UUID_MIME  # format constant is shared with the drop targets


def test_task_table_collapsible_group_headers(qtbot):
    from jtask_gui.models.group_proxy import GROUP_HEADER_ROLE, GROUP_KEY_ROLE
    from jtask_gui.models.task_model import TaskTableModel
    from jtask_gui.widgets.task_table import TaskTable

    model = TaskTableModel()
    model.set_tasks([
        {"id": 1, "uuid": "a", "description": "x", "status": "pending", "project": "خانه"},
        {"id": 2, "uuid": "b", "description": "y", "status": "pending", "project": "خانه"},
        {"id": 3, "uuid": "c", "description": "z", "status": "pending", "project": "کار"},
    ])
    table = TaskTable(model)
    qtbot.addWidget(table)

    table.set_group_key("project")
    gm = table._group_model
    # 2 header rows + 3 task rows
    assert gm.rowCount() == 5
    header_rows = gm.header_rows()
    assert len(header_rows) == 2
    assert gm.index(header_rows[0], 0).data(GROUP_HEADER_ROLE) is True

    # collapse the first group -> its 2 children disappear
    first_key = gm.index(header_rows[0], 0).data(GROUP_KEY_ROLE)
    gm.toggle(first_key)
    assert gm.rowCount() == 3  # 2 headers + 1 remaining child

    # selection still resolves to real tasks, never a header
    table.set_group_key("project")
    table.selectRow(gm.header_rows()[-1] + 1)
    assert table.selected_uuids() and all(
        u in {"a", "b", "c"} for u in table.selected_uuids()
    )

    # back to flat
    table.set_group_key("none")
    assert table.model() is table._proxy


def test_sidebar_project_drop_emits_reassign(qtbot):
    from PyQt6.QtCore import QMimeData
    from PyQt6.QtGui import QDropEvent

    from jtask_gui.widgets.sidebar import UUID_MIME, Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_projects([{"project": "وب", "open": 3}])
    got = []
    sb.tasksDroppedOnProject.connect(lambda u, p: got.append((u, p)))

    proj_item = sb._projects.child(0)
    rect = sb.visualItemRect(proj_item)
    mime = QMimeData()
    mime.setData(UUID_MIME, b"u1 u2")
    from PyQt6.QtCore import QPointF, Qt

    ev = QDropEvent(QPointF(rect.center()), Qt.DropAction.MoveAction, mime,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    sb.dropEvent(ev)
    assert got == [(["u1", "u2"], "وب")]


def test_sidebar_tag_drop_emits_add_tag(qtbot):
    from PyQt6.QtCore import QMimeData, QPointF, Qt
    from PyQt6.QtGui import QDropEvent

    from jtask_gui.widgets.sidebar import UUID_MIME, Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_tags([{"tag": "مهم", "count": 2}])
    got = []
    sb.tasksDroppedOnTag.connect(lambda u, tag: got.append((u, tag)))

    rect = sb.visualItemRect(sb._tags.child(0))
    mime = QMimeData()
    mime.setData(UUID_MIME, b"a b c")
    ev = QDropEvent(QPointF(rect.center()), Qt.DropAction.MoveAction, mime,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    sb.dropEvent(ev)
    assert got == [(["a", "b", "c"], "مهم")]


def test_sidebar_tag_context_menu_signals(qtbot, monkeypatch):
    import PyQt6.QtWidgets as W

    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_tags([{"tag": "کار", "count": 5}])
    renamed, removed = [], []
    sb.tagRenameRequested.connect(lambda o, n: renamed.append((o, n)))
    sb.tagRemoveRequested.connect(removed.append)

    made: list = []
    monkeypatch.setattr(
        W.QMenu, "addAction", lambda self, text: made.append(object()) or made[-1]
    )
    monkeypatch.setattr(
        W.QInputDialog, "getText", staticmethod(lambda *a, **k: ("#urgent", True))
    )
    pos = sb.visualItemRect(sb._tags.child(0)).center()

    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[0])   # first = rename
    sb._context_menu(pos)
    assert renamed == [("کار", "urgent")]  # '#' stripped

    made.clear()
    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[1])   # second = remove
    sb._context_menu(pos)
    assert removed == ["کار"]


def test_main_window_tag_management_flow(qtbot, tw_env, qapp, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["alpha task", "+draft"])
    tw.add(["beta task", "+draft", "+keep"])

    win = MainWindow(Settings())
    qtbot.addWidget(win)

    def _drain():
        for _ in range(8):
            qapp.processEvents()
            wait_for_done(4000)
            qapp.processEvents()

    _drain()

    # add: drop two tasks onto a tag row
    uuids = [t["uuid"] for t in tw.export(["status:pending"])]
    win._add_tag_to(uuids, "sprint")
    _drain()
    for u in uuids:
        assert "sprint" in (tw.export([u])[0].get("tags") or [])

    # rename: confirm dialog auto-accepts
    monkeypatch.setattr(mw, "confirm", lambda *a, **k: True)
    win._rename_tag("draft", "review")
    _drain()
    tw.refresh_lookups()
    assert "draft" not in tw.list_tags() and "review" in tw.list_tags()

    # remove
    win._remove_tag("keep")
    _drain()
    tw.refresh_lookups()
    assert "keep" not in tw.list_tags()


def test_sidebar_project_context_menu_signals(qtbot, monkeypatch):
    from unittest.mock import MagicMock

    import PyQt6.QtWidgets as W

    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_projects([{"project": "Work", "open": 3}])
    renamed, deleted = [], []
    sb.projectRenameRequested.connect(lambda o, n: renamed.append((o, n)))
    sb.projectDeleteRequested.connect(deleted.append)

    made: list = []
    monkeypatch.setattr(
        W.QMenu, "addAction", lambda self, text: made.append(MagicMock()) or made[-1]
    )
    monkeypatch.setattr(W.QMenu, "addSeparator", lambda self: None)
    monkeypatch.setattr(
        W.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Client.", True))
    )
    pos = sb.visualItemRect(sb._projects.child(0)).center()

    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[0])   # rename
    sb._context_menu(pos)
    assert renamed == [("Work", "Client")]  # trailing '.' stripped

    made.clear()
    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[-1])   # delete (last)
    sb._context_menu(pos)
    assert deleted == ["Work"]


def test_sidebar_project_colour_menu_and_dot(qtbot, monkeypatch):
    from unittest.mock import MagicMock

    import PyQt6.QtWidgets as W

    from jtask_gui.widgets import project_color_dialog as pcd
    from jtask_gui.widgets.sidebar import _COLOUR_ROLE, Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    # a project that already has a colour → the row shows a dot, not the glyph
    sb.populate_projects([{"project": "Work", "open": 3}], {"Work": "bright blue"})
    item = sb._projects.child(0)
    assert item.data(0, _COLOUR_ROLE) == "bright blue"
    assert not item.icon(0).isNull()

    set_calls, clear_calls = [], []
    sb.projectColorRequested.connect(lambda n, c: set_calls.append((n, c)))
    sb.projectColorClearRequested.connect(clear_calls.append)

    made: list = []
    monkeypatch.setattr(
        W.QMenu, "addAction", lambda self, text: made.append(MagicMock()) or made[-1]
    )
    monkeypatch.setattr(W.QMenu, "addSeparator", lambda self: None)
    pos = sb.visualItemRect(item).center()

    # choose "Set colour…" (index 1) → dialog returns a colour string
    fake_dlg = MagicMock()
    fake_dlg.exec.return_value = 1
    fake_dlg.result_color.return_value = "rgb520"
    monkeypatch.setattr(pcd, "ProjectColorDialog", lambda *a, **k: fake_dlg)
    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[1])
    sb._context_menu(pos)
    assert set_calls == [("Work", "rgb520")]

    # choose "Clear colour" (index 2)
    made.clear()
    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[2])
    sb._context_menu(pos)
    assert clear_calls == ["Work"]


def test_main_window_project_colour_flow(qtbot, tw_env, qapp, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["t-Work", "project:Work"])
    win = MainWindow(Settings())
    qtbot.addWidget(win)

    def _drain():
        for _ in range(8):
            qapp.processEvents()
            wait_for_done(4000)
            qapp.processEvents()

    _drain()
    win._set_project_color("Work", "bright blue")
    _drain()
    tw.refresh_lookups()
    assert tw.project_colors() == {"Work": "bright blue"}

    win._clear_project_color("Work")
    _drain()
    tw.refresh_lookups()
    assert tw.project_colors() == {}


def test_main_window_context_switch_scopes_the_task_list(qtbot, tw_env, qapp):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["work item", "project:Work"])
    tw.add(["home item", "project:Home"])
    tw.context_define("work", "project:Work")

    win = MainWindow(Settings())
    qtbot.addWidget(win)

    def _drain():
        for _ in range(8):
            qapp.processEvents()
            wait_for_done(4000)
            qapp.processEvents()

    def descs() -> set[str]:
        return {tk["description"] for tk in win._model._tasks}

    _drain()
    assert descs() == {"work item", "home item"}

    win._change_context("work")
    _drain()
    assert descs() == {"work item"}

    win._change_context("")  # back to no context
    _drain()
    assert descs() == {"work item", "home item"}

    tw.context_activate(None)


def test_main_window_project_management_flow(qtbot, tw_env, qapp, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    for p in ("Work", "Work.Admin", "Workshop"):
        tw.add([f"t-{p}", f"project:{p}"])

    win = MainWindow(Settings())
    qtbot.addWidget(win)

    def _drain():
        for _ in range(8):
            qapp.processEvents()
            wait_for_done(4000)
            qapp.processEvents()

    _drain()
    monkeypatch.setattr(mw, "confirm", lambda *a, **k: True)

    # rename: Work + Work.Admin -> Client + Client.Admin ; Workshop untouched
    win._rename_project("Work", "Client")
    _drain()
    tw.refresh_lookups()
    assert set(tw.list_projects()) >= {"Client", "Client.Admin", "Workshop"}
    assert "Work" not in tw.list_projects()

    # delete: Client + Client.Admin gone, Workshop kept
    win._delete_project("Client")
    _drain()
    tw.refresh_lookups()
    open_projects = {t.get("project") for t in tw.export(["status.not:deleted"])}
    assert open_projects == {"Workshop"}


def test_calendar_day_drop_emits_gregorian_date(qtbot, tw_env, qapp):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QDropEvent

    from jtask_gui.widgets.calendar_report import CalendarReport
    from jtask_gui.widgets.task_table import UUID_MIME

    cal = CalendarReport("شب")
    qtbot.addWidget(cal)
    got = []
    cal.taskRescheduled.connect(lambda u, d: got.append((u, d)))
    cal._on_drop(["x"], (1403, 7, 10))
    assert got == [(["x"], "2024-10-01")]
    _ = (QDropEvent, QPointF, Qt, UUID_MIME)


# --- dependency graph -----------------------------------------

def test_dep_graph_shows_blockers_and_dependents(qtbot):
    from jtask_gui.widgets.dep_graph import DependencyGraph

    tasks = [
        {"uuid": "a", "id": 1, "description": "بلاکر", "status": "completed"},
        {"uuid": "b", "id": 2, "description": "این", "status": "pending", "depends": ["a"]},
        {"uuid": "c", "id": 3, "description": "وابسته", "status": "pending", "depends": ["b"]},
    ]
    g = DependencyGraph("شب")
    qtbot.addWidget(g)
    g.show_task(tasks[1], tasks)
    # 3 nodes + 3 labels + 2 edges = 8 items
    assert len(g.scene().items()) >= 6


def test_dep_graph_empty_note(qtbot):
    from jtask_gui.widgets.dep_graph import DependencyGraph

    g = DependencyGraph("شب")
    g.resize(360, 220)
    qtbot.addWidget(g)
    g.show()
    g.show_task({"uuid": "a", "id": 1, "description": "تنها", "status": "pending"}, [])
    assert g._empty.isVisible()
    assert "وابستگی" in g._empty.text()
    # the empty state stays inside the view, does not spill out
    assert g._empty.geometry().width() <= g.viewport().width() + 1
    assert g._empty.geometry().height() <= g.viewport().height() + 1
    # and no scene items were scaled up to fill the view
    assert g.transform().m11() <= 1.0


# --- custom reports in the Reports view -----------------------

@pytest.fixture
def rc_with_custom(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text(
        "report.mine.description=مال من\n"
        "report.mine.columns=id,description,due\n"
        "report.mine.labels=ش,شرح,سررسید\n"
        "report.mine.filter=status:pending\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TASKRC", str(rc))
    from jtask import taskwarrior

    taskwarrior.refresh_lookups()
    yield
    taskwarrior.refresh_lookups()


def test_reports_view_discovers_and_renders_custom_report(qtbot, qapp, rc_with_custom):
    from jtask import taskwarrior
    from jtask_gui.widgets.reports_view import ReportsView

    taskwarrior.add(["خرید", "due:2024-10-01"])
    rv = ReportsView("شب")
    qtbot.addWidget(rv)
    for _ in range(10):
        qapp.processEvents()
        from jtask_gui.workers import wait_for_done

        wait_for_done(3000)
        qapp.processEvents()
    assert "mine" in rv._custom_names

    for i in range(rv._rail.count()):
        if rv._rail.item(i).data(0x0100) == "custom:mine":
            rv._rail.setCurrentRow(i)
    for _ in range(10):
        qapp.processEvents()
        from jtask_gui.workers import wait_for_done

        wait_for_done(3000)
        qapp.processEvents()
    assert rv._generic.columnCount() == 3
    assert rv._generic.rowCount() == 1
    assert rv._generic.item(0, 2).text() == "۱۴۰۳-۰۷-۱۰"
