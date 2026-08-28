"""Settings dialog: appearance + notifications."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .settings import Settings
from .theme import THEMES
from .widgets.fa_spinbox import FaSpinBox

_NOTIFY_STATES = [("عقب‌افتاده", "overdue"), ("سررسید امروز", "today"),
                  ("نزدیک سررسید", "soon")]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("تنظیمات")
        self.setMinimumWidth(420)
        self._settings = settings

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self._theme = QComboBox()
        self._theme.addItems(list(THEMES))
        self._theme.setCurrentText(settings.theme)
        form.addRow("پوسته", self._theme)

        self._digits = QCheckBox("ارقام فارسی (۰-۹)")
        self._digits.setChecked(settings.persian_digits)
        form.addRow("", self._digits)

        self._due_soon = FaSpinBox()
        self._due_soon.setRange(1, 30)
        self._due_soon.setValue(settings.due_soon_days)
        self._due_soon.setSuffix(" روز")
        form.addRow("آستانهٔ «نزدیک سررسید»", self._due_soon)

        sec = QLabel("اعلان‌ها")
        sec.setObjectName("Section")
        root.addWidget(sec)
        nform = QFormLayout()
        root.addLayout(nform)

        self._notify = QCheckBox("اعلان دسکتاپ فعال باشد")
        self._notify.setChecked(settings.notifications_enabled)
        nform.addRow("", self._notify)

        self._states: dict[str, QCheckBox] = {}
        states_row = QHBoxLayout()
        enabled = set(settings.notify_states)
        for label, key in _NOTIFY_STATES:
            cb = QCheckBox(label)
            cb.setChecked(key in enabled)
            self._states[key] = cb
            states_row.addWidget(cb)
        sw = QWidget()
        sw.setLayout(states_row)
        nform.addRow("وضعیت‌ها", sw)

        self._interval = FaSpinBox()
        self._interval.setRange(1, 240)
        self._interval.setValue(settings.notify_interval_min)
        self._interval.setSuffix(" دقیقه")
        nform.addRow("بازهٔ بررسی", self._interval)

        qs, qe = settings.quiet_hours
        self._quiet_start = FaSpinBox()
        self._quiet_start.setRange(0, 23)
        self._quiet_start.setValue(qs)
        self._quiet_end = FaSpinBox()
        self._quiet_end.setRange(0, 23)
        self._quiet_end.setValue(qe)
        quiet_row = QHBoxLayout()
        quiet_row.addWidget(QLabel("از"))
        quiet_row.addWidget(self._quiet_start)
        quiet_row.addWidget(QLabel("تا"))
        quiet_row.addWidget(self._quiet_end)
        quiet_row.addStretch(1)
        qw = QWidget()
        qw.setLayout(quiet_row)
        nform.addRow("ساعات سکوت", qw)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("تأیید")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("انصراف")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        s = self._settings
        s.theme = self._theme.currentText()
        s.persian_digits = self._digits.isChecked()
        s.due_soon_days = self._due_soon.value()
        s.notifications_enabled = self._notify.isChecked()
        s.notify_states = [k for k, cb in self._states.items() if cb.isChecked()]
        s.notify_interval_min = self._interval.value()
        s.quiet_hours = (self._quiet_start.value(), self._quiet_end.value())
        s.sync()
        self.accept()
