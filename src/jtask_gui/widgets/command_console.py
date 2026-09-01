"""Dockable raw ``task …`` console — the zero-feature-loss escape hatch (§6.9)."""

from __future__ import annotations

import re
import shlex

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QKeyEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from jtask import rewrite, taskwarrior

from .. import tokens as tok
from ..i18n import t
from ..theme import palette
from ..workers import submit


def _prompt_icon() -> QIcon:
    """A ``❯`` prompt glyph in the console-prompt colour (theme-independent —
    the console is always dark)."""
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(palette("dark")["console_prompt"]))
    f = QFont("DejaVu Sans Mono")
    f.setPointSize(11)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, "❯")
    p.end()
    return QIcon(pm)

# Taskwarrior underlines table headers with SGR escapes (\x1b[4m … \x1b[0m)
# even when rc.color=off / rc._forcecolor=off — a QPlainTextEdit is not a
# terminal, so strip every CSI/OSC sequence before displaying.
_ANSI_RE = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")

# noise Taskwarrior prints to stderr for jtask's own `_RC` prefix / the
# TASKDATA/TASKRC env — never anything the user typed, so drop it.
_NOISE_RE = re.compile(
    r"^(?:Configuration override rc\.\S+=.*|TASKRC override: .*|TASKDATA override: .*)$"
)


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def clean_output(text: str) -> str:
    lines = [ln for ln in strip_ansi(text).splitlines() if not _NOISE_RE.match(ln)]
    return "\n".join(lines).strip("\n")


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


# verbs / tokens that can change the Taskwarrior store or config — after one
# of these runs in the console the GUI must re-read everything.
_MUTATING = {
    "add", "log", "modify", "done", "delete", "purge", "start", "stop",
    "annotate", "denotate", "append", "prepend", "duplicate", "edit",
    "undo", "import", "synchronize", "sync", "config", "context",
}


def _is_mutating(args: list[str]) -> bool:
    if any(a.startswith("rc.") and "=" in a for a in args):
        return True
    return any(a in _MUTATING for a in args)


class CommandConsole(QWidget):
    #: emitted after any command that could have changed Taskwarrior state —
    #: MainWindow connects this to a full refresh so console edits show at once.
    stateChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandConsole")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(tok.SP_6, tok.SP_6, tok.SP_6, tok.SP_6)
        lay.setSpacing(tok.SP_6)

        self._out = QPlainTextEdit()
        self._out.setObjectName("ConsoleOutput")
        self._out.setReadOnly(True)
        self._out.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        lay.addWidget(self._out, 1)

        self._in = _HistoryLineEdit()
        self._in.setObjectName("ConsoleInput")
        self._in.setPlaceholderText(t("console.input_placeholder"))
        self._in.setClearButtonEnabled(True)
        self._in.addAction(
            _prompt_icon(), QLineEdit.ActionPosition.LeadingPosition
        )
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
        self._mutating = _is_mutating(args)

        def work() -> str:
            proc = taskwarrior.run(args, check=False)
            return (proc.stdout or "") + (proc.stderr or "")

        submit(work, self._done, self._done)

    def _done(self, output: object) -> None:
        text = output if isinstance(output, str) else str(output)
        self._append(clean_output(text) or t("console.no_output"))
        self._in.setEnabled(True)
        self._in.setFocus()
        if getattr(self, "_mutating", False):
            self.stateChanged.emit()
