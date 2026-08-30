"""Friendly recurrence builder that maps to Taskwarrior ``recur:`` syntax."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QSpinBox, QWidget

from .. import tokens as tok
from ..i18n import t

_UNITS = [
    ("recur.unit.day", "d"), ("recur.unit.week", "weekly"),
    ("recur.unit.month", "monthly"), ("recur.unit.year", "yearly"),
]
_NAMED = {"daily": (1, 0), "weekly": (1, 1), "monthly": (1, 2), "yearly": (1, 3)}


class RecurrenceBuilder(QWidget):
    """Emits ``recurrenceChanged(str)`` — the ``recur:`` value ('' when none)."""

    recurrenceChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(tok.SP_6)

        self._enabled = QComboBox()
        self._enabled.addItems([t("recur.none"), t("recur.every")])
        self._enabled.currentIndexChanged.connect(self._on_mode)
        row.addWidget(self._enabled)

        self._n = QSpinBox()
        self._n.setRange(1, 999)
        self._n.setFixedWidth(64)
        self._n.valueChanged.connect(self._changed)
        row.addWidget(self._n)

        self._unit = QComboBox()
        for label_key, _ in _UNITS:
            self._unit.addItem(t(label_key))
        self._unit.currentIndexChanged.connect(self._changed)
        row.addWidget(self._unit)
        row.addStretch(1)

        self._on_mode(0)

    def _on_mode(self, index: int) -> None:
        on = index == 1
        self._n.setVisible(on)
        self._unit.setVisible(on)
        self._changed()

    def set_value(self, recur: str) -> None:
        if not recur:
            self._enabled.setCurrentIndex(0)
            return
        self._enabled.setCurrentIndex(1)
        if recur in _NAMED:
            n, unit = _NAMED[recur]
        else:
            digits = "".join(c for c in recur if c.isdigit())
            n = int(digits) if digits else 1
            unit = 0 if "d" in recur else 1 if "w" in recur else 2 if "m" in recur else 3
        self._n.setValue(n)
        self._unit.setCurrentIndex(unit)

    def value(self) -> str:
        if self._enabled.currentIndex() == 0:
            return ""
        n = self._n.value()
        _, token = _UNITS[self._unit.currentIndex()]
        if token == "d":
            return f"{n}d"
        return token if n == 1 else f"{n}{token.rstrip('ly')}s"

    def _changed(self, *_a) -> None:
        self.recurrenceChanged.emit(self.value())
