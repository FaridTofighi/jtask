"""Status-bar operation indicator (§22 — visible async execution state).

A single label that always reflects the last heavy operation's state:
``idle`` (blank) · ``running`` · ``success`` · ``failed`` · ``cancelled``.
Success and cancelled auto-fade back to idle; failed stays until the next
operation so the user is not left wondering.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
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
        self._action: Callable[[], None] | None = None
        self._fade = QTimer(self)
        self._fade.setSingleShot(True)
        self._fade.timeout.connect(self.idle)

    def _set(self, state: str, message: str, fade_ms: int = 0) -> None:
        self._fade.stop()
        self.state = state
        if state != "failed":
            self._action = None
        if state == "idle" or not message:
            self.setText("")
        else:
            self.setText(f"{_GLYPH.get(state, '')} {message}".strip())
        self.setObjectName(_ROLE.get(state, "Muted"))
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._action else Qt.CursorShape.ArrowCursor
        )
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

    def failed(self, message: str, *, action: Callable[[], None] | None = None) -> None:
        """*action*, when given, makes the message clickable (e.g. a background
        failure that should open its detail view rather than a blocking dialog)."""
        self._action = action
        self._set("failed", message)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._action is not None:
            self._action()
        else:
            super().mousePressEvent(event)

    def cancelled(self, message: str | None = None) -> None:
        if message is None:
            from ..i18n import t

            message = t("op.cancelled")
        self._set("cancelled", message, fade_ms=2500)
