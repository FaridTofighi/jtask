"""gtd-S: the stuck-project computation shared by the sidebar badge, the review
wizard and the CLI ``jtask review``.

A project is *stuck* when it has pending work but nothing you could pick up
now — no pending task that isn't blocked, ``+waiting`` or ``+someday`` (the GTD
board's Next Actions rule).
"""

from __future__ import annotations

import pytest

from jtask import gtd, reports, taskwarrior


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    taskwarrior.refresh_lookups()
    yield
    taskwarrior.refresh_lookups()


# --- pure logic (no Taskwarrior) --------------------------------

def test_stuck_project_names_from_a_task_list():
    tasks = [
        {"uuid": "1", "status": "pending", "project": "Live", "tags": []},
        {"uuid": "2", "status": "pending", "project": "OnlyWaiting", "tags": ["waiting"]},
        {"uuid": "3", "status": "pending", "project": "OnlySomeday", "tags": ["someday"]},
        {"uuid": "4", "status": "pending", "project": "Blocked", "tags": [],
         "depends": ["5"]},
        {"uuid": "5", "status": "pending", "project": "Blocked", "tags": []},
        {"uuid": "6", "status": "completed", "project": "DoneOnly", "tags": []},
        {"uuid": "7", "status": "pending", "tags": []},               # no project
    ]
    stuck = gtd.stuck_project_names(tasks)
    assert stuck == {"OnlyWaiting", "OnlySomeday"}
    # "Blocked" project: task 4 is blocked by 5, but 5 IS a pickable next action
    assert "Blocked" not in stuck
    assert "Live" not in stuck and "DoneOnly" not in stuck   # no pending / has next


def test_a_project_whose_only_task_is_blocked_is_stuck():
    tasks = [
        {"uuid": "a", "status": "pending", "project": "P", "tags": [], "depends": ["b"]},
        {"uuid": "b", "status": "pending", "project": "Other", "tags": []},
    ]
    assert gtd.stuck_project_names(tasks) == {"P"}


def test_depends_accepts_a_comma_string_too():
    tasks = [
        {"uuid": "a", "status": "pending", "project": "P", "tags": [], "depends": "b,c"},
        {"uuid": "b", "status": "pending", "project": "Q", "tags": []},
    ]
    assert "P" in gtd.stuck_project_names(tasks)


# --- end to end against a real, isolated Taskwarrior -----------

def test_stuck_projects_end_to_end(tw_env):
    taskwarrior.add(["ship it", "project:Alive"])                    # next action
    taskwarrior.add(["chase Sara", "project:Delegated", "+waiting"])  # stuck
    taskwarrior.add(["maybe rewrite", "project:Later", "+someday"])   # stuck
    taskwarrior.add(["loose end"])                                    # no project
    taskwarrior.refresh_lookups()

    assert gtd.stuck_projects() == ["Delegated", "Later"]


def test_report_projects_flags_stuck_rows(tw_env):
    taskwarrior.add(["do the thing", "project:Fine"])
    taskwarrior.add(["waiting on legal", "project:Stuck", "+waiting"])
    taskwarrior.refresh_lookups()

    rows = {r["project"]: r for r in reports.report_projects()}
    assert rows["Stuck"]["stuck"] is True
    assert rows["Fine"]["stuck"] is False


def test_review_stuck_step_uses_the_shared_rule(tw_env):
    taskwarrior.add(["actionable", "project:Ok"])
    taskwarrior.add(["someday-only", "project:Wedged", "+someday"])
    taskwarrior.refresh_lookups()

    rows = gtd.review_step("stuck_projects").gather()
    assert [row["project"] for row in rows] == ["Wedged"]
