"""M7 — export text / import / sync introspection (integration against `task`)."""

from __future__ import annotations

import json

import pytest

from jtask import taskwarrior


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    taskwarrior.refresh_lookups()
    yield tmp_path
    taskwarrior.refresh_lookups()


def test_export_text_array_vs_lines(tw_env):
    taskwarrior.add(["الف", "project:خانه"])
    taskwarrior.add(["ب"])

    arr = taskwarrior.export_text()
    assert arr.startswith("[") and arr.rstrip().endswith("]")
    assert json.loads(arr) and len(json.loads(arr)) == 2

    lines = taskwarrior.export_text(array=False)
    rows = [json.loads(ln) for ln in lines.splitlines() if ln.strip()]
    assert len(rows) == 2
    assert not lines.lstrip().startswith("[")


def test_export_text_respects_filter(tw_env):
    taskwarrior.add(["الف", "project:خانه"])
    taskwarrior.add(["ب"])
    out = json.loads(taskwarrior.export_text(["project:خانه"]))
    assert len(out) == 1 and out[0]["description"] == "الف"


def test_import_file_reports_added_and_modified(tw_env, tmp_path):
    taskwarrior.add(["اصلی"])
    task = taskwarrior.export()[0]

    # one modification + one brand-new task
    task["description"] = "به‌روز"
    fresh = {"description": "تازه", "status": "pending"}
    path = tmp_path / "import.json"
    path.write_text(json.dumps([task, fresh]), encoding="utf-8")

    res = taskwarrior.import_file(str(path))
    assert res["modified"] == 1
    assert res["added"] == 1
    assert res["total"] == 2
    descs = {t["description"] for t in taskwarrior.export()}
    assert {"به‌روز", "تازه"} <= descs


def test_round_trip_export_then_import_into_empty_db(tw_env, tmp_path, monkeypatch):
    taskwarrior.add(["یک"])
    taskwarrior.add(["دو", "+مهم"])
    dump = taskwarrior.export_text()
    path = tmp_path / "backup.json"
    path.write_text(dump, encoding="utf-8")

    monkeypatch.setenv("TASKDATA", str(tmp_path / "fresh"))
    taskwarrior.refresh_lookups()
    assert taskwarrior.export() == []

    res = taskwarrior.import_file(str(path))
    assert res["total"] == 2
    assert len(taskwarrior.export()) == 2


def test_sync_status_reports_unconfigured(tw_env):
    st = taskwarrior.sync_status()
    assert st["configured"] is False
    assert st["kind"] is None


def test_sync_status_detects_local_server(tw_env):
    taskwarrior.run(["config", "sync.local.server_dir", "/tmp/jtask-sync"])
    taskwarrior.refresh_lookups()
    st = taskwarrior.sync_status()
    assert st["configured"] is True
    assert st["kind"] == "local"
    assert "jtask-sync" in st["target"]
