"""Raw Taskwarrior filter input with shared autocomplete.

M1: raw syntax only (with autocomplete). The visual filter builder is M3.
"""

from __future__ import annotations

import shlex

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget

from jtask import rewrite, taskwarrior

from .autocomplete import make_token_completer


class FilterBar(QWidget):
    """Emits ``filterChanged(list[str])`` — Gregorian-rewritten filter tokens."""

    filterChanged = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("فیلتر: «project:وب +مهم due.before:فردا»")
        self._edit.returnPressed.connect(self._apply)
        row.addWidget(self._edit, 1)

        clear = QToolButton()
        clear.setText("✕")
        clear.clicked.connect(self.clear)
        row.addWidget(clear)

        self.refresh_completions()

    def refresh_completions(self) -> None:
        try:
            projects = taskwarrior.list_projects()
            tags = taskwarrior.list_tags()
            udas = list(taskwarrior.uda_definitions())
        except Exception:  # noqa: BLE001
            projects, tags, udas = [], [], []
        self._edit.setCompleter(make_token_completer(projects, tags, udas))

    def raw_text(self) -> str:
        return self._edit.text().strip()

    def set_text(self, text: str) -> None:
        self._edit.setText(text)

    def clear(self) -> None:
        self._edit.clear()
        self.filterChanged.emit([])

    def current_filter(self) -> list[str]:
        text = self._edit.text().strip()
        if not text:
            return []
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()
        return rewrite.rewrite_args(tokens)

    def _apply(self) -> None:
        self.filterChanged.emit(self.current_filter())
