"""Status-bar operation indicator (§22 — visible async execution state).

A single label that always reflects the last heavy operation's state:
``idle`` (blank) · ``running`` · ``success`` · ``failed`` · ``cancelled``.
Success and cancelled auto-fade back to idle; failed stays until the next
operation so the user is not left wondering.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QWidget

_GLYPH = {
    "running": "⟳",
    "success": "✓",
    "failed": "✗",
    "cancelled": "⊘",
}
_ROLE = {
    "running": "Muted",
    "success": "StatusOk",
    "failed": "StatusBad",
    "cancelled": "Muted",
}


class OperationStatus(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Muted")
        self.state = "idle"
        self._fade = QTimer(self)
        self._fade.setSingleShot(True)
        self._fade.timeout.connect(self.idle)

    def _set(self, state: str, message: str, fade_ms: int = 0) -> None:
        self._fade.stop()
        self.state = state
        if state == "idle" or not message:
            self.setText("")
        else:
            self.setText(f"{_GLYPH.get(state, '')} {message}".strip())
        self.setObjectName(_ROLE.get(state, "Muted"))
        self.style().unpolish(self)
        self.style().polish(self)
        if fade_ms:
            self._fade.start(fade_ms)

    def idle(self) -> None:
        self._set("idle", "")

    def running(self, message: str) -> None:
        self._set("running", message)

    def success(self, message: str) -> None:
        self._set("success", message, fade_ms=2500)

    def failed(self, message: str) -> None:
        self._set("failed", message)

    def cancelled(self, message: str = "لغو شد") -> None:
        self._set("cancelled", message, fade_ms=2500)
