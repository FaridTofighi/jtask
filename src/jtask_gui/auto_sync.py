"""Automatic periodic ``task sync`` — one execution path, shared with the
Sync Manager's manual button.

`AutoSyncManager` owns the single concurrency guard (`_running`): the manual
Sync button (via :class:`~jtask_gui.widgets.sync_dialog.SyncManagerDialog`)
and the interval timer both call :meth:`run`, and `run` refuses to start a
second attempt while one is in flight. A timer tick that lands on a busy
manager is *dropped*, not queued — the next scheduled tick tries again.

Modelled on :class:`~jtask_gui.notifications.NotificationManager` (a `QObject`
with a `QTimer`, `start` / `stop` / `reconfigure` driven by `Settings`).
"""

from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from jtask import taskwarrior

from .settings import Settings
from .workers import submit


class AutoSyncManager(QObject):
    #: emitted when an attempt starts — arg is the source ("auto" / "manual")
    syncStarted = pyqtSignal(str)
    #: source, ISO-8601 local timestamp just stored as ``settings.last_sync``
    syncSucceeded = pyqtSignal(str, str)
    #: source, the raising exception (never swallowed — surfaced to the caller)
    syncFailed = pyqtSignal(str, object)

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._running = False
        self._stopped = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # --- state ----------------------------------------------

    def is_running(self) -> bool:
        return self._running

    def interval_ms(self) -> int:
        return max(
            Settings.AUTOSYNC_FLOOR_SEC, self._settings.autosync_interval_sec
        ) * 1000

    # --- lifecycle -----------------------------------------

    def start(self) -> None:
        self._stopped = False
        self._timer.start(self.interval_ms())

    def stop(self) -> None:
        # Mirrors NotificationManager.stop — the flag also blocks a tick that
        # is already queued in the event loop from scheduling a worker after
        # teardown has drained the pool.
        self._stopped = True
        self._timer.stop()

    def reconfigure(self) -> None:
        """Apply the current ``settings`` — call after the toggle or the
        interval field changes. Takes effect at once, no restart."""
        self.stop()
        if self._settings.autosync_enabled:
            self.start()

    # --- execution ----------------------------------------

    def _tick(self) -> None:
        if self._stopped or not self._settings.autosync_enabled:
            return
        if self._running:
            return  # skip this tick entirely — wait for the next interval
        self.run("auto")

    def run(self, source: str) -> bool:
        """Start one sync attempt through the shared threaded path. Returns
        ``False`` (and does nothing) if an attempt is already running."""
        if self._running:
            return False
        self._running = True
        self.syncStarted.emit(source)
        submit(
            taskwarrior.synchronize,
            lambda _text, s=source: self._done(s),
            lambda err, s=source: self._failed(s, err),
        )
        return True

    def _done(self, source: str) -> None:
        self._running = False
        iso = dt.datetime.now().isoformat(timespec="seconds")
        self._settings.last_sync = iso
        self.syncSucceeded.emit(source, iso)

    def _failed(self, source: str, err: object) -> None:
        self._running = False
        self.syncFailed.emit(source, err)
