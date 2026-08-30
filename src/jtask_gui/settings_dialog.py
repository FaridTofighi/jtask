"""Settings dialog: appearance + language + notifications."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .i18n import t
from .settings import Settings
from .theme import THEMES
from .widgets.fa_spinbox import FaSpinBox

_NOTIFY_STATES = [
    ("settings.notify.state.overdue", "overdue"),
    ("settings.notify.state.today", "today"),
    ("settings.notify.state.soon", "soon"),
]
_LANGUAGES = [("settings.language.fa", "fa"), ("settings.language.en", "en")]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(420)
        self._settings = settings

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self._language = QComboBox()
        for key, code in _LANGUAGES:
            self._language.addItem(t(key), code)
        self._language.setCurrentIndex(
            max(0, [c for _, c in _LANGUAGES].index(settings.language))
            if settings.language in [c for _, c in _LANGUAGES]
            else 0
        )
        form.addRow(t("settings.language"), self._language)

        self._theme = QComboBox()
        self._theme.addItems(list(THEMES))
        self._theme.setCurrentText(settings.theme)
        form.addRow(t("settings.theme"), self._theme)

        self._digits = QCheckBox(t("settings.persian_digits"))
        self._digits.setChecked(settings.persian_digits)
        form.addRow("", self._digits)

        self._due_soon = FaSpinBox()
        self._due_soon.setRange(1, 30)
        self._due_soon.setValue(settings.due_soon_days)
        self._due_soon.setSuffix(t("settings.suffix.days"))
        form.addRow(t("settings.due_soon_threshold"), self._due_soon)

        sec = QLabel(t("settings.notifications"))
        sec.setObjectName("Section")
        root.addWidget(sec)
        nform = QFormLayout()
        root.addLayout(nform)

        self._notify = QCheckBox(t("settings.notify.enabled"))
        self._notify.setChecked(settings.notifications_enabled)
        nform.addRow("", self._notify)

        self._states: dict[str, QCheckBox] = {}
        states_row = QHBoxLayout()
        enabled = set(settings.notify_states)
        for key, state in _NOTIFY_STATES:
            cb = QCheckBox(t(key))
            cb.setChecked(state in enabled)
            self._states[state] = cb
            states_row.addWidget(cb)
        sw = QWidget()
        sw.setLayout(states_row)
        nform.addRow(t("settings.notify.states"), sw)

        self._interval = FaSpinBox()
        self._interval.setRange(1, 240)
        self._interval.setValue(settings.notify_interval_min)
        self._interval.setSuffix(t("settings.suffix.minutes"))
        nform.addRow(t("settings.notify.interval"), self._interval)

        qs, qe = settings.quiet_hours
        self._quiet_start = FaSpinBox()
        self._quiet_start.setRange(0, 23)
        self._quiet_start.setValue(qs)
        self._quiet_end = FaSpinBox()
        self._quiet_end.setRange(0, 23)
        self._quiet_end.setValue(qe)
        quiet_row = QHBoxLayout()
        quiet_row.addWidget(QLabel(t("word.from")))
        quiet_row.addWidget(self._quiet_start)
        quiet_row.addWidget(QLabel(t("word.to")))
        quiet_row.addWidget(self._quiet_end)
        quiet_row.addStretch(1)
        qw = QWidget()
        qw.setLayout(quiet_row)
        nform.addRow(t("settings.notify.quiet_hours"), qw)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("btn.confirm"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("btn.cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        s = self._settings
        s.theme = self._theme.currentText()

        # Resolution 1: a change here is an explicit user choice — record it so a
        # future language switch never silently rewrites the digit mode.
        if self._digits.isChecked() != s.persian_digits:
            s.digit_mode_user_overridden = True
        s.persian_digits = self._digits.isChecked()

        s.due_soon_days = self._due_soon.value()
        s.notifications_enabled = self._notify.isChecked()
        s.notify_states = [k for k, cb in self._states.items() if cb.isChecked()]
        s.notify_interval_min = self._interval.value()
        s.quiet_hours = (self._quiet_start.value(), self._quiet_end.value())

        new_lang = self._language.currentData()
        lang_changed = new_lang != s.language
        s.language = new_lang
        s.sync()

        if lang_changed:
            QMessageBox.information(
                self, t("settings.restart.title"), t("settings.restart.body")
            )
        self.accept()
