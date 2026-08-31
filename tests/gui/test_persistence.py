"""M4-review: settings / window / onboarding state must survive a 'restart'."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QByteArray, QSettings


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point QSettings at an isolated store and clear it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QSettings("jtask", "jtask-gui").clear()
    QSettings("jtask", "jtask-gui").sync()
    yield


def _fresh():
    """A brand-new Settings instance — simulates the next process launch."""
    from jtask_gui.settings import Settings

    return Settings()


def test_dialog_value_survives_restart(store):
    s1 = _fresh()
    s1.theme = "light"
    s1.due_soon_days = 12
    s1.notifications_enabled = True
    s1.notify_states = ["overdue", "soon"]
    s1.quiet_hours = (23, 6)
    s1.sync()
    del s1

    s2 = _fresh()
    assert s2.theme == "light"
    assert s2.due_soon_days == 12
    assert s2.notifications_enabled is True
    assert set(s2.notify_states) == {"overdue", "soon"}
    assert s2.quiet_hours == (23, 6)


def test_wizard_done_flag_survives_restart(store):
    s1 = _fresh()
    assert s1.wizard_done is False
    s1.wizard_done = True
    del s1
    assert _fresh().wizard_done is True


def test_window_geometry_survives_restart(store):
    s1 = _fresh()
    geo = QByteArray(b"\x01\x02\x03geometry")
    state = QByteArray(b"\x04\x05\x06state")
    s1.save_window(geo, state)
    del s1

    s2 = _fresh()
    assert bytes(s2.window_geometry()) == bytes(geo)
    assert bytes(s2.window_state()) == bytes(state)


def test_columns_and_saved_filters_survive_restart(store):
    s1 = _fresh()
    s1.save_columns(["id", "description"], ["urgency"], {"id": 60})
    s1.save_filter("مهم", "+مهم status:pending")
    del s1

    s2 = _fresh()
    order, hidden, widths = s2.columns()
    assert order == ["id", "description"]
    assert widths == {"id": 60}
    assert s2.saved_filters() == {"مهم": "+مهم status:pending"}


def test_taskwarrior_overrides_survive_restart(store):
    s1 = _fresh()
    assert s1.task_bin == "" and s1.taskdata == "" and s1.taskrc == ""
    s1.task_bin = "/opt/task/bin/task"
    s1.taskdata = "/data/tw"
    s1.taskrc = "/home/x/.taskrc"
    del s1

    s2 = _fresh()
    assert s2.task_bin == "/opt/task/bin/task"
    assert s2.taskdata == "/data/tw"
    assert s2.taskrc == "/home/x/.taskrc"


def test_reset_columns_forgets_persisted_layout(store):
    s1 = _fresh()
    s1.save_columns(["id", "description"], ["urgency"], {"id": 60})
    s1.reset_columns()
    del s1

    order, hidden, widths = _fresh().columns()
    assert order == [] and hidden == [] and widths == {}


def test_app_applies_taskwarrior_overrides_before_use(store):
    import os

    from jtask_gui import app

    s = _fresh()
    s.task_bin = "/custom/task"
    s.taskdata = "/custom/data"

    saved = {k: os.environ.get(k) for k in ("JTASK_TASK_BIN", "TASKDATA", "TASKRC")}
    try:
        app._apply_taskwarrior_overrides(s)
        assert os.environ["JTASK_TASK_BIN"] == "/custom/task"
        assert os.environ["TASKDATA"] == "/custom/data"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_settings_dialog_reopened_shows_saved_values(qtbot, store):
    from jtask_gui.settings import Settings
    from jtask_gui.settings_dialog import SettingsDialog

    s = Settings()
    d1 = SettingsDialog(s)
    qtbot.addWidget(d1)
    d1._theme.setCurrentText("روز")
    d1._digits.setChecked(False)
    d1._due_soon.setValue(9)
    d1._notify.setChecked(True)
    d1._interval.setValue(45)
    d1._accept()

    d2 = SettingsDialog(s)          # reopened, same session
    qtbot.addWidget(d2)
    assert d2._theme.currentText() == "روز"
    assert d2._digits.isChecked() is False
    assert d2._due_soon.value() == 9
    assert d2._notify.isChecked() is True
    assert d2._interval.value() == 45

    d3 = SettingsDialog(Settings())  # reopened after a "restart"
    qtbot.addWidget(d3)
    assert d3._theme.currentText() == "روز"
    assert d3._interval.value() == 45


def test_settings_always_targets_the_jtask_store(store):
    """Every Settings instance reads/writes the same explicit org/app pair,
    independent of whatever name the running QApplication happens to carry."""
    s = _fresh()
    assert s._s.organizationName() == "jtask"
    assert s._s.applicationName() == "jtask-gui"
    assert "jtask-gui" in s._s.fileName()


def test_app_identity_is_set_before_qapplication_construction():
    """The org / app / desktop-file identity is set before the QApplication is
    constructed — re-setting it afterwards makes Qt re-register the app-id with
    the desktop portal (a noisy warning)."""
    import inspect

    from jtask_gui import app

    src = inspect.getsource(app.build_application)
    construct_at = src.index("QApplication.instance() or QApplication(")
    for setter in ("setApplicationName", "setOrganizationName", "setDesktopFileName"):
        first = src.index(setter)
        assert first < construct_at, f"{setter} runs after QApplication is constructed"
        assert src.count(setter) == 1, f"{setter} is set more than once"
