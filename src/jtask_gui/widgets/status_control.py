"""The Status form-row's inline action control.

Shows the task's *effective* state (`reports.effective_status`) and only the
transitions valid from it. These are momentary *actions* (fire once, the task
changes, the control rebuilds), not a persisted selection — so it is a row
of small buttons, not a `SegmentedControl` (which keeps one button `checked`
to represent a value) and not a hidden menu (the whole point is
discoverability — reopen especially had no direct in-panel action before).
The delete button carries `#DangerButton` (design-system §3); the badge
reuses the existing `#Badge` pill style.

The badge + buttons live in a **FlowLayout** — they wrap to a second line
when the panel is narrow instead of forcing the whole detail panel wider
(the recurring "detail panel clips its later sections" bug: the tag chips
hit exactly this in M1 and were fixed the same way). See
docs/jtask-gui-design.md.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from jtask import reports

from .. import tokens as tok
from ..i18n import t
from .flow_layout import FlowLayout

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
        # a wrapping layout — never forces its container wider than the panel
        self._flow = FlowLayout(self, hspacing=tok.SP_6, vspacing=tok.SP_6)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._badge = QLabel("—")
        self._badge.setObjectName("Badge")
        self._flow.addWidget(self._badge)

        self.state = ""

    # QFormLayout asks the row how tall it needs to be at the given width —
    # delegate so a wrapped second line of buttons is accounted for.
    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)

    # --- API ---------------------------------------------------------

    def set_task(self, task: dict) -> None:
        self.state = reports.effective_status(task)
        self._badge.setText(t(_STATE_LABEL.get(self.state, "detail.status.pending")))

        # drop the old action buttons (keep the badge at index 0)
        while self._flow.count() > 1:
            item = self._flow.takeAt(self._flow.count() - 1)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        for label_key, action in _actions_for(self.state, bool(task.get("start"))):
            btn = QPushButton(t(label_key))
            btn.setProperty("_action", action)
            if action == "delete":
                btn.setObjectName("DangerButton")
            btn.clicked.connect(lambda _checked=False, a=action: self.actionRequested.emit(a))
            self._flow.addWidget(btn)

        self.updateGeometry()

    def badge_text(self) -> str:
        return self._badge.text()

    def action_ids(self) -> list[str]:
        return [
            self._flow.itemAt(i).widget().property("_action")
            for i in range(1, self._flow.count())
        ]
