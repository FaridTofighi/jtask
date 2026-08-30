"""Chip-style tag editor with autocomplete over the shared tag list."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)

from .. import tokens as tok
from ..i18n import t


class _Chip(QFrame):
    removed = pyqtSignal(str)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Chip")
        self.text = text
        row = QHBoxLayout(self)
        row.setContentsMargins(tok.SP_6, 1, tok.SP_2, 1)
        row.setSpacing(tok.SP_2)
        row.addWidget(QLabel(f"#{text}"))
        btn = QToolButton()
        btn.setText("✕")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.removed.emit(self.text))
        row.addWidget(btn)


class TagChipEditor(QWidget):
    """Emits ``tagsChanged(list[str])`` on every add/remove."""

    tagsChanged = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tags: list[str] = []
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(tok.SP_4)

        self._input = QLineEdit()
        self._input.setPlaceholderText(t("chips.placeholder"))
        self._input.returnPressed.connect(self._commit_input)
        self._row.addWidget(self._input, 1)

    # --- API -----------------------------------------------------

    def set_completions(self, tags: list[str]) -> None:
        completer = QCompleter(sorted(tags))
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._input.setCompleter(completer)

    def set_tags(self, tags: list[str]) -> None:
        for chip in self.findChildren(_Chip):
            chip.setParent(None)
            chip.deleteLater()
        self._tags = []
        for tag in tags:
            self._add(tag, silent=True)
        self.tagsChanged.emit(list(self._tags))

    def tags(self) -> list[str]:
        return list(self._tags)

    # --- internals ---------------------------------------------

    def _commit_input(self) -> None:
        text = self._input.text().strip().lstrip("#")
        self._input.clear()
        if text:
            self._add(text)

    def _add(self, tag: str, silent: bool = False) -> None:
        if tag in self._tags:
            return
        self._tags.append(tag)
        chip = _Chip(tag)
        chip.removed.connect(self._remove)
        self._row.insertWidget(self._row.count() - 1, chip)
        if not silent:
            self.tagsChanged.emit(list(self._tags))

    def _remove(self, tag: str) -> None:
        if tag not in self._tags:
            return
        self._tags.remove(tag)
        for chip in self.findChildren(_Chip):
            if chip.text == tag:
                chip.setParent(None)
                chip.deleteLater()
        self.tagsChanged.emit(list(self._tags))
