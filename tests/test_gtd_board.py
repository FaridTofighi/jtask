"""NB-2: the GTD preset's column filters produce the right membership.

Verified against a real, isolated Taskwarrior (the `tw_env` fixture), using the
project's own `+waiting` / `+someday` conventions.
"""

from __future__ import annotations

import shlex

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


@pytest.fixture
def gtd_env(tw_env):
    from jtask import taskwarrior as tw

    tw.add(["catch the train"])                       # inbox: no project, no tag
    tw.add(["reply to landlord"])                     # inbox
    tw.add(["write the spec", "project:Work", "priority:H"])   # next (project)
    tw.add(["book a haircut", "+errand"])             # next (tag, no project)
    tw.add(["chase the invoice", "project:Work", "+waiting"])  # waiting
    tw.add(["learn the cello", "+someday"])           # someday
    tw.add(["read SICP", "project:Learning", "+someday"])      # someday
    tw.add(["ship the release", "project:Work"])
    tw.command([tw.export(["description:ship"])[0]["uuid"]], "done")   # done
    tw.refresh_lookups()
    yield


def _members(filter_str: str) -> set[str]:
    return {t["description"] for t in taskwarrior.export(shlex.split(filter_str))}


def _gtd_columns() -> dict[str, str]:
    from jtask_gui.boards import BUILTIN_BOARDS

    return {c["title"].rsplit(".", 1)[-1]: c["filter"]
            for c in BUILTIN_BOARDS["gtd"]["columns"]}


def test_gtd_column_membership(gtd_env):
    cols = _gtd_columns()
    assert _members(cols["inbox"]) == {"catch the train", "reply to landlord"}
    assert _members(cols["next"]) == {"write the spec", "book a haircut"}
    assert _members(cols["waiting"]) == {"chase the invoice"}
    assert _members(cols["someday"]) == {"learn the cello", "read SICP"}
    assert _members(cols["done"]) == {"ship the release"}


def test_gtd_columns_partition_pending_tasks(gtd_env):
    """No pending task is in two GTD columns at once (Done is completed)."""
    cols = _gtd_columns()
    seen: dict[str, list[str]] = {}
    for name in ("inbox", "next", "waiting", "someday"):
        for desc in _members(cols[name]):
            seen.setdefault(desc, []).append(name)
    doubled = {d: c for d, c in seen.items() if len(c) > 1}
    assert not doubled, doubled


def test_gtd_drop_actions_use_the_established_tag_conventions():
    from jtask_gui.boards import BUILTIN_BOARDS, compile_drop

    drops = {c["title"].rsplit(".", 1)[-1]: c["drop"]
             for c in BUILTIN_BOARDS["gtd"]["columns"]}
    assert compile_drop(drops["inbox"]) is None                       # view only
    assert compile_drop(drops["next"]) == ("modify", ["-waiting", "-someday"])
    assert compile_drop(drops["waiting"]) == ("modify", ["+waiting", "-someday"])
    assert compile_drop(drops["someday"]) == ("modify", ["+someday", "-waiting"])
    assert compile_drop(drops["done"]) == ("done", [])


def test_dragging_a_waiting_task_to_next_actions_clears_it(gtd_env):
    from jtask_gui.boards import BUILTIN_BOARDS, compile_drop

    uuid = taskwarrior.export(["+waiting"])[0]["uuid"]
    verb, mods = compile_drop(
        next(c["drop"] for c in BUILTIN_BOARDS["gtd"]["columns"]
             if c["title"].endswith("next"))
    )
    taskwarrior.command([uuid], verb, mods)
    taskwarrior.refresh_lookups()
    after = taskwarrior.export([uuid])[0]
    assert "waiting" not in (after.get("tags") or [])
    # it now satisfies Next Actions (still has project:Work)
    assert uuid in {t["uuid"] for t in taskwarrior.export(
        shlex.split(_gtd_columns()["next"]))}
