"""Raw Data tab — the task's Taskwarrior record exactly as stored (JSON)."""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _clean(task: dict) -> dict:
    """Drop jtask's derived ``*_gregorian`` helper keys — show only real data."""
    return {k: v for k, v in task.items() if not k.endswith("_gregorian")}


class RawDataView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RawDataView")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel("دادهٔ خام Taskwarrior (JSON)"), 1)
        self._copy = QPushButton("رونوشت")
        self._copy.clicked.connect(self._copy_json)
        top.addWidget(self._copy)
        lay.addLayout(top)

        self._text = QPlainTextEdit()
        self._text.setObjectName("RawJson")
        self._text.setReadOnly(True)
        self._text.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self._text, 1)

    def load_task(self, task: dict) -> None:
        self._text.setPlainText(
            json.dumps(_clean(task), ensure_ascii=False, indent=2, sort_keys=True)
        )

    def _copy_json(self) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(self._text.toPlainText())
