"""Shared fixtures for the GUI test suite (headless)."""

from __future__ import annotations

import datetime
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import jdatetime  # noqa: E402
import pytest  # noqa: E402

from jtask import jalali, taskwarrior  # noqa: E402

TEHRAN = datetime.timezone(datetime.timedelta(hours=3, minutes=30))

# ---------------------------------------------------------------------------
# pytest-qt is the preferred provider of the ``qapp`` / ``qtbot`` fixtures.
# When it is not installed we supply minimal stand-ins here so the GUI suite
# still runs (and, crucially, so a test that touches Qt without a live
# QApplication skips/handles it gracefully instead of aborting the whole
# interpreter with ``Fatal Python error: Aborted``).
# ---------------------------------------------------------------------------
try:  # pragma: no cover - trivial import guard
    import pytestqt  # noqa: F401

    _HAVE_PYTEST_QT = True
except ImportError:  # pragma: no cover - exercised only on stripped envs
    _HAVE_PYTEST_QT = False


if not _HAVE_PYTEST_QT:
    from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
    from PyQt6.QtTest import QTest  # noqa: E402
    from PyQt6.QtWidgets import QApplication  # noqa: E402

    @pytest.fixture(scope="session")
    def qapp():
        app = QApplication.instance() or QApplication([])
        yield app

    class _SignalWaiter:
        def __init__(self, signal, timeout):
            self._signal = signal
            self._timeout = timeout
            self.signal_triggered = False

        def _on(self, *_a):
            self.signal_triggered = True
            self._loop.quit()

        def __enter__(self):
            self._loop = QEventLoop()
            self._signal.connect(self._on)
            return self

        def __exit__(self, *exc):
            if not self.signal_triggered:
                QTimer.singleShot(self._timeout, self._loop.quit)
                self._loop.exec()
            try:
                self._signal.disconnect(self._on)
            except (TypeError, RuntimeError):
                pass
            if exc[0] is None and not self.signal_triggered:
                raise AssertionError("signal was not emitted within timeout")
            return False

    class _QtBot:
        """The sliver of the pytest-qt ``qtbot`` API the suite actually uses."""

        def __init__(self, app):
            self._app = app
            self._widgets = []

        def addWidget(self, widget):  # noqa: N802 - match pytest-qt
            self._widgets.append(widget)

        def wait(self, ms):
            QTest.qWait(int(ms))

        def waitSignal(self, signal, timeout=5000, raising=True):  # noqa: N802
            return _SignalWaiter(signal, timeout)

        def waitUntil(self, predicate, timeout=5000):  # noqa: N802
            step = 20
            waited = 0
            while not predicate() and waited < timeout:
                QTest.qWait(step)
                waited += step
            assert predicate(), "condition not met within timeout"

        def _cleanup(self):
            for w in self._widgets:
                try:
                    w.close()
                    w.deleteLater()
                except RuntimeError:
                    pass
            self._widgets.clear()
            self._app.processEvents()

    @pytest.fixture
    def qtbot(qapp):
        bot = _QtBot(qapp)
        yield bot
        bot._cleanup()


@pytest.fixture(autouse=True)
def _tz(monkeypatch):
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)


@pytest.fixture(autouse=True)
def _drain_workers():
    """Make sure no background worker from a prior test is still running —
    a straggler could re-populate a lookup cache with the wrong TASKRC."""
    yield
    try:
        from jtask_gui.workers import wait_for_done

        wait_for_done(3000)
    except Exception:  # noqa: BLE001
        pass
    taskwarrior.refresh_lookups()


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    monkeypatch.setenv("JTASK_CONFIG_DIR", str(tmp_path / "cfg"))
    taskwarrior.refresh_lookups()
    yield
    taskwarrior.refresh_lookups()


@pytest.fixture
def today_1403_07_10():
    return jdatetime.date(1403, 7, 10)
