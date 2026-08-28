"""Compact settings dialog (M1 subset)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
)

from .settings import Settings
from .theme import THEMES


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("تنظیمات")
        self._settings = settings

        form = QFormLayout(self)

        self._theme = QComboBox()
        self._theme.addItems(list(THEMES))
        self._theme.setCurrentText(settings.theme)
        form.addRow("پوسته", self._theme)

        self._digits = QCheckBox("ارقام فارسی (۰-۹)")
        self._digits.setChecked(settings.persian_digits)
        form.addRow("", self._digits)

        self._due_soon = QSpinBox()
        self._due_soon.setRange(1, 30)
        self._due_soon.setValue(settings.due_soon_days)
        self._due_soon.setSuffix(" روز")
        form.addRow("آستانهٔ «نزدیک سررسید»", self._due_soon)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _accept(self) -> None:
        self._settings.theme = self._theme.currentText()
        self._settings.persian_digits = self._digits.isChecked()
        self._settings.due_soon_days = self._due_soon.value()
        self._settings.sync()
        self.accept()
