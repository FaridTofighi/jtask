"""M4 — tray notifications, quiet hours, first-run wizard, packaging assets."""

from __future__ import annotations

import datetime

import pytest

from jtask import jalali
from jtask.rtl import set_digit_mode

TEHRAN = datetime.timezone(datetime.timedelta(hours=3, minutes=30))


@pytest.fixture(autouse=True)
def _digits_and_tz(monkeypatch):
    set_digit_mode(True)
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)
    yield
    set_digit_mode(True)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("JTASK_CONFIG_DIR", str(tmp_path))
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings

    return Settings()


def _mgr(settings, qtbot):
    from PyQt6.QtWidgets import QSystemTrayIcon

    from jtask_gui.notifications import NotificationManager

    tray = QSystemTrayIcon()
    mgr = NotificationManager(settings, tray)
    sent: list = []
    tray.showMessage = lambda *a: sent.append(a)  # type: ignore
    return mgr, sent


def _utc(days: int) -> str:
    d = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return d.strftime("%Y%m%dT%H%M%SZ")


# --- notification classification ---------------------------------

def test_multiple_overdue_are_batched_with_persian_digit_title(settings, qtbot):
    settings.notifications_enabled = True
    settings.notify_states = ["overdue"]
    mgr, sent = _mgr(settings, qtbot)

    tasks = [
        {"uuid": "a", "description": "دیرکرد ۱", "status": "pending", "due_gregorian": _utc(-3)},
        {"uuid": "b", "description": "دیرکرد ۲", "status": "pending", "due_gregorian": _utc(-1)},
        {"uuid": "c", "description": "بعداً", "status": "pending", "due_gregorian": _utc(30)},
    ]
    mgr._evaluate(tasks)
    assert len(sent) == 1  # batched
    assert "۲ کار" in sent[0][0]  # Persian digit in the title

    mgr._evaluate(tasks)  # nothing new -> no repeat
    assert len(sent) == 1


def test_classify_states_directly():
    from jtask_gui.notifications import _classify

    assert _classify({"status": "pending", "due_gregorian": _utc(-1)}, 3) == "overdue"
    assert _classify({"status": "pending", "due_gregorian": _utc(2)}, 3) == "soon"
    assert _classify({"status": "pending", "due_gregorian": _utc(30)}, 3) is None
    assert _classify({"status": "completed", "due_gregorian": _utc(-1)}, 3) is None


def test_state_not_enabled_is_skipped(settings, qtbot):
    settings.notifications_enabled = True
    settings.notify_states = ["overdue"]  # not 'soon'
    mgr, sent = _mgr(settings, qtbot)
    mgr._evaluate([{"uuid": "b", "description": "به‌زودی", "status": "pending",
                    "due_gregorian": _utc(1)}])
    assert sent == []


def test_single_overdue_uses_warning_icon(settings, qtbot):
    from PyQt6.QtWidgets import QSystemTrayIcon

    settings.notifications_enabled = True
    settings.notify_states = ["overdue"]
    mgr, sent = _mgr(settings, qtbot)
    mgr._evaluate([{"uuid": "a", "description": "x", "status": "pending",
                    "due_gregorian": _utc(-1)}])
    assert sent[0][2] == QSystemTrayIcon.MessageIcon.Warning


def test_quiet_hours_wrap_past_midnight(settings, qtbot, monkeypatch):
    settings.notifications_enabled = True
    settings.quiet_hours = (22, 7)
    mgr, _ = _mgr(settings, qtbot)

    monkeypatch.setattr("jtask_gui.notifications._current_hour", lambda: 23)
    assert mgr._in_quiet_hours() is True
    monkeypatch.setattr("jtask_gui.notifications._current_hour", lambda: 3)
    assert mgr._in_quiet_hours() is True
    monkeypatch.setattr("jtask_gui.notifications._current_hour", lambda: 12)
    assert mgr._in_quiet_hours() is False


# --- first-run wizard -----------------------------------------

def test_wizard_persists_choices(settings, qtbot):
    from jtask_gui.widgets.first_run import FirstRunWizard

    wiz = FirstRunWizard(settings)
    qtbot.addWidget(wiz)
    wiz._digits.setChecked(False)
    wiz._notify.setChecked(True)
    wiz._finish()

    assert settings.persian_digits is False
    assert settings.notifications_enabled is True
    assert settings.wizard_done is True


# --- packaging assets ----------------------------------------

def test_fa_spinbox_shows_persian_digits(qtbot):
    from jtask.rtl import set_digit_mode
    from jtask_gui.widgets.fa_spinbox import FaSpinBox

    set_digit_mode(True)
    sb = FaSpinBox()
    qtbot.addWidget(sb)
    sb.setRange(0, 100)
    sb.setValue(22)
    assert sb.text() == "۲۲"
    set_digit_mode(False)
    assert FaSpinBox().textFromValue(7) == "7"


def test_settings_dialog_persists_notification_prefs(qtbot, settings):
    from jtask_gui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(settings)
    qtbot.addWidget(dlg)
    dlg._notify.setChecked(True)
    dlg._states["soon"].setChecked(True)
    dlg._interval.setValue(30)
    dlg._quiet_start.setValue(23)
    dlg._quiet_end.setValue(6)
    dlg._accept()

    assert settings.notifications_enabled is True
    assert "soon" in settings.notify_states
    assert settings.notify_interval_min == 30
    assert settings.quiet_hours == (23, 6)


def test_app_icon_loads():
    from jtask_gui.app import app_icon

    assert not app_icon().isNull()


def test_desktop_file_is_valid():
    from pathlib import Path

    text = (Path(__file__).parents[2] / "packaging" / "jtask-gui.desktop").read_text()
    assert "Exec=jtask-gui" in text
    assert "StartupWMClass=jtask-gui" in text
    assert "Icon=jtask-gui" in text
