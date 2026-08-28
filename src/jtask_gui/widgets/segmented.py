"""A small segmented (single-choice) button control with a visible active state."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    """Exclusive row of toggle buttons. ``changed(value)`` fires on selection."""

    changed = pyqtSignal(object)

    def __init__(self, options: list[tuple[str, object]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._values: list[object] = []

        for i, (label, value) in enumerate(options):
            btn = QPushButton(label)
            btn.setObjectName("Segment")
            btn.setCheckable(True)
            btn.setAutoExclusive(False)
            btn.setProperty("pos", "only" if len(options) == 1
                            else "first" if i == 0
                            else "last" if i == len(options) - 1
                            else "mid")
            if i == 0:
                btn.setChecked(True)
            self._group.addButton(btn, i)
            self._values.append(value)
            row.addWidget(btn)

        self._group.idClicked.connect(lambda idx: self.changed.emit(self._values[idx]))

    def value(self) -> object:
        return self._values[self._group.checkedId()]

    def set_value(self, value: object) -> None:
        if value in self._values:
            self._group.button(self._values.index(value)).setChecked(True)
