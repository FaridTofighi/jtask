"""Dockable raw ``task …`` console — the zero-feature-loss escape hatch (§6.9)."""

from __future__ import annotations

import re
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

from .. import tokens as tok
from ..i18n import t
from ..workers import submit

# Taskwarrior underlines table headers with SGR escapes (\x1b[4m … \x1b[0m)
# even when rc.color=off / rc._forcecolor=off — a QPlainTextEdit is not a
# terminal, so strip every CSI/OSC sequence before displaying.
_ANSI_RE = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


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
        lay.setContentsMargins(tok.SP_6, tok.SP_6, tok.SP_6, tok.SP_6)
        lay.setSpacing(tok.SP_4)

        self._out = QPlainTextEdit()
        self._out.setObjectName("ConsoleOutput")
        self._out.setReadOnly(True)
        lay.addWidget(self._out, 1)

        self._in = _HistoryLineEdit()
        self._in.setPlaceholderText(t("console.input_placeholder"))
        self._in.returnPressed.connect(self._run)
        lay.addWidget(self._in)

        self._append(t("console.intro"))

    def prefill(self, text: str) -> None:
        """Put *text* in the input line and focus it — do not run it."""
        self._in.setText(text)
        self._in.setFocus()
        self._in.end(False)

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

    def _done(self, output: object) -> None:
        text = output if isinstance(output, str) else str(output)
        self._append(strip_ansi(text) or t("console.no_output"))
        self._in.setEnabled(True)
        self._in.setFocus()
