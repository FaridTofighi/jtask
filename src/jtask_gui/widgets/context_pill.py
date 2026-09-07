"""Toolbar context indicator — a pill that shows the active Taskwarrior
context (or "no context") and, on click, a menu to switch or clear it.

An active context silently scopes *every* view in the app, so this must read
as a persistent global mode, not a navigation icon: when a context is active
the pill takes the app's accent (`primary_soft` fill + `primary` bold text +
a filled dot), the same visual language as the selected sidebar item / the
status control's current-state chip. It lives at the reading-start edge of
row one (the input strip), a full toolbar row away from row two's icon
clusters.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QWidget

from jtask.rtl import bidi_isolate

from .. import tokens as tok
from ..i18n import t


class ContextPill(QFrame):
    contextChangeRequested = pyqtSignal(str)  # context name; "" clears it

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContextPill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(t("context.pill.tip"))

        row = QHBoxLayout(self)
        row.setContentsMargins(tok.SP_8, tok.SP_2, tok.SP_8, tok.SP_2)
        row.setSpacing(tok.SP_6)
        self._dot = QLabel("●")  # ●
        self._dot.setObjectName("ContextDot")
        self._name = QLabel("—")
        self._name.setObjectName("ContextName")
        row.addWidget(self._dot)
        row.addWidget(self._name)

        self._names: list[str] = []
        self._active: str | None = None
        self.set_state(None, [])

    # --- API --------------------------------------------------------

    def set_state(self, active: str | None, names: list[str]) -> None:
        self._active = active or None
        self._names = list(names)
        if self._active:
            self._name.setText(bidi_isolate(self._active))
        else:
            self._name.setText(t("context.none"))
        self.setProperty("active", bool(self._active))
        self.style().unpolish(self)
        self.style().polish(self)

    def is_active(self) -> bool:
        return bool(self._active)

    def name_text(self) -> str:
        return self._name.text()

    # --- interaction ----------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        menu = QMenu(self)
        none_act = menu.addAction(t("context.menu.none"))
        none_act.setCheckable(True)
        none_act.setChecked(self._active is None)
        none_act.triggered.connect(lambda: self.contextChangeRequested.emit(""))
        if self._names:
            menu.addSeparator()
        for name in self._names:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == self._active)
            act.triggered.connect(lambda _c=False, n=name: self.contextChangeRequested.emit(n))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
