"""The Weekly Review Wizard — a non-modal guided pass through the shared
``jtask.gtd.REVIEW_STEPS``.

It lives in a dock (like the console) and never blocks the app: for each step it
just asks ``MainWindow`` to load that step's live Taskwarrior filter into the
real task table, which the user keeps acting on normally. The ``stuck_projects``
step (no single filter) shows its list in the dock itself. Progress is
persisted so a review can be resumed after the user closes the dock to go act
on something.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jtask import gtd

from .. import fmt
from .. import tokens as tok
from ..i18n import t
from .segmented import SegmentedControl

# the wizard = the shared data steps + a GUI-only closing "reports" glance
STEP_KEYS: list[str] = [s.key for s in gtd.REVIEW_STEPS] + ["reports"]


class ReviewWizard(QWidget):
    #: emitted on entering a step — MainWindow drives the matching view
    stepEntered = pyqtSignal(int)
    #: "add a next action" for a stuck project (index into the dock list)
    addNextActionRequested = pyqtSignal(str)
    exited = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewWizard")
        self._i = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_PANEL)
        root.setSpacing(tok.SP_6)

        top = QHBoxLayout()
        self._seg = SegmentedControl(
            [(fmt.num(n + 1), n) for n in range(len(STEP_KEYS))]
        )
        self._seg.changed.connect(lambda n: self.jump(int(n)))
        top.addWidget(self._seg, 1)
        self._exit_btn = QPushButton(t("review.exit"))
        self._exit_btn.clicked.connect(self.exited.emit)
        top.addWidget(self._exit_btn)
        root.addLayout(top)

        self._heading = QLabel("")
        self._heading.setObjectName("H2")
        root.addWidget(self._heading)
        self._hint = QLabel("")
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        self._stuck = QListWidget()
        self._stuck.setObjectName("ReviewStuckList")
        self._stuck.itemActivated.connect(self._stuck_activated)
        self._stuck.hide()
        root.addWidget(self._stuck)

        nav = QHBoxLayout()
        self._back = QPushButton(t("review.back"))
        self._back.clicked.connect(lambda: self.go(-1))
        self._next = QPushButton(t("review.next"))
        self._next.clicked.connect(lambda: self.go(1))
        nav.addWidget(self._back)
        nav.addStretch(1)
        nav.addWidget(self._next)
        root.addLayout(nav)

    # --- navigation ----------------------------------------------

    def start(self, at: int = 0) -> None:
        self.jump(max(0, min(at, len(STEP_KEYS) - 1)))

    def current(self) -> int:
        return self._i

    def key(self, index: int | None = None) -> str:
        return STEP_KEYS[self._i if index is None else index]

    def go(self, delta: int) -> None:
        self.jump(self._i + delta)

    def jump(self, index: int) -> None:
        if index >= len(STEP_KEYS):      # "Finish" past the last step
            self.exited.emit()
            return
        if not 0 <= index < len(STEP_KEYS):
            return
        self._i = index
        self._seg.set_value(index)
        key = STEP_KEYS[index]
        self._heading.setText(
            t("review.step_of", n=fmt.num(index + 1),
              total=fmt.num(len(STEP_KEYS)), title=t(f"review.step.{key}"))
        )
        self._hint.setText(t(f"review.hint.{key}"))
        self._back.setEnabled(index > 0)
        self._next.setText(
            t("review.finish") if index == len(STEP_KEYS) - 1 else t("review.next")
        )
        self._stuck.setVisible(key == "stuck_projects")
        self.stepEntered.emit(index)

    # --- the stuck-projects step --------------------------------

    def show_stuck(self, projects: list[str]) -> None:
        self._stuck.clear()
        if not projects:
            done = QListWidgetItem(t("review.stuck.none"))
            done.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._stuck.addItem(done)
            return
        for proj in projects:
            item = QListWidgetItem(t("review.stuck.row", project=proj))
            item.setData(Qt.ItemDataRole.UserRole, proj)
            self._stuck.addItem(item)

    def _stuck_activated(self, item: QListWidgetItem) -> None:
        proj = item.data(Qt.ItemDataRole.UserRole)
        if proj:
            self.addNextActionRequested.emit(proj)
