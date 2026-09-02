"""A single task card on a board."""

from __future__ import annotations

from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from jtask.rtl import auto_isolate, bidi_isolate

from .. import icons
from .. import tokens as tok
from ..bidi import apply_content_direction
from ..calendar_system import active
from ..i18n import t

UUID_MIME = "application/x-jtask-uuids"

_PRIORITY_LABEL = {"H": "col.priority.h", "M": "col.priority.m", "L": "col.priority.l"}


class BoardCard(QFrame):
    activated = pyqtSignal(str)          # uuid
    starToggled = pyqtSignal(str, bool)  # uuid, on

    def __init__(self, task: dict, theme_name: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self.task = task
        self.uuid = task.get("uuid", "")
        self.setObjectName("BoardCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._press_pos = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_4)

        top = QHBoxLayout()
        top.setSpacing(tok.SP_4)
        self._star = QToolButton()
        self._star.setObjectName("CardStar")
        self._star.setCheckable(True)
        self._star.setChecked("starred" in (task.get("tags") or []))
        self._star.clicked.connect(self._on_star)
        description = task.get("description", "")
        desc = QLabel(auto_isolate(description))
        desc.setObjectName("CardTitle")
        desc.setWordWrap(True)
        apply_content_direction(desc, description)
        top.addWidget(self._star, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(desc, 1)
        lay.addLayout(top)

        meta = self._meta_line(task)
        if meta:
            m = QLabel(meta)
            m.setObjectName("CardMeta")
            m.setWordWrap(True)
            lay.addWidget(m)

        self.setProperty("priority", task.get("priority") or "")
        self._refresh_star_icon()

    # --- rendering --------------------------------------------

    def _meta_line(self, task: dict) -> str:
        bits: list[str] = []
        if task.get("project"):
            bits.append(auto_isolate(task["project"]))
        pri = task.get("priority", "")
        if pri in _PRIORITY_LABEL:
            bits.append(t(_PRIORITY_LABEL[pri]))
        due_g = task.get("due_gregorian") or ""
        if due_g:
            bits.append(bidi_isolate(active().format_utc(due_g, "short")))
        tags = [x for x in (task.get("tags") or [])
                if not x.isupper() and x != "starred"]
        if tags:
            bits.append(bidi_isolate("  ".join(f"#{x}" for x in tags)))
        return "   ·   ".join(bits)

    def set_theme(self, _name: str) -> None:
        self._refresh_star_icon()

    def _refresh_star_icon(self) -> None:
        on = self._star.isChecked()
        self._star.setIcon(icons.icon("star" if on else "star_outline",
                                      "due_soon" if on else "text_muted"))

    def _on_star(self, checked: bool) -> None:
        self._refresh_star_icon()
        self.starToggled.emit(self.uuid, checked)

    # --- drag / activate -------------------------------------

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._press_pos is None or not self.uuid:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(UUID_MIME, self.uuid.encode())
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if self.uuid:
            self.activated.emit(self.uuid)
