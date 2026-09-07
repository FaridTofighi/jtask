"""The Status form-row's inline action control.

Shows the task's *effective* state (`reports.effective_status`) and only the
transitions valid from it. These are momentary *actions* (fire once, the task
changes, the control rebuilds), not a persisted selection — so it is a plain
row of small buttons, not a `SegmentedControl` (which keeps one button
`checked` to represent a value) and not a hidden menu (the whole point is
discoverability — reopen especially had no direct in-panel action before).
The delete button carries `#DangerButton` (design-system §3); the badge
reuses the existing `#Badge` pill style. See docs/jtask-gui-design.md.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from jtask import reports

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


def _actions_for(state: str, started: bool) -> list[tuple[str, str]]:
    """`[(i18n label key, action id)]` valid from *state*, in display order.

    action id ∈ {start, stop, done, delete, reopen, unwait}.
    """
    if state in ("completed", "deleted"):
        return [("detail.status.act.reopen", "reopen")]
    if state == "recurring":
        return []
    # pending / active / waiting all share the pending action set
    base = [
        (("detail.status.act.stop", "stop") if started
         else ("detail.status.act.start", "start")),
        ("detail.status.act.done", "done"),
        ("detail.status.act.delete", "delete"),
    ]
    if state == "waiting":
        return [("detail.status.act.unwait", "unwait"), *base]
    return base


class StatusControl(QWidget):
    actionRequested = pyqtSignal(str)  # start|stop|done|delete|reopen|unwait

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusControl")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(tok.SP_8)

        self._badge = QLabel("—")
        self._badge.setObjectName("Badge")
        row.addWidget(self._badge)

        self._actions = QHBoxLayout()
        self._actions.setSpacing(tok.SP_6)
        row.addLayout(self._actions)
        row.addStretch(1)

        self.state = ""

    # --- API ---------------------------------------------------------

    def set_task(self, task: dict) -> None:
        self.state = reports.effective_status(task)
        self._badge.setText(t(_STATE_LABEL.get(self.state, "detail.status.pending")))

        while self._actions.count():
            item = self._actions.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for label_key, action in _actions_for(self.state, bool(task.get("start"))):
            btn = QPushButton(t(label_key))
            btn.setProperty("_action", action)
            if action == "delete":
                btn.setObjectName("DangerButton")
            btn.clicked.connect(lambda _checked=False, a=action: self.actionRequested.emit(a))
            self._actions.addWidget(btn)

    def badge_text(self) -> str:
        return self._badge.text()

    def action_ids(self) -> list[str]:
        return [
            self._actions.itemAt(i).widget().property("_action")
            for i in range(self._actions.count())
        ]
