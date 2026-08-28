"""Dockable raw ``task …`` console — the zero-feature-loss escape hatch (§6.9)."""

from __future__ import annotations

import shlex

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from jtask import rewrite, taskwarrior

from ..workers import submit


class _HistoryLineEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history: list[str] = []
        self._pos = 0

    def push(self, text: str) -> None:
        self._history.append(text)
        self._pos = len(self._history)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Up and self._history:
            self._pos = max(0, self._pos - 1)
            self.setText(self._history[self._pos])
        elif event.key() == Qt.Key.Key_Down and self._history:
            self._pos = min(len(self._history), self._pos + 1)
            self.setText(self._history[self._pos] if self._pos < len(self._history) else "")
        else:
            super().keyPressEvent(event)


class CommandConsole(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        self._out = QPlainTextEdit()
        self._out.setObjectName("ConsoleOutput")
        self._out.setReadOnly(True)
        lay.addWidget(self._out, 1)

        self._in = _HistoryLineEdit()
        self._in.setPlaceholderText("task …  (تاریخ‌های جلالی بازنویسی می‌شوند)")
        self._in.returnPressed.connect(self._run)
        lay.addWidget(self._in)

        self._append("» کنسول فرمان — دستور را بدون واژهٔ «task» وارد کنید.\n")

    def _append(self, text: str) -> None:
        self._out.appendPlainText(text.rstrip("\n"))

    def _run(self) -> None:
        raw = self._in.text().strip()
        if not raw:
            return
        self._in.push(raw)
        self._in.clear()
        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()
        args = rewrite.rewrite_args(tokens)
        self._append(f"\n$ task {' '.join(args)}")
        self._in.setEnabled(False)

        def work() -> str:
            proc = taskwarrior.run(args, check=False)
            return (proc.stdout or "") + (proc.stderr or "")

        submit(work, self._done, self._done)

    def _done(self, output: str) -> None:
        self._append(output or "(بدون خروجی)")
        self._in.setEnabled(True)
        self._in.setFocus()
