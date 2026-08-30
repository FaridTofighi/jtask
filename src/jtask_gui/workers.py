"""Run every ``task`` subprocess call off the UI thread.

Usage::

    submit(lambda: reports.report_next(filter_args), on_ok=self._populate,
           on_err=self._show_error)

Nothing in the GUI calls ``jtask.taskwarrior`` / ``jtask.reports`` on the main
thread — a blocking ``task export`` on a 1000-task database would freeze the UI.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from jtask.errors import JtaskError

log = logging.getLogger("jtask_gui.workers")

_pool = QThreadPool.globalInstance()

# Keep strong refs to in-flight runnables so their signal objects are not
# garbage-collected mid-run.
_live: set[QRunnable] = set()


class _Signals(QObject):
    finished = pyqtSignal(object)
    # carries the exception itself (a JtaskError / TaskCommandError) so the UI
    # can surface the real exit code + stderr, not a flattened string.
    failed = pyqtSignal(object)


class TaskRunnable(QRunnable):
    """Wraps a zero-arg callable; emits ``finished(result)`` or ``failed(exc)``."""

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _Signals()

    def run(self) -> None:  # noqa: D401 - Qt entry point
        try:
            result = self._fn()
        except JtaskError as exc:
            self.signals.failed.emit(exc)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("background task failed:\n%s", traceback.format_exc())
            self.signals.failed.emit(
                JtaskError(f"خطای غیرمنتظره: {exc}\n(جزئیات در فایل لاگ ثبت شد.)")
            )
        else:
            self.signals.finished.emit(result)


def submit(
    fn: Callable[[], Any],
    on_ok: Callable[[Any], None],
    on_err: Callable[[Any], None] | None = None,
) -> TaskRunnable:
    """Schedule *fn* on the global pool and wire its result to the callbacks."""
    runnable = TaskRunnable(fn)
    runnable.signals.finished.connect(on_ok)
    if on_err is not None:
        runnable.signals.failed.connect(on_err)
    _live.add(runnable)
    runnable.signals.finished.connect(lambda *_a: _live.discard(runnable))
    runnable.signals.failed.connect(lambda *_a: _live.discard(runnable))
    _pool.start(runnable)
    return runnable


def wait_for_done(msecs: int = 5000) -> bool:
    """Block until all pooled tasks finish (used by tests)."""
    return _pool.waitForDone(msecs)
