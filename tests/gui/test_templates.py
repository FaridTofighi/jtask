"""N-C: task templates — a saved reusable task shape, distinct from recurrence."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings


@pytest.fixture(autouse=True)
def _clean_store():
    QSettings("jtask", "jtask-gui").clear()
    yield
    QSettings("jtask", "jtask-gui").clear()


def test_template_store_roundtrips_through_settings():
    from jtask_gui.settings import Settings

    s = Settings()
    assert s.templates() == {}
    spec = {"description": "Weekly report", "project": "Work",
            "tags": ["report"], "priority": "M"}
    s.save_template("Weekly", spec)
    assert Settings().templates() == {"Weekly": spec}   # survives a fresh wrapper
    s.delete_template("Weekly")
    assert Settings().templates() == {}


def test_add_form_applies_a_template(qtbot):
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.task_form import TaskFormDialog

    s = Settings()
    s.save_template("Standup", {
        "description": "Daily standup notes", "project": "Team",
        "tags": ["meeting"], "priority": "L",
    })
    d = TaskFormDialog("add", ["Team", "Work"], ["meeting"], None, settings=s)
    qtbot.addWidget(d)

    names = [a.text() for a in d._tpl_btn.menu().actions() if a.text()]
    assert "Standup" in names

    d._apply_template(s.templates()["Standup"])
    assert d._description.text() == "Daily standup notes"
    assert d._project.currentText() == "Team"
    assert set(d._tags.tags()) == {"meeting"}
    assert d._priority.value() == "L"
    assert "priority:L" in d.args() and "project:Team" in d.args()


def test_apply_template_never_overwrites_a_typed_description(qtbot):
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.task_form import TaskFormDialog

    s = Settings()
    s.save_template("T", {"description": "from template", "project": "", "tags": [],
                          "priority": ""})
    d = TaskFormDialog("add", [], [], None, settings=s)
    qtbot.addWidget(d)
    d._description.setText("what I typed")
    d._apply_template(s.templates()["T"])
    assert d._description.text() == "what I typed"


def test_save_current_form_as_template(qtbot):
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.task_form import TaskFormDialog

    s = Settings()
    d = TaskFormDialog("add", ["Work"], [], None, settings=s)
    qtbot.addWidget(d)
    d._description.setText("Draft blog post")
    d._project.setCurrentText("Work")
    d._tags.set_tags(["writing"])
    d._priority.set_value("M")

    assert d.current_template_spec() == {
        "description": "Draft blog post", "project": "Work",
        "tags": ["writing"], "priority": "M",
    }


def test_recurrence_copier_is_not_called_a_template_anymore():
    from jtask_gui.i18n import set_language, t

    for lang in ("fa", "en"):
        set_language(lang)
        # the recurrence button no longer uses the word "template" / "الگو"
        assert "الگو" not in t("form.recur.from_template")
        assert "template" not in t("form.recur.from_template").lower()
        # the task-template menu does
        assert t("form.template.menu")
    set_language("fa")


def test_main_window_save_task_as_template(qapp, qtbot, tw_env, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["shape me", "project:Work", "+writing", "priority:H"])
    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    import PyQt6.QtWidgets as W

    monkeypatch.setattr(W.QInputDialog, "getText", staticmethod(lambda *a, **k: ("My shape", True)))
    task = tw.export(["description:shape"])[0]
    w._save_task_as_template(task)
    saved = Settings().templates()
    assert saved.get("My shape") == {
        "description": "shape me", "project": "Work",
        "tags": ["writing"], "priority": "H",
    }
