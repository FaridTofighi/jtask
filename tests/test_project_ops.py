"""Project management — delete / rename a project and its sub-projects.

Taskwarrior has no project entity; "the project and its sub-tasks" is every
task in ``name`` or a dotted sub-project ``name.*``. A bare ``project:name``
filter is a *prefix* match, so ``Work`` must not touch ``Workshop``.
"""

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
    yield
    taskwarrior.refresh_lookups()


def _seed() -> None:
    for p in ("Work", "Work.Admin", "Work.Admin.Q3", "Workshop", "Home"):
        taskwarrior.add([f"t-{p}", f"project:{p}"])


def _projects_of_open_tasks() -> set[str]:
    return {
        tk.get("project", "")
        for tk in taskwarrior.export(["status.not:deleted"])
    }


def test_project_task_count_covers_subprojects_not_prefix_siblings(tw_env):
    _seed()
    assert taskwarrior.project_task_count("Work") == 3        # Work + .Admin + .Admin.Q3
    assert taskwarrior.project_task_count("Work.Admin") == 2  # .Admin + .Admin.Q3
    assert taskwarrior.project_task_count("Workshop") == 1    # NOT caught by "Work"
    assert taskwarrior.project_task_count("Nope") == 0
    assert taskwarrior.project_task_count("") == 0


def test_delete_project_removes_it_and_subtasks_only(tw_env):
    _seed()
    taskwarrior.command(["1"], "done")  # a completed task still counts as non-deleted

    n = taskwarrior.delete_project("Work")
    assert n == 3
    taskwarrior.refresh_lookups()
    assert _projects_of_open_tasks() == {"Workshop", "Home"}
    # the deleted tasks are in the 'deleted' state, not purged — but a
    # project is just a shared string value, so it must not still be set on
    # them (else the project would keep showing up, all-zero, forever)
    deleted = [t for t in taskwarrior.export(["status:deleted"])]
    assert len(deleted) == 3
    assert all(not t.get("project") for t in deleted)
    # reversible
    assert taskwarrior.undo_preview()["empty"] is False


def test_delete_project_also_clears_already_deleted_tasks(tw_env):
    """Bug: a task individually deleted *before* "delete project" runs keeps
    its project field forever (task delete refuses an already-deleted task),
    so the project keeps appearing — with all-zero counts — even after
    every visible (pending/completed) task is gone."""
    _seed()
    # target by uuid, not sequential id — completing/deleting a task shifts
    # every later pending task's id, so a hardcoded id would silently drift
    # onto the wrong task
    admin = taskwarrior.export(["project.is:Work.Admin"])[0]["uuid"]
    taskwarrior.command([admin], "delete")   # Work.Admin -> deleted, pre-existing
    taskwarrior.command(
        [taskwarrior.export(["project.is:Work"])[0]["uuid"]], "done"
    )                                        # Work -> completed
    taskwarrior.refresh_lookups()

    n = taskwarrior.delete_project("Work")
    assert n == 2  # the completed "Work" task + the still-pending "Work.Admin.Q3"

    # nothing in *any* status still names Work or a Work.* sub-project
    everything = (
        taskwarrior.export(["status:pending"])
        + taskwarrior.export(["status:completed"])
        + taskwarrior.export(["status:deleted"])
        + taskwarrior.export(["status:waiting"])
    )
    assert not any(
        (t.get("project") or "") == "Work" or (t.get("project") or "").startswith("Work.")
        for t in everything
    )


def test_delete_project_cleans_up_a_zombie_with_zero_visible_tasks(tw_env):
    """The project has *only* an already-deleted task naming it (e.g. every
    other task was individually deleted earlier, or a previous, buggy
    "delete project" run already handled the visible ones) — nothing
    pending/completed, so project_task_count is 0, but delete_project must
    still clean it up rather than being a no-op."""
    taskwarrior.add(["zombie task", "project:Ghost"])
    taskwarrior.command(["1"], "delete")
    taskwarrior.refresh_lookups()

    assert taskwarrior.project_task_count("Ghost") == 0
    assert taskwarrior.project_deleted_count("Ghost") == 1

    n = taskwarrior.delete_project("Ghost")
    assert n == 0  # nothing new was deleted — it already was
    assert taskwarrior.project_deleted_count("Ghost") == 0
    assert not taskwarrior.export(["status:deleted"])[0].get("project")


def test_rename_project_also_moves_already_deleted_tasks(tw_env):
    """Same class of leak as delete_project: rename must not leave a
    deleted-status task behind still naming the *old* project."""
    _seed()
    taskwarrior.command(["2"], "delete")  # Work.Admin -> deleted, pre-existing
    taskwarrior.refresh_lookups()

    n = taskwarrior.rename_project("Work", "Client")
    assert n == 3  # Work, the now-deleted Work.Admin, Work.Admin.Q3

    deleted = taskwarrior.export(["status:deleted"])
    assert len(deleted) == 1
    assert deleted[0]["project"] == "Client.Admin"
    assert taskwarrior.project_deleted_count("Work") == 0


def test_delete_unknown_project_is_a_noop(tw_env):
    _seed()
    assert taskwarrior.delete_project("Ghost") == 0
    assert taskwarrior.delete_project("") == 0
    taskwarrior.refresh_lookups()
    assert len(taskwarrior.export(["status.not:deleted"])) == 5


def test_rename_project_preserves_the_hierarchy(tw_env):
    _seed()
    n = taskwarrior.rename_project("Work", "Client")
    assert n == 3
    taskwarrior.refresh_lookups()
    assert _projects_of_open_tasks() == {"Client", "Client.Admin", "Client.Admin.Q3",
                                         "Workshop", "Home"}


def test_rename_project_noop_cases(tw_env):
    _seed()
    assert taskwarrior.rename_project("Work", "Work") == 0
    assert taskwarrior.rename_project("Ghost", "X") == 0
    assert taskwarrior.rename_project("", "X") == 0
    assert taskwarrior.rename_project("Work", "") == 0


def test_project_colour_set_change_and_clear(tw_env):
    _seed()
    assert taskwarrior.project_colors() == {}

    taskwarrior.set_project_color("Work", "bright blue")
    assert taskwarrior.project_colors() == {"Work": "bright blue"}

    # changing just overwrites
    taskwarrior.set_project_color("Work", "rgb520")
    assert taskwarrior.project_colors() == {"Work": "rgb520"}

    # a second project is independent
    taskwarrior.set_project_color("Home", "green")
    assert taskwarrior.project_colors() == {"Work": "rgb520", "Home": "green"}

    # clear via empty string, and via clear_project_color
    taskwarrior.set_project_color("Work", "")
    assert taskwarrior.project_colors() == {"Home": "green"}
    taskwarrior.clear_project_color("Home")
    assert taskwarrior.project_colors() == {}


def test_project_colour_noop_cases(tw_env):
    _seed()
    assert taskwarrior.set_project_color("", "red") == ""
    # a trailing dot on the project name is normalised away
    taskwarrior.set_project_color("Work.", "cyan")
    assert taskwarrior.project_colors() == {"Work": "cyan"}
    # clearing an unknown project is a tolerated no-op
    taskwarrior.clear_project_color("Ghost")
    assert taskwarrior.project_colors() == {"Work": "cyan"}
