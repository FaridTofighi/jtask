"""Unit tests for pure text-parsing helpers in ``jtask.taskwarrior`` — kept
separate from the ``tw_env``-backed integration tests since these exercise
known real-world *output shapes*, independent of whichever Taskwarrior
version happens to be on the machine running the suite.
"""

from __future__ import annotations

from jtask.taskwarrior import _parse_undo_preview

# --- fixtures: verbatim (trimmed) output captured from real binaries -------

# Taskwarrior 3.5.0 — names the count explicitly.
_TW35_PREVIEW = """The following 6 operations would be reverted:
Uuid                                 Modification
28c25e0b-0383-4bd7-9e5c-4230302e9b0d Create task
                                     Add property 'description' with value 'tw35 task'
                                     Add property 'status' with value 'pending'

The undo command is not reversible.  Are you sure you want to revert to the previous state? (yes/no)"""

_TW35_EMPTY = "No operations to undo.\nCould not undo: other operations have occurred."

# Taskwarrior 2.6.2 — a bare Prior/Current Values diff table, no count
# phrasing anywhere; captured against the real apt-installed 2.6.2 binary
# (docs/taskwarrior-compatibility.md).
_TW262_PREVIEW = """
The last modification was made 2026-09-05

             Prior Values                          Current Values
-----------  ------------------------------------  ------------------------------------
description  test undo preview task                test undo preview task
status       pending                               pending
priority                                           H

The undo command is not reversible.  Are you sure you want to revert to the previous state? (yes/no) No changes made.
"""

_TW262_EMPTY = "There are no recorded transactions to undo.\n"


def test_undo_preview_parses_taskwarrior_3x_explicit_count():
    r = _parse_undo_preview(_TW35_PREVIEW)
    assert r["empty"] is False
    assert r["count"] == 6
    assert "would be reverted" in r["text"]
    # the yes/no confirmation prompt itself is stripped from the shown text
    assert "Are you sure" not in r["text"]


def test_undo_preview_parses_taskwarrior_3x_nothing_to_undo():
    r = _parse_undo_preview(_TW35_EMPTY)
    assert r == {"text": _TW35_EMPTY, "count": 0, "empty": True}


def test_undo_preview_falls_back_to_count_one_for_older_bare_diff_table():
    """Taskwarrior <3.0 never says 'N operations would be reverted' — just a
    Prior/Current Values table. It also only ever reverts one transaction per
    invocation, so count=1 isn't just a guess, it's accurate."""
    r = _parse_undo_preview(_TW262_PREVIEW)
    assert r["empty"] is False
    assert r["count"] == 1
    assert "Prior Values" in r["text"]
    assert "Are you sure" not in r["text"]


def test_undo_preview_recognizes_older_nothing_to_undo_wording():
    """Regression: 'There are no recorded transactions to undo.' matched none
    of the original hardcoded phrases, so this case fell through to
    count=1/empty=False — the GUI would have offered to revert an operation
    that doesn't exist."""
    r = _parse_undo_preview(_TW262_EMPTY)
    assert r["empty"] is True
    assert r["count"] == 0
