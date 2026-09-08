"""Auto-sync — configurable interval + status-bar notification.

Every automatic sync runs through the same `AutoSyncManager.run` that the
manual Sync button uses; overlapping attempts are refused by one shared guard;
results land in the status bar (clickable on failure), never a blocking dialog.
"""

from __future__ import annotations

import pytest

from jtask.errors import TaskCommandError


@pytest.fixture
def s(qapp, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings

    return Settings()


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()


# --- settings / persistence -----------------------------------

def test_autosync_off_by_default_and_persists(s):
    from jtask_gui.settings import Settings

    assert s.autosync_enabled is False
    assert s.autosync_interval_sec == 600

    s.autosync_enabled = True
    s.autosync_interval_sec = 300
    fresh = Settings()
    assert fresh.autosync_enabled is True
    assert fresh.autosync_interval_sec == 300


def test_interval_floor_is_enforced(s):
    from jtask_gui.settings import Settings

    s.autosync_interval_sec = 5  # below the 60s floor
    assert Settings().autosync_interval_sec == Settings.AUTOSYNC_FLOOR_SEC == 60


# --- the timer ----------------------------------------------

def test_timer_uses_the_configured_interval_and_does_not_fire_early(qapp, s):
    from jtask_gui.auto_sync import AutoSyncManager

    s.autosync_enabled = True
    s.autosync_interval_sec = 120
    m = AutoSyncManager(s)
    started = []
    m.syncStarted.connect(started.append)

    m.start()
    assert m._timer.isActive()
    assert m._timer.interval() == 120_000
    qapp.processEvents()
    assert started == []  # a fresh start does not sync immediately


def test_interval_and_toggle_changes_take_effect_without_restart(qapp, s):
    from jtask_gui.auto_sync import AutoSyncManager

    s.autosync_enabled = True
    s.autosync_interval_sec = 600
    m = AutoSyncManager(s)
    m.reconfigure()
    assert m._timer.interval() == 600_000

    s.autosync_interval_sec = 90
    m.reconfigure()
    assert m._timer.isActive() and m._timer.interval() == 90_000

    s.autosync_enabled = False
    m.reconfigure()
    assert not m._timer.isActive()


# --- concurrency guard -------------------------------------

def test_run_refuses_a_second_concurrent_attempt(qapp, s, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.auto_sync import AutoSyncManager

    monkeypatch.setattr(tw, "synchronize", lambda: "Sync complete.")
    m = AutoSyncManager(s)
    ok = []
    m.syncSucceeded.connect(lambda src, iso: ok.append((src, iso)))

    assert m.run("manual") is True
    assert m.is_running()
    assert m.run("auto") is False  # refused while one is in flight

    _drain(qapp)
    assert not m.is_running()
    assert ok and ok[0][0] == "manual"
    assert s.last_sync


def test_timer_tick_is_dropped_while_syncing_and_not_queued(qapp, s, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.auto_sync import AutoSyncManager

    monkeypatch.setattr(tw, "synchronize", lambda: "Sync complete.")
    s.autosync_enabled = True
    m = AutoSyncManager(s)
    m.start()  # timer live (60s away — never fires during the test)
    started = []
    m.syncStarted.connect(started.append)

    m._running = True  # a sync (manual or automatic) is already in progress
    m._tick()
    m._tick()
    assert started == []  # ticks dropped, nothing submitted

    m._running = False
    m._tick()
    assert started == ["auto"]  # exactly one — the skipped ticks did not pile up
    m.stop()


# --- status-bar notification ------------------------------

@pytest.fixture
def win(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    _drain(qapp)
    return w


def test_status_bar_success_message_fades_like_a_transient(win, qapp):
    win._on_autosync_done("auto", "2026-09-08T14:30:00")
    assert win._op_status.state == "success"  # survives the concurrent refresh
    txt = win._op_status.text()
    assert "✓" in txt
    assert "۱۴۰۵" in txt or "1405" in txt  # the Jalali year of the timestamp
    assert win._op_status._fade.isActive()  # auto-fades
    _drain(qapp)


def test_status_bar_failure_is_clickable_and_opens_the_sync_manager(win):
    opened = []
    win._open_sync = lambda: opened.append(1)

    err = TaskCommandError("boom", returncode=1, stderr="network down", cmd=["task", "sync"])
    win._on_autosync_failed("auto", err)

    assert win._op_status.state == "failed"
    assert not win._op_status._fade.isActive()  # a failure stays put
    assert win._op_status._action is not None  # clickable
    win._op_status.mousePressEvent(None)
    assert opened == [1]  # opens the manager (full error), not a blocking dialog


def test_manual_sync_result_does_not_touch_the_status_bar(win):
    win._on_autosync_done("manual", "2026-09-08T14:30:00")
    assert win._op_status.state == "idle"
    win._on_autosync_failed("manual", RuntimeError("x"))
    assert win._op_status.state == "idle"


def test_a_new_operation_clears_a_stale_sync_failure_action(win):
    win._on_autosync_failed("auto", RuntimeError("x"))
    assert win._op_status._action is not None
    win._op_status.success("something else")
    assert win._op_status._action is None


# --- the dialog drives the shared manager ----------------

def test_sync_dialog_controls_reconfigure_the_shared_manager(qapp, s):
    from jtask_gui.auto_sync import AutoSyncManager
    from jtask_gui.widgets.sync_dialog import SyncManagerDialog

    mgr = AutoSyncManager(s)
    d = SyncManagerDialog(s, manager=mgr)
    d._interval.setValue(200)
    d._auto.setChecked(True)

    assert s.autosync_enabled is True
    assert s.autosync_interval_sec == 200
    assert mgr._timer.isActive() and mgr._timer.interval() == 200_000

    d._auto.setChecked(False)
    assert s.autosync_enabled is False
    assert not mgr._timer.isActive()


def test_sync_dialog_shares_the_concurrency_guard(qapp, s):
    from jtask_gui.auto_sync import AutoSyncManager
    from jtask_gui.widgets.sync_dialog import SyncManagerDialog

    mgr = AutoSyncManager(s)
    mgr._running = True  # an automatic sync is mid-flight
    d = SyncManagerDialog(s, manager=mgr)
    d._show_status({"configured": True, "kind": "local", "target": "/x"})

    d._run()  # must not start a second sync
    assert not d._go.isEnabled()
