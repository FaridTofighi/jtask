"""Global tag management — rename / remove a tag across every task."""

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


def _tags_of_desc(desc: str) -> list[str]:
    for tk in taskwarrior.export(["status.not:deleted"]):
        if tk.get("description") == desc:
            return [x for x in (tk.get("tags") or []) if not x.isupper()]
    return []


def test_tag_count(tw_env):
    taskwarrior.add(["one", "+alpha", "+work"])
    taskwarrior.add(["two", "+alpha"])
    taskwarrior.add(["three", "+beta"])
    assert taskwarrior.tag_count("alpha") == 2
    assert taskwarrior.tag_count("+alpha") == 2      # leading '+' tolerated
    assert taskwarrior.tag_count("nope") == 0


def test_rename_tag_across_all_tasks(tw_env):
    taskwarrior.add(["a", "+draft"])
    taskwarrior.add(["b", "+draft", "+urgent"])
    taskwarrior.command(["1"], "done")               # also rename on completed

    n = taskwarrior.rename_tag("draft", "review")
    assert n == 2
    taskwarrior.refresh_lookups()
    assert "draft" not in taskwarrior.list_tags()
    assert "review" in taskwarrior.list_tags()
    assert set(_tags_of_desc("b")) == {"review", "urgent"}
    assert _tags_of_desc("a") == ["review"]           # renamed on the completed one too


def test_remove_tag_across_all_tasks(tw_env):
    taskwarrior.add(["a", "+spam", "+keep"])
    taskwarrior.add(["b", "+spam"])

    n = taskwarrior.remove_tag("spam")
    assert n == 2
    taskwarrior.refresh_lookups()
    assert "spam" not in taskwarrior.list_tags()
    assert _tags_of_desc("a") == ["keep"]


def test_tag_ops_on_unused_tag_are_noops(tw_env):
    taskwarrior.add(["a", "+real"])
    assert taskwarrior.remove_tag("ghost") == 0
    assert taskwarrior.rename_tag("ghost", "spirit") == 0
    assert taskwarrior.rename_tag("real", "real") == 0   # same name
