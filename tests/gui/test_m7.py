"""M7 — export / import / sync GUI."""

from __future__ import annotations

import json

import pytest


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


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_dialog_spec_reflects_scope_and_format(qapp):
    from jtask_gui.widgets.export_dialog import ExportDialog

    d = ExportDialog(["project:خانه", "+مهم"])
    assert d.spec()["filter"] == []  # default scope = all

    d._scope.set_value("current")
    d._on_scope(None)
    assert d.spec()["filter"] == ["project:خانه", "+مهم"]

    d._format.set_value("lines")
    assert d.spec()["array"] is False


def test_write_export_creates_file_with_all_tasks(tw_env, tmp_path):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.export_dialog import write_export

    tw.add(["الف"])
    tw.add(["ب", "+x"])
    path = tmp_path / "out.json"
    res = write_export({"filter": [], "array": True, "path": str(path)})
    assert res["count"] == 2
    assert json.loads(path.read_text("utf-8"))


def test_export_flow_writes_file(win, qapp, tmp_path, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.workers import wait_for_done

    tw.add(["برای خروجی"])
    out = tmp_path / "e.json"

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def spec(self):
            return {"filter": [], "array": False, "path": str(out)}

    monkeypatch.setattr(mw, "ExportDialog", FakeDialog, raising=False)
    monkeypatch.setattr(
        "jtask_gui.widgets.export_dialog.ExportDialog", FakeDialog
    )
    win._open_export()
    wait_for_done(4000)
    qapp.processEvents()
    assert out.exists()
    assert "برای خروجی" in out.read_text("utf-8")


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_inspect_import_detects_array_and_lines(tmp_path):
    from jtask_gui.widgets.import_dialog import inspect_import

    a = tmp_path / "a.json"
    a.write_text(json.dumps([{"description": "یک"}, {"description": "دو"}]), "utf-8")
    ra = inspect_import(str(a))
    assert ra["ok"] and ra["count"] == 2 and ra["format"] == "آرایهٔ JSON"
    assert "یک" in ra["sample"]

    b = tmp_path / "b.json"
    b.write_text('{"description":"x"}\n{"description":"y"}\n', "utf-8")
    rb = inspect_import(str(b))
    assert rb["ok"] and rb["count"] == 2 and rb["format"] == "خطوط JSON"


def test_inspect_import_rejects_garbage(tmp_path):
    from jtask_gui.widgets.import_dialog import inspect_import

    p = tmp_path / "x.json"
    p.write_text("not json at all", "utf-8")
    r = inspect_import(str(p))
    assert not r["ok"] and r["error"]


def test_import_dialog_enables_ok_only_for_valid_file(qapp, tmp_path):
    from jtask_gui.widgets.import_dialog import ImportDialog

    d = ImportDialog()
    assert not d._ok.isEnabled()
    good = tmp_path / "g.json"
    good.write_text(json.dumps([{"description": "z"}]), "utf-8")
    d._path.setText(str(good))
    assert d._ok.isEnabled()
    d._path.setText(str(tmp_path / "missing.json"))
    assert not d._ok.isEnabled()


def test_import_flow_adds_tasks(win, qapp, tmp_path, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    src = tmp_path / "imp.json"
    src.write_text(json.dumps([{"description": "واردشده", "status": "pending"}]), "utf-8")

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def path(self):
            return str(src)

    monkeypatch.setattr("jtask_gui.widgets.import_dialog.ImportDialog", FakeDialog)
    win._open_import()
    wait_for_done(4000)
    qapp.processEvents()
    assert any(t["description"] == "واردشده" for t in tw.export())


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def test_sync_dialog_unconfigured_disables_button(qapp, tw_env):
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.sync_dialog import SyncManagerDialog
    from jtask_gui.workers import wait_for_done

    d = SyncManagerDialog(Settings())
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    assert not d._go.isEnabled()
    assert "پیکربندی نشده" in d._status.text()


def test_sync_dialog_configured_enables_and_runs(qapp, tw_env, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.sync_dialog import SyncManagerDialog
    from jtask_gui.workers import wait_for_done

    tw.run(["config", "sync.local.server_dir", "/tmp/jtask-sync-test"])
    tw.refresh_lookups()
    monkeypatch.setattr(tw, "synchronize", lambda: "Sync complete.")

    st = Settings()
    d = SyncManagerDialog(st)
    fired = []
    d.synced.connect(lambda: fired.append(1))
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    assert d._go.isEnabled()

    d._run()
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    assert fired == [1]
    assert st.last_sync  # timestamp stored
