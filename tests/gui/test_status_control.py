"""Feature: one contextual Status control in the detail panel — shows the
task's effective state and only the transitions valid from it.

Presentation decision: a plain row of buttons, not a SegmentedControl (that
keeps one button `checked` to represent a *value*; status transitions are
momentary *actions*) and not a hidden menu (discoverability is the point —
reopen had no in-panel action before). All actions route through the app's
existing write paths (`_start_stop` / `_bulk` "done" / `_delete` /
`_save_task`), so they stay undoable with no parallel implementation.
"""

from __future__ import annotations

import pytest

# --- core: the effective-state model --------------------------------

def test_effective_status_derives_active_and_waiting():
    from jtask import reports

    assert reports.effective_status({"status": "pending"}) == "pending"
    assert reports.effective_status(
        {"status": "pending", "start": "20260101T000000Z"}
    ) == "active"
    # modern Taskwarrior reports a waiting task as status:pending + future wait
    assert reports.effective_status(
        {"status": "pending", "wait": "20990101T000000Z"}
    ) == "waiting"
    # a past wait is not waiting
    assert reports.effective_status(
        {"status": "pending", "wait": "20000101T000000Z"}
    ) == "pending"
    # waiting wins over started
    assert reports.effective_status(
        {"status": "pending", "wait": "20990101T000000Z", "start": "20260101T000000Z"}
    ) == "waiting"
    assert reports.effective_status({"status": "completed"}) == "completed"
    assert reports.effective_status({"status": "deleted"}) == "deleted"


# --- the control offers exactly the valid actions per state ---------

@pytest.mark.parametrize(
    "setup, state, actions",
    [
        (lambda tw, u: None, "pending", ["start", "done", "delete"]),
        (lambda tw, u: tw.command([u], "start"), "active", ["stop", "done", "delete"]),
        (lambda tw, u: tw.command([u], "modify", ["wait:2099-01-01"]),
         "waiting", ["unwait", "start", "done", "delete"]),
        (lambda tw, u: tw.command([u], "done"), "completed", ["reopen"]),
        (lambda tw, u: tw.command([u], "delete"), "deleted", ["reopen"]),
    ],
)
def test_control_offers_exactly_the_valid_actions(tw_env, qapp, setup, state, actions):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.detail_panel import DetailPanel

    tw.add(["t"])
    u = tw.export()[0]["uuid"]
    setup(tw, u)

    panel = DetailPanel()
    panel.load_task(tw.export([u])[0])
    assert panel._status.state == state
    assert panel._status.action_ids() == actions
    # never an invalid transition
    if state in ("completed", "deleted"):
        assert "start" not in panel._status.action_ids()
        assert "done" not in panel._status.action_ids()


# --- each action performs the real transition and is undoable -------

@pytest.fixture
def win(qapp, qtbot, tw_env):
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["Solo"])
    tw.refresh_lookups()
    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    return w


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()


def _fresh(uuid):
    from jtask import taskwarrior as tw

    return tw.export([uuid])[0]


@pytest.mark.parametrize(
    "action, precondition, expect",
    [
        ("start", lambda tw, u: None, lambda t: bool(t.get("start"))),
        ("stop", lambda tw, u: tw.command([u], "start"), lambda t: not t.get("start")),
        ("done", lambda tw, u: None, lambda t: t["status"] == "completed"),
        ("reopen", lambda tw, u: tw.command([u], "done"), lambda t: t["status"] == "pending"),
    ],
)
def test_action_makes_the_real_transition_and_undoes(
    win, qapp, monkeypatch, action, precondition, expect
):
    from jtask import taskwarrior as tw

    u = tw.export(["description:Solo"])[0]["uuid"]
    precondition(tw, u)
    tw.refresh_lookups()
    win._show_detail(tw.export([u])[0])
    _drain(qapp)
    before = _fresh(u)

    win._detail._status_action(action)
    _drain(qapp)
    assert expect(_fresh(u)), f"{action} did not transition"

    # the write went through the normal reversible path — `task undo` restores
    # it (the same undo the panel's own undo action runs; called directly here
    # to skip its confirm dialog, which blocks headless)
    win._write(lambda: tw.run(["undo"]), "undone")
    _drain(qapp)
    after = _fresh(u)
    assert bool(after.get("start")) == bool(before.get("start"))
    assert after["status"] == before["status"]


def test_delete_action_confirms_then_deletes_and_undoes(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw

    monkeypatch.setattr("jtask_gui.mixins.task_lifecycle.confirm", lambda *a, **k: True)
    u = tw.export(["description:Solo"])[0]["uuid"]
    win._show_detail(tw.export([u])[0])
    _drain(qapp)

    win._detail._status_action("delete")
    _drain(qapp)
    assert _fresh(u)["status"] == "deleted"
    # reopen now reachable directly from the panel
    assert win._detail._status.action_ids() == ["reopen"]

    win._write(lambda: tw.run(["undo"]), "undone")
    _drain(qapp)
    assert _fresh(u)["status"] == "pending"


def test_clear_wait_action_removes_the_wait_date_and_state_updates(win, qapp):
    from jtask import taskwarrior as tw

    u = tw.export(["description:Solo"])[0]["uuid"]
    tw.command([u], "modify", ["wait:2099-01-01"])
    tw.refresh_lookups()
    win._show_detail(tw.export([u])[0])
    _drain(qapp)
    assert win._detail._status.state == "waiting"

    win._detail._status_action("unwait")
    _drain(qapp)
    assert not _fresh(u).get("wait")
    assert win._detail._status.state == "pending"
