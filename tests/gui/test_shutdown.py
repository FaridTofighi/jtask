"""App teardown must not let a background worker abort the interpreter.

Regression: confirming the language/calendar restart raised
``RuntimeError: wrapped C/C++ object of type _Signals has been deleted`` from
``workers.TaskRunnable.run`` → ``Aborted`` — a worker thread outlived the event
loop and emitted onto a freed signal object.
"""

from __future__ import annotations

import sys
import time


def test_run_survives_a_deleted_signal_object(qapp):
    from jtask_gui.workers import TaskRunnable

    r = TaskRunnable(lambda: "ok")

    class _Dead:
        # accessing an attribute raises, exactly like a freed sip wrapper
        def __getattr__(self, _name):
            raise RuntimeError("wrapped C/C++ object of type _Signals has been deleted")

    r.signals = _Dead()
    r.run()  # must not raise / abort — nothing is listening

    r2 = TaskRunnable(lambda: 1 / 0)  # exercises the failed path too
    r2.signals = _Dead()
    r2.run()


def test_shutdown_drains_in_flight_workers(qapp):
    from jtask_gui import workers

    done = []
    workers.submit(lambda: (time.sleep(0.15), "ok")[1], done.append)
    workers.shutdown()  # blocks until the worker finishes, then drains the queue
    assert done == ["ok"]
    assert not workers._live


def test_restart_request_reexecs_and_avoids_startdetached(qapp, monkeypatch):
    import jtask_gui.app as app_mod

    monkeypatch.setattr(app_mod, "_restart_requested", False)
    calls = {}
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QApplication.quit", lambda: calls.setdefault("quit", True)
    )
    app_mod.request_restart()
    assert app_mod._restart_requested is True
    assert calls.get("quit") is True

    # _reexec replaces the process image — patch os.execv so the test survives
    execv = {}
    monkeypatch.setattr("os.execv", lambda exe, args: execv.setdefault("a", (exe, args)))
    app_mod._reexec()
    assert execv["a"][0] == sys.executable


def test_qt_message_handler_suppresses_portal_noise(qapp, caplog):
    import logging

    from jtask_gui import app as app_mod

    app_mod._QT_HANDLER_INSTALLED = False
    app_mod._install_qt_message_handler()

    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    # grab the installed handler by re-installing and capturing the previous
    handler = qInstallMessageHandler(None)
    qInstallMessageHandler(handler)

    with caplog.at_level(logging.WARNING, logger="jtask_gui.qt"):
        handler(
            QtMsgType.QtWarningMsg, None,
            'Failed to register with host portal ... Could not register app ID',
        )
        handler(QtMsgType.QtWarningMsg, None, "some other real warning")

    msgs = [r.message for r in caplog.records]
    assert "some other real warning" in msgs
    assert not any("host portal" in m for m in msgs)


def test_build_application_wires_teardown(qapp, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui import workers
    from jtask_gui.app import build_application

    app, window = build_application([])
    window.refresh_all()
    window._notify.poll()

    # what aboutToQuit runs, invoked directly: stop polling + drain, no abort
    window._notify.stop()
    workers.shutdown()
    assert not workers._live
    assert not window._notify._timer.isActive()

    # a poll that sneaks in after stop() (pending singleShot) must not resubmit
    before = len(workers._live)
    window._notify.poll()
    assert len(workers._live) == before
