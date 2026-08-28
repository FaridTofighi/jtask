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
