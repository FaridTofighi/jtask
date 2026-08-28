"""Friendly recurrence builder that maps to Taskwarrior ``recur:`` syntax."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QSpinBox, QWidget

_UNITS = [
    ("روز", "d"),
    ("هفته", "weekly"),
    ("ماه", "monthly"),
    ("سال", "yearly"),
]
_NAMED = {"daily": (1, "d"), "weekly": (1, "weekly"), "monthly": (1, "monthly"),
          "yearly": (1, "yearly")}


class RecurrenceBuilder(QWidget):
    """Emits ``recurrenceChanged(str)`` — the ``recur:`` value ('' when none)."""

    recurrenceChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._enabled = QComboBox()
        self._enabled.addItems(["بدون تکرار", "هر…"])
        self._enabled.currentIndexChanged.connect(self._changed)
        row.addWidget(self._enabled)

        self._n = QSpinBox()
        self._n.setRange(1, 999)
        self._n.valueChanged.connect(self._changed)
        row.addWidget(self._n)

        self._unit = QComboBox()
        for label, _ in _UNITS:
            self._unit.addItem(label)
        self._unit.currentIndexChanged.connect(self._changed)
        row.addWidget(self._unit)

        self._raw = QLineEdit()
        self._raw.setPlaceholderText("یا مقدار خام: 2weeks")
        self._raw.editingFinished.connect(self._changed)
        row.addWidget(self._raw, 1)

    def set_value(self, recur: str) -> None:
        if not recur:
            self._enabled.setCurrentIndex(0)
            return
        self._enabled.setCurrentIndex(1)
        if recur in _NAMED:
            n, unit = _NAMED[recur]
            self._n.setValue(n)
        else:
            self._raw.setText(recur)

    def value(self) -> str:
        if self._enabled.currentIndex() == 0:
            return ""
        if self._raw.text().strip():
            return self._raw.text().strip()
        n = self._n.value()
        _, token = _UNITS[self._unit.currentIndex()]
        if token == "d":
            return f"{n}d"
        return token if n == 1 else f"{n}{token.rstrip('ly')}s"

    def _changed(self, *_a) -> None:
        self.recurrenceChanged.emit(self.value())
