"""Dedicated annotations tab — list with Jalali timestamps, add / delete."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as tok
from ..bidi import align_item, bind_auto_direction, directional_isolate
from ..calendar_system import active
from ..i18n import t


class AnnotationsView(QWidget):
    annotateRequested = pyqtSignal(str, str)   # uuid, text
    denotateRequested = pyqtSignal(str, str)   # uuid, text

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._uuid: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_PANEL)
        lay.setSpacing(tok.SP_10)

        heading = QLabel(t("detail.annotations"))
        heading.setObjectName("H2")
        lay.addWidget(heading)

        self._list = QListWidget()
        self._list.setObjectName("AnnotationsList")
        lay.addWidget(self._list, 1)

        self._empty = QLabel(t("detail.annotations.empty"))
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        lay.addWidget(self._empty)

        row = QHBoxLayout()
        row.setSpacing(tok.SP_6)
        self._input = QLineEdit()
        self._input.setPlaceholderText(t("detail.annotation.new"))
        self._input.returnPressed.connect(self._add)
        bind_auto_direction(self._input)
        add = QPushButton(t("btn.add"))
        add.clicked.connect(self._add)
        delete = QPushButton(t("detail.annotation.delete"))
        delete.clicked.connect(self._delete)
        row.addWidget(self._input, 1)
        row.addWidget(add)
        row.addWidget(delete)
        lay.addLayout(row)

    def load_task(self, task: dict) -> None:
        self._uuid = task.get("uuid")
        self._list.clear()
        annotations = task.get("annotations") or []
        for ann in annotations:
            when = ann.get("entry", "")
            if when and not when.startswith("۱"):
                when = active().format_utc(when, "short")
            desc = ann.get("description", "")
            item = QListWidgetItem(f"{when} — {directional_isolate(desc)}")
            item.setData(Qt.ItemDataRole.UserRole, desc)
            align_item(item, desc)
            self._list.addItem(item)
        has = bool(annotations)
        self._list.setVisible(has)
        self._empty.setVisible(not has)

    def _add(self) -> None:
        text = self._input.text().strip()
        if self._uuid and text:
            self.annotateRequested.emit(self._uuid, text)
            self._input.clear()

    def _delete(self) -> None:
        item = self._list.currentItem()
        if self._uuid and item:
            self.denotateRequested.emit(
                self._uuid, item.data(Qt.ItemDataRole.UserRole)
            )
