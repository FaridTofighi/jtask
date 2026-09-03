"""gtd-S: the sidebar / Projects-report stuck marker and its "add next action"
jump."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _en():
    from jtask_gui import i18n

    prev = i18n.lang()
    i18n.set_language("en")
    yield
    i18n.set_language(prev)


def _project_rows(sb):
    return [sb._projects.child(i) for i in range(sb._projects.childCount())]


def test_sidebar_badges_only_the_stuck_projects(qtbot):
    from jtask_gui.widgets.sidebar import _STUCK_ROLE, Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_projects([
        {"project": "Alive", "open": 3, "stuck": False},
        {"project": "Wedged", "open": 2, "stuck": True},
    ])
    by_name = {it.text(0).split("  ·")[0]: it for it in _project_rows(sb)}
    assert not by_name["Alive"].data(0, _STUCK_ROLE)
    assert by_name["Wedged"].data(0, _STUCK_ROLE) is True
    assert by_name["Wedged"].toolTip(0)                 # explains why
    assert not by_name["Wedged"].icon(0).isNull()       # badged icon painted


def test_add_next_action_menu_emits_the_project(qtbot, monkeypatch):
    from unittest.mock import MagicMock

    import PyQt6.QtWidgets as W

    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_projects([{"project": "Wedged", "open": 1, "stuck": True}])

    got = []
    sb.addNextActionRequested.connect(got.append)

    made: list = []
    monkeypatch.setattr(
        W.QMenu, "addAction", lambda self, text: made.append(MagicMock()) or made[-1]
    )
    monkeypatch.setattr(W.QMenu, "addSeparator", lambda self: None)
    # "Add a next action…" is made[3] (after rename / colour / clear)
    monkeypatch.setattr(W.QMenu, "exec", lambda self, *a: made[3])
    sb._context_menu(sb.visualItemRect(sb._projects.child(0)).center())
    assert got == ["Wedged"]


def test_main_window_opens_add_task_prefilled_for_the_project(qapp, qtbot, tw_env, monkeypatch):
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    seen = {}

    def fake_form(mode, projects, tags, parent, settings=None):
        class _Dlg:
            def __init__(self):
                from PyQt6.QtWidgets import QComboBox, QLineEdit
                self._project = QComboBox()
                self._project.setEditable(True)
                self._description = QLineEdit()

            def exec(self):
                seen["project"] = self._project.currentText()
                return 0
        return _Dlg()

    monkeypatch.setattr("jtask_gui.widgets.task_form.TaskFormDialog", fake_form)
    w._sidebar.addNextActionRequested.emit("Backend")
    assert seen["project"] == "Backend"


def test_projects_report_marks_stuck_rows(qtbot):
    from jtask_gui.widgets.table_reports import ProjectsReport

    rep = ProjectsReport()
    qtbot.addWidget(rep)
    rep.set_data([
        {"project": "Fine", "open": 2, "waiting": 0, "overdue": 0, "pct": 0, "stuck": False},
        {"project": "Stuck", "open": 1, "waiting": 1, "overdue": 0, "pct": 0, "stuck": True},
    ])
    rows = {rep.item(r, 0).text(): rep.item(r, 0) for r in range(rep.rowCount())}
    assert rows["Fine"].icon().isNull()
    assert not rows["Stuck"].icon().isNull()
    assert rows["Stuck"].toolTip()
