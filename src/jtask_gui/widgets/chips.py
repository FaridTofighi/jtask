"""Chip-style tag editor with autocomplete over the shared tag list.

The chips wrap (FlowLayout) so a task with many tags grows *taller*, never
wider — a single-row layout used to force the whole edit panel wider than its
pane and clip the Close button.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from .. import tokens as tok
from ..i18n import t
from .flow_layout import FlowLayout


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
        self._chips: list[_Chip] = []
        self._flow = FlowLayout(self, hspacing=tok.SP_4, vspacing=tok.SP_4)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._input = QLineEdit()
        self._input.setPlaceholderText(t("chips.placeholder"))
        self._input.setMinimumWidth(90)
        self._input.returnPressed.connect(self._commit_input)
        self._flow.addWidget(self._input)

    # --- height-for-width so a QFormLayout row grows when chips wrap ----

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)

    # --- API -----------------------------------------------------

    def set_completions(self, tags: list[str]) -> None:
        completer = QCompleter(sorted(tags))
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._input.setCompleter(completer)

    def set_tags(self, tags: list[str]) -> None:
        for chip in self._chips:
            chip.setParent(None)
            chip.deleteLater()
        self._chips = []
        self._tags = []
        for tag in tags:
            self._add(tag, silent=True)
        self._relayout()
        self.tagsChanged.emit(list(self._tags))

    def tags(self) -> list[str]:
        return list(self._tags)

    # --- internals ---------------------------------------------

    def _commit_input(self) -> None:
        text = self._input.text().strip().lstrip("#")
        self._input.clear()
        if text:
            self._add(text)
            self._relayout()

    def _add(self, tag: str, silent: bool = False) -> None:
        if tag in self._tags:
            return
        self._tags.append(tag)
        chip = _Chip(tag)
        chip.removed.connect(self._remove)
        self._chips.append(chip)
        if not silent:
            self.tagsChanged.emit(list(self._tags))

    def _remove(self, tag: str) -> None:
        if tag not in self._tags:
            return
        self._tags.remove(tag)
        for chip in list(self._chips):
            if chip.text == tag:
                self._chips.remove(chip)
                chip.setParent(None)
                chip.deleteLater()
        self._relayout()
        self.tagsChanged.emit(list(self._tags))

    def _relayout(self) -> None:
        """Re-add every chip then the input, so the input always trails.

        ``takeAt`` detaches layout items without deleting the widgets (they stay
        parented to ``self``), so re-adding just re-orders them.
        """
        while self._flow.count():
            self._flow.takeAt(0)
        for chip in self._chips:
            self._flow.addWidget(chip)
        self._flow.addWidget(self._input)
        self.updateGeometry()
