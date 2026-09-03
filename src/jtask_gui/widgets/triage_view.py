"""Triage Mode — process one card at a time.

A triage decision is just a board column's drop action applied to the current
card (``boards.compile_drop``) — the same bounded vocabulary as a drag between
columns — plus three built-ins: Skip, Edit… (hand off to the full detail panel)
and Trash. An inline Project field covers the common "organise into a project"
case. Every write goes through ``MainWindow._write`` (undoable); this view only
holds the queue and renders the current card.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jtask.rtl import bidi_isolate

from .. import fmt
from .. import tokens as tok
from ..bidi import apply_content_direction
from ..boards import Board, compile_drop
from ..calendar_system import active
from ..i18n import t
from .autocomplete import make_token_completer


class TriageView(QWidget):
    decision = pyqtSignal(str, str, list)    # uuid, verb, mods  → _write then advance
    projectAssigned = pyqtSignal(str, str)   # uuid, project
    editRequested = pyqtSignal(str)          # uuid
    deleteRequested = pyqtSignal(str)        # uuid
    exited = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TriageView")
        self._board: Board | None = None
        self._queue: list[dict] = []
        self._i = 0
        self._col_buttons: list[QPushButton] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_PANEL)
        root.setSpacing(tok.SP_12)

        head = QHBoxLayout()
        self._heading = QLabel(t("triage.title"))
        self._heading.setObjectName("H2")
        head.addWidget(self._heading)
        head.addStretch(1)
        self._counter = QLabel("")
        self._counter.setObjectName("Muted")
        head.addWidget(self._counter)
        exit_btn = QPushButton(t("triage.exit"))
        exit_btn.clicked.connect(self.exited.emit)
        head.addWidget(exit_btn)
        root.addLayout(head)

        self._card = QWidget()
        self._card.setObjectName("TriageCard")
        card = QVBoxLayout(self._card)
        card.setContentsMargins(*tok.INSET_PANEL)
        card.setSpacing(tok.SP_8)
        self._desc = QLabel("")
        self._desc.setObjectName("H1")
        self._desc.setWordWrap(True)
        card.addWidget(self._desc)
        self._meta = QLabel("")
        self._meta.setObjectName("Muted")
        self._meta.setWordWrap(True)
        card.addWidget(self._meta)

        prow = QHBoxLayout()
        prow.addWidget(QLabel(t("word.project")))
        self._project = QLineEdit()
        self._project.setPlaceholderText(t("triage.project.placeholder"))
        self._project.returnPressed.connect(self._assign_project)
        prow.addWidget(self._project, 1)
        card.addLayout(prow)
        root.addWidget(self._card)

        self._cols_row = QHBoxLayout()
        root.addLayout(self._cols_row)

        actions = QHBoxLayout()
        self._skip = QPushButton(t("triage.skip"))
        self._skip.clicked.connect(self.advance)
        self._edit = QPushButton(t("triage.edit"))
        self._edit.clicked.connect(lambda: self._emit_for_current(self.editRequested))
        self._trash = QPushButton(t("triage.trash"))
        self._trash.setObjectName("DangerButton")
        self._trash.clicked.connect(lambda: self._emit_for_current(self.deleteRequested))
        actions.addWidget(self._skip)
        actions.addWidget(self._edit)
        actions.addStretch(1)
        actions.addWidget(self._trash)
        root.addLayout(actions)

        self._done = QLabel(t("triage.done"))
        self._done.setObjectName("EmptyState")
        self._done.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done.hide()
        root.addWidget(self._done, 1)
        root.addStretch(1)

    # --- API -----------------------------------------------------

    def set_projects(self, projects: list[str]) -> None:
        self._project.setCompleter(make_token_completer(projects, []))

    def start(self, board: Board, cards: list[dict]) -> None:
        self._board = board
        self._queue = list(cards)
        self._i = 0
        self._build_column_buttons()
        self._render()

    def remaining(self) -> int:
        return max(0, len(self._queue) - self._i)

    def advance(self) -> None:
        self._i += 1
        self._render()

    # --- internals ---------------------------------------------

    def _build_column_buttons(self) -> None:
        while self._cols_row.count():
            item = self._cols_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._col_buttons = []
        for col in (self._board.columns if self._board else []):
            compiled = compile_drop(col.drop)
            if compiled is None:
                continue                       # e.g. the Inbox column itself
            btn = QPushButton(col.title)
            btn.setObjectName("TriageColButton")
            btn.clicked.connect(lambda _=False, c=compiled: self._decide(c))
            self._cols_row.addWidget(btn)
            self._col_buttons.append(btn)
        self._cols_row.addStretch(1)

    def _current(self) -> dict | None:
        return self._queue[self._i] if 0 <= self._i < len(self._queue) else None

    def _uuid(self) -> str:
        cur = self._current()
        return cur.get("uuid", "") if cur else ""

    def _emit_for_current(self, signal) -> None:
        if self._uuid():
            signal.emit(self._uuid())

    def _decide(self, compiled: tuple[str, list[str]]) -> None:
        verb, mods = compiled
        if self._uuid():
            self.decision.emit(self._uuid(), verb, list(mods))

    def _assign_project(self) -> None:
        proj = self._project.text().strip()
        if self._uuid() and proj:
            self.projectAssigned.emit(self._uuid(), proj)

    def _render(self) -> None:
        done = self._current() is None
        self._card.setVisible(not done)
        for btn in (self._skip, self._edit, self._trash, *self._col_buttons):
            btn.setVisible(not done)
        self._done.setVisible(done)
        if done:
            self._counter.setText("")
            return
        task = self._current()
        desc = task.get("description", "")
        self._desc.setText(desc)
        apply_content_direction(self._desc, desc)
        self._meta.setText(self._meta_text(task))
        self._project.setText(task.get("project", "") or "")
        self._counter.setText(t(
            "triage.counter", n=fmt.num(self._i + 1), total=fmt.num(len(self._queue))
        ))

    def _meta_text(self, task: dict) -> str:
        bits: list[str] = []
        if task.get("project"):
            bits.append(bidi_isolate(task["project"]))
        tags = [x for x in (task.get("tags") or []) if not x.isupper() and x != "starred"]
        if tags:
            bits.append(bidi_isolate("  ".join(f"#{x}" for x in tags)))
        entry = task.get("entry_gregorian") or task.get("entry")
        if entry:
            bits.append(bidi_isolate(active().format_utc(entry, "short")))
        return "   ·   ".join(bits)
