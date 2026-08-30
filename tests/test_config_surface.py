"""M8 — config / context / UDA / report introspection + writes (via `task config`)."""

from __future__ import annotations

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


def test_config_names_lists_known_variables(tw_env):
    names = taskwarrior.config_names()
    assert "weekstart" in names
    assert "confirmation" in names
    assert len(names) > 100


def test_config_set_and_defaults_roundtrip(tw_env):
    assert taskwarrior.config_defaults().get("weekstart") is None

    taskwarrior.config_set("weekstart", "Monday")
    taskwarrior.refresh_lookups()
    assert "".join(taskwarrior._lines(["_get", "rc.weekstart"])) == "Monday"

    defs = taskwarrior.config_defaults()
    assert defs.get("weekstart") == "sunday"

    taskwarrior.config_unset("weekstart")
    taskwarrior.refresh_lookups()
    assert taskwarrior.config_defaults().get("weekstart") is None


def test_context_crud(tw_env):
    assert taskwarrior.context_list() == []

    taskwarrior.context_define("work", "project:Work")
    taskwarrior.context_define("home", "+home")
    taskwarrior.refresh_lookups()
    ctx = {c["name"]: c for c in taskwarrior.context_list()}
    assert ctx["work"]["read"] == "project:Work"
    assert all(not c["active"] for c in ctx.values())

    taskwarrior.context_activate("work")
    taskwarrior.refresh_lookups()
    ctx = {c["name"]: c for c in taskwarrior.context_list()}
    assert ctx["work"]["active"] is True

    taskwarrior.context_activate(None)
    taskwarrior.context_delete("home")
    taskwarrior.refresh_lookups()
    assert [c["name"] for c in taskwarrior.context_list()] == ["work"]


def test_uda_define_and_delete(tw_env):
    taskwarrior.uda_set("size", "type", "string")
    taskwarrior.uda_set("size", "label", "Size")
    taskwarrior.uda_set("size", "values", "S,M,L")
    taskwarrior.refresh_lookups()

    udas = taskwarrior.uda_definitions()
    assert udas["size"]["type"] == "string"
    assert udas["size"]["label"] == "Size"
    assert udas["size"]["values"] == "S,M,L"

    taskwarrior.uda_delete("size")
    taskwarrior.refresh_lookups()
    assert "size" not in taskwarrior.uda_definitions()


def test_report_set_edits_custom_report(tw_env):
    taskwarrior.config_set("report.mine.columns", "id,description")
    taskwarrior.config_set("report.mine.labels", "ID,Desc")
    taskwarrior.config_set("report.mine.filter", "status:pending")
    taskwarrior.refresh_lookups()
    assert "mine" in taskwarrior.report_specs()

    taskwarrior.report_set("mine", "sort", "urgency-")
    taskwarrior.refresh_lookups()
    assert taskwarrior.report_specs()["mine"]["sort"] == "urgency-"


def test_builtin_reports_constant():
    assert "next" in taskwarrior.BUILTIN_REPORTS
    assert "mine" not in taskwarrior.BUILTIN_REPORTS
