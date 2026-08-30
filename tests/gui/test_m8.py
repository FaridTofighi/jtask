"""M8 — Config / Context / UDA / Reports managers."""

from __future__ import annotations

import pytest


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()


# ---------------------------------------------------------------------------
# Config Manager
# ---------------------------------------------------------------------------


def test_config_manager_lists_and_flags_overrides(qapp, tw_env):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.config_manager import ConfigManager

    tw.config_set("weekstart", "Monday")
    tw.refresh_lookups()

    m = ConfigManager()
    m.reload()
    _drain(qapp)

    names = {m._rows[i][0] for i in range(len(m._rows))}
    assert "weekstart" in names
    ws = next(r for r in m._rows if r[0] == "weekstart")
    assert ws[1] == "Monday" and ws[2] == "sunday" and ws[3] is True


def test_config_manager_group_filter(qapp, tw_env):
    from jtask_gui.widgets.config_manager import ConfigManager, _group_of

    assert _group_of("color.due") == "color"
    assert _group_of("report.next.columns") == "report"
    assert _group_of("weekstart") == "date"

    m = ConfigManager()
    m.reload()
    _drain(qapp)
    m._group.setCurrentIndex(
        [m._group.itemData(i) for i in range(m._group.count())].index("color")
    )
    m._apply_filter()
    for r in range(m._table.rowCount()):
        assert m._table.item(r, 0).text().startswith("color")


def test_config_manager_write_and_reset(qapp, tw_env, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets import config_manager

    monkeypatch.setattr(config_manager, "confirm", lambda *a, **k: True)
    m = config_manager.ConfigManager()

    m._write("weekstart", "Monday")
    _drain(qapp)
    tw.refresh_lookups()
    assert "".join(tw._lines(["_get", "rc.weekstart"])) == "Monday"

    m._write("weekstart", "", reset=True)
    _drain(qapp)
    tw.refresh_lookups()
    assert tw.config_defaults().get("weekstart") is None


# ---------------------------------------------------------------------------
# Context Manager
# ---------------------------------------------------------------------------


def test_context_manager_crud(qapp, tw_env, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets import context_manager

    monkeypatch.setattr(context_manager, "confirm", lambda *a, **k: True)
    m = context_manager.ContextManager()

    m._apply(lambda: tw.context_define("خانه", "+خانه"))
    _drain(qapp)
    assert m._table.rowCount() == 1
    assert m._table.item(0, 0).text() == "خانه"

    m._table.setCurrentCell(0, 0)
    m._set_active("خانه")
    _drain(qapp)
    assert m._table.item(0, 3).text() == "✓"

    m._table.setCurrentCell(0, 0)
    m._delete_selected()
    _drain(qapp)
    assert m._table.rowCount() == 0


# ---------------------------------------------------------------------------
# UDA Manager
# ---------------------------------------------------------------------------


def test_uda_manager_create_and_delete(qapp, tw_env, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets import uda_manager

    monkeypatch.setattr(uda_manager, "confirm", lambda *a, **k: True)
    m = uda_manager.UdaManager()

    m._save({"name": "effort", "label": "تلاش", "type": "numeric",
             "values": "", "default": ""})
    _drain(qapp)
    tw.refresh_lookups()
    assert tw.uda_definitions()["effort"]["type"] == "numeric"

    def _row_of(name):
        return next(
            r for r in range(m._table.rowCount())
            if m._table.item(r, 0).text() == name
        )

    assert m._table.item(_row_of("effort"), 2).text() == "عددی"

    m._table.setCurrentCell(_row_of("effort"), 0)
    m._delete()
    _drain(qapp)
    tw.refresh_lookups()
    assert "effort" not in tw.uda_definitions()


# ---------------------------------------------------------------------------
# Report Manager
# ---------------------------------------------------------------------------


def test_report_manager_marks_builtin_vs_custom(qapp, tw_env):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.report_manager import ReportManager

    tw.config_set("report.mine.columns", "id,description")
    tw.config_set("report.mine.description", "مال من")
    tw.refresh_lookups()

    m = ReportManager()
    m.reload()
    _drain(qapp)

    kinds = {
        m._table.item(r, 0).text(): m._table.item(r, 1).text()
        for r in range(m._table.rowCount())
    }
    assert kinds.get("next") == "داخلی"
    assert kinds.get("mine") == "سفارشی"


def test_report_manager_edits_custom_report(qapp, tw_env, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets import report_manager

    monkeypatch.setattr(report_manager, "confirm", lambda *a, **k: True)
    tw.config_set("report.mine.columns", "id,description")
    tw.refresh_lookups()

    m = report_manager.ReportManager()
    m.reload()
    _drain(qapp)
    m._specs = tw.report_specs()
    m._save("mine", {"columns": "id,description,project", "sort": "urgency-",
                     "labels": "", "filter": "", "dateformat": "", "description": ""},
            is_new=False)
    _drain(qapp)
    tw.refresh_lookups()
    assert tw.report_specs()["mine"]["sort"] == "urgency-"
    assert "project" in tw.report_specs()["mine"]["columns"]


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_manager_dialog_has_four_tabs_and_bubbles_changed(qapp, tw_env):
    from jtask_gui.widgets.manager_dialog import ManagerDialog

    d = ManagerDialog()
    _drain(qapp)
    assert d._tabs.count() == 4
    fired = []
    d.changed.connect(lambda: fired.append(1))
    d.config.changed.emit()
    assert fired == [1]


def test_main_window_opens_manager(win, qapp, monkeypatch):
    calls = []

    class _Sig:
        def connect(self, *_a):
            pass

    class FakeDialog:
        changed = _Sig()

        def __init__(self, *a, **k):
            calls.append(1)

        def exec(self):
            return 0

    monkeypatch.setattr(
        "jtask_gui.widgets.manager_dialog.ManagerDialog", FakeDialog
    )
    win._open_manager()
    assert calls == [1]


@pytest.fixture
def win(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    yield w
    wait_for_done(4000)
