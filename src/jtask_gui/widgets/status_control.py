"""The Status form-row's control — one cohesive segmented row.

Left/leading: the task's *effective* state (`reports.effective_status`),
rendered in the app's active-selection accent (`#StatusCurrent`, the same
`primary_soft` / `primary` language as the selected sidebar item) so it
reads as "this is where the task *is*", never as another button.

Right/trailing: only the transitions valid *from* that state, as compact
icon `QToolButton`s (`#StatusAction`) with the full label on hover. Momentary
actions — fire once, the task changes, the control rebuilds — so not a
`SegmentedControl` (which keeps one segment `checked` to hold a value) and
not a hidden menu (discoverability is the point; reopen had no in-panel
action before). Delete tints red on hover (design-system §3).

Everything is one horizontal row inside a bordered `#StatusControl` frame:
the icon buttons keep it narrow enough to never wrap or widen the panel
(the recurring "detail panel clips its later sections" bug). Element order
and corner rounding mirror automatically with the layout direction — the
row is a plain `QHBoxLayout`, the accent is a full fill (no leading-edge
border to place by hand). See docs/jtask-gui-design.md.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget

from jtask import reports

from .. import icons
from .. import tokens as tok
from ..i18n import t

_STATE_LABEL = {
    "pending": "detail.status.pending",
    "active": "detail.status.active",
    "waiting": "detail.status.waiting",
    "completed": "detail.status.completed",
    "deleted": "detail.status.deleted",
    "recurring": "detail.status.recurring",
}

_ACTION_ICON = {
    "start": "start", "stop": "stop", "done": "done",
    "delete": "delete", "reopen": "reopen", "unwait": "unwait",
}


def _actions_for(state: str, started: bool) -> list[tuple[str, str]]:
    """`[(i18n label key, action id)]` valid from *state*, in display order.

    action id ∈ {start, stop, done, delete, reopen, unwait}.
    """
    if state in ("completed", "deleted"):
        return [("detail.status.act.reopen", "reopen")]
    if state == "recurring":
        return []
    base = [
        (("detail.status.act.stop", "stop") if started
         else ("detail.status.act.start", "start")),
        ("detail.status.act.done", "done"),
        ("detail.status.act.delete", "delete"),
    ]
    if state == "waiting":
        return [("detail.status.act.unwait", "unwait"), *base]
    return base


class StatusControl(QFrame):
    actionRequested = pyqtSignal(str)  # start|stop|done|delete|reopen|unwait

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusControl")
        # hug the content — a fixed-size row that never dictates panel width
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(tok.SP_2, tok.SP_2, tok.SP_2, tok.SP_2)
        self._row.setSpacing(tok.SP_2)

        self._current = QLabel("—")
        self._current.setObjectName("StatusCurrent")
        self._row.addWidget(self._current)

        self.state = ""

    # --- API ---------------------------------------------------------

    def set_task(self, task: dict) -> None:
        self.state = reports.effective_status(task)
        self._current.setText(t(_STATE_LABEL.get(self.state, "detail.status.pending")))

        while self._row.count() > 1:  # keep the current-state label at index 0
            w = self._row.takeAt(self._row.count() - 1).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        for label_key, action in _actions_for(self.state, bool(task.get("start"))):
            btn = QToolButton()
            btn.setObjectName("StatusAction")
            btn.setProperty("_action", action)
            btn.setProperty("act", action)  # QSS hook (delete → red hover)
            btn.setIcon(icons.icon(
                _ACTION_ICON[action], "overdue" if action == "delete" else "text_muted"
            ))
            btn.setIconSize(QSize(tok.FS_LG, tok.FS_LG))
            btn.setToolTip(t(label_key))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, a=action: self.actionRequested.emit(a)
            )
            self._row.addWidget(btn)

        self.updateGeometry()

    def badge_text(self) -> str:
        return self._current.text()

    def action_ids(self) -> list[str]:
        return [
            self._row.itemAt(i).widget().property("_action")
            for i in range(1, self._row.count())
        ]
