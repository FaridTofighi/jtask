"""A Ctrl/Cmd-K command palette — fuzzy search over actions, views, filters.

Complements (never replaces) the Raw Command Console: the palette is a fast
launcher for things that already have a control; the console stays the escape
hatch for raw ``task`` commands.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as tok
from ..i18n import t


@dataclass(frozen=True)
class Command:
    label: str
    category: str
    run: Callable[[], None]
    hint: str = ""  # e.g. a shortcut string


def _score(query: str, text: str) -> int | None:
    """Subsequence fuzzy score — lower is better, ``None`` = no match."""
    q, s = query.lower(), text.lower()
    if not q:
        return 0
    if q in s:
        return s.index(q)  # contiguous match, ranked by position
    i = 0
    gaps = 0
    last = -1
    for ch in q:
        j = s.find(ch, i)
        if j < 0:
            return None
        if last >= 0:
            gaps += j - last - 1
        last = j
        i = j + 1
    return 1000 + gaps  # non-contiguous — always worse than any substring hit


class CommandPalette(QDialog):
    def __init__(self, commands: list[Command], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandPalette")
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setModal(True)
        self._commands = commands
        self._filtered: list[Command] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_6)

        self._input = QLineEdit()
        self._input.setObjectName("PaletteInput")
        self._input.setPlaceholderText(t("palette.placeholder"))
        self._input.textChanged.connect(self._refilter)
        self._input.returnPressed.connect(self._activate_current)
        lay.addWidget(self._input)

        self._list = QListWidget()
        self._list.setObjectName("PaletteList")
        self._list.setUniformItemSizes(True)
        self._list.itemActivated.connect(lambda _i: self._activate_current())
        self._list.itemClicked.connect(lambda _i: self._activate_current())
        lay.addWidget(self._list)

        self._input.installEventFilter(self)
        self.resize(560, 420)
        self._refilter("")

    # --- filtering / navigation ------------------------------------

    def _refilter(self, text: str) -> None:
        scored: list[tuple[int, int, Command]] = []
        for idx, cmd in enumerate(self._commands):
            s = _score(text, cmd.label)
            if s is None and text:
                s = _score(text, f"{cmd.category} {cmd.label}")
            if s is not None:
                scored.append((s, idx, cmd))
        scored.sort(key=lambda x: (x[0], x[1]))
        self._filtered = [c for _s, _i, c in scored]

        self._list.clear()
        for cmd in self._filtered:
            it = QListWidgetItem(f"{cmd.label}")
            it.setData(Qt.ItemDataRole.UserRole, cmd)
            badge = cmd.hint or cmd.category
            if badge:
                it.setToolTip(badge)
            self._list.addItem(it)
        if self._filtered:
            self._list.setCurrentRow(0)

    def _move(self, delta: int) -> None:
        n = self._list.count()
        if not n:
            return
        self._list.setCurrentRow((self._list.currentRow() + delta) % n)

    def _activate_current(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._filtered):
            cmd = self._filtered[row]
            self.accept()
            cmd.run()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move(-1)
                return True
        return super().eventFilter(obj, event)
