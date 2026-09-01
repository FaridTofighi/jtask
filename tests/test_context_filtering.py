"""Active-context read-filter scoping.

Taskwarrior's ``task export`` command ignores the active context (every report
respects it, but ``export`` does not). jtask reads exclusively through
``task export``, so it applies the context's ``read`` filter itself — otherwise
switching context has no visible effect on anything jtask shows.
"""

from __future__ import annotations

import pytest

from jtask import reports, taskwarrior


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    taskwarrior.refresh_lookups()
    yield
    taskwarrior.context_activate(None)
    taskwarrior.refresh_lookups()


def _seed() -> None:
    taskwarrior.add(["work task", "project:Work"])
    taskwarrior.add(["work sub task", "project:Work.Admin"])
    taskwarrior.add(["home task", "project:Home"])
    taskwarrior.add(["tagged home", "project:Home", "+urgent"])


def test_export_scopes_to_active_context(tw_env):
    _seed()
    taskwarrior.context_define("work", "project:Work")

    assert len(taskwarrior.export()) == 4  # no context yet

    taskwarrior.context_activate("work")
    assert sorted(t["description"] for t in taskwarrior.export()) == [
        "work sub task",
        "work task",
    ]
    # a caller filter is ANDed on top of the context
    assert [t["description"] for t in taskwarrior.export(["project:Work.Admin"])] == [
        "work sub task"
    ]


def test_apply_context_false_bypasses_scoping(tw_env):
    _seed()
    taskwarrior.context_define("work", "project:Work")
    taskwarrior.context_activate("work")

    assert len(taskwarrior.export(apply_context=False)) == 4
    assert "home task" in taskwarrior.export_text(apply_context=False)


def test_reports_respect_context(tw_env):
    _seed()
    taskwarrior.context_define("home", "project:Home")
    taskwarrior.context_activate("home")

    assert {r["description"] for r in reports.report_next()} == {"home task", "tagged home"}
    assert [r["project"] for r in reports.report_projects()] == ["Home"]
    assert {r["tag"] for r in reports.report_tags()} == {"urgent"}


def test_no_context_is_a_noop(tw_env):
    _seed()
    assert taskwarrior.context_read_filter() == ()
    assert len(taskwarrior.export()) == 4


def test_read_filter_tokenises_quoted_values(tw_env):
    _seed()
    taskwarrior.add(["spaced", "project:Home", "+urgent", 'description:"home task"'])
    taskwarrior.context_define("q", 'description:"home task"')
    taskwarrior.context_activate("q")

    assert taskwarrior.context_read_filter() == ("description:home task",)
    got = {t["description"] for t in taskwarrior.export()}
    assert "home task" in got and "work task" not in got


def test_context_switch_clears_the_cache(tw_env):
    _seed()
    taskwarrior.context_define("work", "project:Work")
    taskwarrior.context_define("home", "project:Home")

    taskwarrior.context_activate("work")
    assert {t["description"] for t in taskwarrior.export()} == {"work task", "work sub task"}
    taskwarrior.context_activate("home")
    assert {t["description"] for t in taskwarrior.export()} == {"home task", "tagged home"}
    taskwarrior.context_activate(None)
    assert len(taskwarrior.export()) == 4
