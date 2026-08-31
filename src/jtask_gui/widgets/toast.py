"""A lightweight non-blocking confirmation toast (§ d6).

For *positive, non-destructive* feedback only — "filter saved", "undo done",
"task added". Destructive actions keep their blocking confirmation dialog; the
toast never asks a question and never blocks input.

One toast per parent window, reused; a new message resets its timer. It floats
just above the status bar, bottom-centre, fades in and auto-dismisses.
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

from .. import icons, tokens

_VISIBLE_MS = 2600
_FADE_MS = 160


class Toast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(tokens.SP_12, tokens.SP_8, tokens.SP_12, tokens.SP_8)
        lay.setSpacing(tokens.SP_8)
        self._icon = QLabel()
        self._icon.setObjectName("ToastIcon")
        self._text = QLabel()
        self._text.setObjectName("ToastText")
        lay.addWidget(self._icon)
        lay.addWidget(self._text)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._anim.setDuration(_FADE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._fade_out)
        # elevation is the surface + border (same choice as the dialogs); a
        # widget can hold only one QGraphicsEffect and the fade needs the
        # opacity one.
        self.hide()

    # --- API ------------------------------------------------------

    def show_message(self, text: str, *, kind: str = "success") -> None:
        self._icon.setPixmap(
            icons.icon("completed" if kind == "success" else "next", "primary")
            .pixmap(tokens.SP_16, tokens.SP_16)
        )
        self._text.setText(text)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._animate_to(1.0)
        self._hold.start(_VISIBLE_MS)

    # --- internals ----------------------------------------------

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._opacity.opacity())
        self._anim.setEndValue(target)
        self._anim.start()

    def _fade_out(self) -> None:
        self._animate_to(0.0)
        QTimer.singleShot(_FADE_MS, self.hide)

    def _reposition(self) -> None:
        p = self.parentWidget()
        if p is None:
            return
        margin = tokens.SP_24
        x = (p.width() - self.width()) // 2
        y = p.height() - self.height() - margin
        self.move(max(margin, x), max(margin, y))

    def parent_resized(self) -> None:
        if self.isVisible():
            self._reposition()
