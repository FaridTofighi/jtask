"""End-to-end tests against a real, isolated Taskwarrior instance."""

from __future__ import annotations

import datetime
import json
import shutil

import pytest

from jtask import config, jalali, taskwarrior
from jtask.cli import main

pytestmark = pytest.mark.skipif(
    shutil.which("task") is None, reason="Taskwarrior binary not installed"
)

TEHRAN = datetime.timezone(datetime.timedelta(hours=3, minutes=30))


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "taskdata"))
    rc = tmp_path / "taskrc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    monkeypatch.setenv("JTASK_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)
    taskwarrior.refresh_lookups()
    config.mark_first_run_done()
    yield
    taskwarrior.refresh_lookups()


def _run(*args: str) -> int:
    return main(list(args))


def _json_out(capsys, *args: str) -> list[dict]:
    _run(*args, "--json")
    return json.loads(capsys.readouterr().out)


def test_add_stores_gregorian_but_displays_jalali(tw_env, capsys):
    assert _run("add", "تماس با آرش", "due:1403.07.10") == 0
    capsys.readouterr()

    raw = taskwarrior.export()
    assert raw[0]["due"].startswith("20240930T") or raw[0]["due"].startswith("20241001T")

    rows = _json_out(capsys, "list")
    assert rows[0]["due"] == "۱۴۰۳-۰۷-۱۰"
    assert rows[0]["due_gregorian"].startswith(("20240930", "20241001"))


def test_roundtrip_relative_date(tw_env, capsys):
    _run("add", "کار فردا", "due:فردا")
    capsys.readouterr()
    today = jalali.jdatetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    rows = _json_out(capsys, "list")
    assert rows[0]["due"] == jalali.to_persian_digits(tomorrow.strftime("%Y-%m-%d"))


def test_gregorian_flag_shows_gregorian(tw_env, capsys):
    _run("add", "کار", "due:1403.07.10")
    capsys.readouterr()
    rows = _json_out(capsys, "list", "--gregorian")
    assert rows[0]["due"] == "2024-10-01"


def test_bulk_modify_by_filter(tw_env, capsys):
    _run("add", "الف", "project:وب")
    _run("add", "ب", "project:وب")
    _run("add", "ج", "project:خانه")
    capsys.readouterr()

    assert _run("modify", "project:وب", "+مهم") == 0
    capsys.readouterr()

    tagged = taskwarrior.export(["+مهم"])
    assert len(tagged) == 2
    assert all("مهم" in t.get("tags", []) for t in tagged)


def test_modify_by_id_rewrites_due(tw_env, capsys):
    _run("add", "کار", "due:1403.07.10")
    capsys.readouterr()
    _run("modify", "1", "due:1403.08.01")
    capsys.readouterr()
    raw = taskwarrior.export(["1"])[0]
    back = jalali.from_taskwarrior(raw["due"])
    assert back == "۱۴۰۳-۰۸-۰۱"


def test_unknown_subcommand_passes_through(tw_env, capfd):
    _run("add", "کار", "+خانه")
    capfd.readouterr()
    rc = _run("_tags")
    out = capfd.readouterr().out  # passthrough writes at fd level
    assert rc == 0
    assert "خانه" in out


def test_rejects_gregorian_looking_input(tw_env, capsys):
    rc = _run("add", "کار", "due:2024-10-01")
    assert rc == 1


def test_missing_task_binary_message(tw_env, capsys, monkeypatch):
    monkeypatch.setenv("JTASK_TASK_BIN", "")
    monkeypatch.setattr(shutil, "which", lambda _: None)
    taskwarrior.refresh_lookups()
    rc = _run("list")
    out = capsys.readouterr().out
    assert rc == 1
    assert "Taskwarrior" in out or "task" in out
