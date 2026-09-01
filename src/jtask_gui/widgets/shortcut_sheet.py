"""The ``?`` keyboard cheat-sheet overlay — renders from ``shortcuts.SHORTCUTS``."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as tok
from ..i18n import t
from ..shortcuts import by_category


def _key_label(keys: str) -> QLabel:
    text = QKeySequence(keys).toString(QKeySequence.SequenceFormat.NativeText) or keys
    lbl = QLabel(text)
    lbl.setObjectName("KeyCap")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


class ShortcutSheet(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ShortcutSheet")
        self.setWindowTitle(t("sc.sheet.title"))
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_12)

        heading = QLabel(t("sc.sheet.title"))
        heading.setObjectName("H1")
        root.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("SheetScroll")
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(tok.SP_16)

        for cat_key, items in by_category():
            cap = QLabel(t(cat_key))
            cap.setObjectName("Section")
            col.addWidget(cap)
            grid = QGridLayout()
            grid.setHorizontalSpacing(tok.SP_16)
            grid.setVerticalSpacing(tok.SP_6)
            grid.setColumnStretch(1, 1)
            for r, sc in enumerate(items):
                grid.addWidget(_key_label(sc.keys), r, 0, Qt.AlignmentFlag.AlignTop)
                desc = QLabel(t(sc.desc_key))
                desc.setWordWrap(True)
                grid.addWidget(desc, r, 1)
            wrap = QWidget()
            wrap.setLayout(grid)
            col.addWidget(wrap)

        col.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.resize(460, 520)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Question):
            self.accept()
            return
        super().keyPressEvent(event)
