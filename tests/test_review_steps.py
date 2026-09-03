"""gtd-W1: the weekly-review step sequence — one definition for `jtask review`
and the GUI wizard."""

from __future__ import annotations

import io

import pytest

from jtask import gtd, taskwarrior


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    taskwarrior.refresh_lookups()
    yield
    taskwarrior.refresh_lookups()


EXPECTED_ORDER = [
    "inbox", "overdue", "due_this_week", "next_actions",
    "waiting_for", "stuck_projects", "someday", "stale",
]


def test_review_steps_are_a_fixed_ordered_sequence():
    assert [s.key for s in gtd.REVIEW_STEPS] == EXPECTED_ORDER


def test_the_cli_renders_exactly_the_shared_steps():
    """`weekly_review`'s title map must cover every REVIEW_STEP and nothing
    else — the CLI can't drift from the wizard."""
    assert set(gtd._REVIEW_TITLES) == {s.key for s in gtd.REVIEW_STEPS}


def test_every_step_but_stuck_projects_maps_to_a_live_filter():
    for s in gtd.REVIEW_STEPS:
        if s.key == "stuck_projects":
            assert s.filter() is None
        else:
            assert isinstance(s.filter(), list) and s.filter()


def test_step_gather_membership(tw_env):
    taskwarrior.add(["loose thought"])                              # inbox
    taskwarrior.add(["ship the thing", "project:Work"])             # next_actions
    taskwarrior.add(["chase Sara", "project:Work", "+waiting"])     # waiting_for + stuck? no
    taskwarrior.add(["read later", "project:Books", "+someday"])    # someday + stuck
    taskwarrior.add(["overdue one", "project:Work", "due:2000-01-01"])  # overdue
    taskwarrior.refresh_lookups()

    def descs(key):
        return {t["description"] for t in gtd.review_step(key).gather()}

    assert descs("inbox") == {"loose thought"}
    assert "ship the thing" in descs("next_actions")
    assert descs("waiting_for") == {"chase Sara"}
    assert descs("someday") == {"read later"}
    assert "overdue one" in descs("overdue")
    # Books has only a +someday task → stuck; Work has a real next action → not
    stuck = {r["project"] for r in gtd.review_step("stuck_projects").gather()}
    assert stuck == {"Books"}


def test_weekly_review_cli_runs_through_all_steps(tw_env):
    from rich.console import Console

    from jtask.cli import Runtime
    from jtask.themes import resolve

    taskwarrior.add(["a task", "project:X"])
    taskwarrior.refresh_lookups()

    buf = io.StringIO()
    rt = Runtime(theme=resolve({}), console=Console(file=buf, width=100))
    gtd.weekly_review(rt, [])
    out = buf.getvalue()
    # console text is reshaped/bidi-reordered for the terminal — check the
    # step numbering ("۱)"…"۸)" render as "(۱"…"(۸") is all there.
    assert all(f"({d}" in out for d in "۱۲۳۴۵۶۷۸")
    assert len(gtd.REVIEW_STEPS) == 8
