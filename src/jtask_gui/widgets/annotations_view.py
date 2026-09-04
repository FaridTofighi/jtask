"""Dedicated annotations tab — wrapped note cards, add / delete.

Each annotation is its own widget (``_NoteCard``), not a single-line list item
— that's what makes the full note text wrap to the panel's width instead of
requiring horizontal scroll or a wider panel. Cards get a subtle, bounded,
theme-derived tint (``theme.NOTE_TINT_ROLES``, cycled) purely for visual
separation between adjacent notes; selection reuses the same background-only
convention as table rows (``@selection@``, no per-card border artifact).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jtask.rtl import bidi_isolate

from .. import tokens as tok
from ..bidi import apply_content_direction, bind_auto_direction, directional_isolate
from ..calendar_system import active
from ..i18n import t
from ..theme import NOTE_TINT_ROLES


class _NoteCard(QFrame):
    """One annotation: a small muted timestamp above the wrapped note body."""

    def __init__(self, when_raw: str, desc: str, tint_index: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AnnotationCard")
        self.setProperty("tint", str(tint_index))
        self.desc = desc

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_2)

        when = when_raw
        if when and not when.startswith("۱"):
            when = active().format_utc(when, "short")
        self._when_label = QLabel(bidi_isolate(when) if when else "")
        self._when_label.setObjectName("AnnotationWhen")
        lay.addWidget(self._when_label)

        self._body = QLabel(directional_isolate(desc))
        self._body.setObjectName("AnnotationBody")
        self._body.setWordWrap(True)
        apply_content_direction(self._body, desc)
        lay.addWidget(self._body)

    def set_selected(self, selected: bool) -> None:
        if self.property("selected") != selected:
            self.setProperty("selected", selected)
            self.style().unpolish(self)
            self.style().polish(self)


class _WrapList(QListWidget):
    """A ``QListWidget`` whose item widgets re-wrap (and the items' size hints
    update) whenever the viewport width changes — never a horizontal scrollbar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.relayout()

    def relayout(self) -> None:
        width = self.viewport().width()
        if width <= 0:
            return
        for i in range(self.count()):
            item = self.item(i)
            card = self.itemWidget(item)
            if card is None:
                continue
            card.setFixedWidth(width)
            item.setSizeHint(card.sizeHint())


class AnnotationsView(QWidget):
    annotateRequested = pyqtSignal(str, str)   # uuid, text
    denotateRequested = pyqtSignal(str, str)   # uuid, text

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnnotationsView")
        self._uuid: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_PANEL)
        lay.setSpacing(tok.SP_10)

        heading = QLabel(t("detail.annotations"))
        heading.setObjectName("H2")
        lay.addWidget(heading)

        self._list = _WrapList()
        self._list.setObjectName("AnnotationsList")
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        lay.addWidget(self._list, 1)

        self._empty = QLabel(t("detail.annotations.empty"))
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        lay.addWidget(self._empty)

        # the primary input for this tab: a real multi-line box, above the
        # action row — not squeezed between the buttons.
        self._input = QPlainTextEdit()
        self._input.setObjectName("AnnotationInput")
        self._input.setPlaceholderText(t("detail.annotation.new"))
        self._input.setMinimumHeight(tok.SP_24 * 3)   # comfortable for a sentence or two
        bind_auto_direction(self._input)
        lay.addWidget(self._input)

        self._button_row = QHBoxLayout()
        self._button_row.setSpacing(tok.SP_6)
        self._add_btn = QPushButton(t("btn.add"))
        self._add_btn.setObjectName("Primary")
        self._add_btn.clicked.connect(self._add)
        self._delete_btn = QPushButton(t("detail.annotation.delete"))
        self._delete_btn.clicked.connect(self._delete)
        self._button_row.addWidget(self._add_btn)
        self._button_row.addWidget(self._delete_btn)
        self._button_row.addStretch(1)
        lay.addLayout(self._button_row)

    def load_task(self, task: dict) -> None:
        self._uuid = task.get("uuid")
        self._list.clear()
        annotations = task.get("annotations") or []
        for i, ann in enumerate(annotations):
            desc = ann.get("description", "")
            card = _NoteCard(ann.get("entry", ""), desc, (i % len(NOTE_TINT_ROLES)) + 1)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, desc)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._list.addItem(item)
            self._list.setItemWidget(item, card)
        self._list.relayout()
        has = bool(annotations)
        self._list.setVisible(has)
        self._empty.setVisible(not has)

    def _on_selection_changed(self) -> None:
        # QListWidgetItem isn't hashable in PyQt6 — check isSelected() per row
        # rather than building a set of selectedItems().
        for i in range(self._list.count()):
            item = self._list.item(i)
            card = self._list.itemWidget(item)
            if card is not None:
                card.set_selected(item.isSelected())

    def _add(self) -> None:
        text = self._input.toPlainText().strip()
        if self._uuid and text:
            self.annotateRequested.emit(self._uuid, text)
            self._input.clear()

    def _delete(self) -> None:
        item = self._list.currentItem()
        if self._uuid and item:
            self.denotateRequested.emit(
                self._uuid, item.data(Qt.ItemDataRole.UserRole)
            )
