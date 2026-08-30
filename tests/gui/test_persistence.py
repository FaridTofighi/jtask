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


def test_app_bootstrap_sets_identity_before_first_settings_use():
    """build_application sets the identity, then creates Settings."""
    import inspect

    from jtask_gui import app

    src = inspect.getsource(app.build_application)
    org_at = src.index("setOrganizationName")
    settings_at = src.index("Settings()")
    assert org_at < settings_at, "org/app name must be set before Settings() is built"
