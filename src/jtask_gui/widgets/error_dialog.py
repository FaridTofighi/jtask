"""Rich error dialog (§23 — real error surfacing).

The human-readable message sits on top; the *actual* failure — the command
line, its exit code and Taskwarrior's stderr — lives behind a disclosure with
copy-to-clipboard, plus a shortcut into the Raw Command Console.  Nothing is
flattened away: whatever ``task`` printed, the user can read and copy.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import icons
from .. import tokens as tok
from ..i18n import t


class ErrorDialog(QDialog):
    def __init__(
        self,
        message: object,
        details: str | None = None,
        parent: QWidget | None = None,
        on_open_console: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorDialog")
        self.setWindowTitle(t("error.title"))
        self.setMinimumWidth(480)

        self._details = (details or "").strip() or None
        self._on_open_console = on_open_console
        self._details_toggle: QToolButton | None = None
        self._details_box: QPlainTextEdit | None = None
        self._copy_btn: QPushButton | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_DIALOG)
        lay.setSpacing(tok.SP_10)

        head = QHBoxLayout()
        head.setSpacing(tok.SP_10)
        glyph = QLabel()
        glyph.setPixmap(icons.icon("overdue", "overdue").pixmap(26, 26))
        head.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        self._msg = QLabel(str(message))
        self._msg.setObjectName("ErrorMessage")
        self._msg.setWordWrap(True)
        self._msg.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        head.addWidget(self._msg, 1)
        lay.addLayout(head)

        if self._details:
            self._details_toggle = QToolButton()
            self._details_toggle.setObjectName("ErrorDetailsToggle")
            self._details_toggle.setText(t("error.details.show"))
            self._details_toggle.setCheckable(True)
            self._details_toggle.setAutoRaise(True)
            self._details_toggle.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            self._details_toggle.setArrowType(Qt.ArrowType.RightArrow)
            self._details_toggle.toggled.connect(self.set_details_visible)
            lay.addWidget(self._details_toggle, 0, Qt.AlignmentFlag.AlignRight)

            box = QPlainTextEdit(self._details)
            box.setObjectName("ErrorDetails")
            box.setReadOnly(True)
            box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            # the command / stderr are ASCII/LTR — never bidi-mangle them
            box.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            box.setVisible(False)
            box.setMinimumHeight(130)
            self._details_box = box
            lay.addWidget(box)

        btns = QDialogButtonBox()
        close_btn = btns.addButton(t("btn.close"), QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn.clicked.connect(self.accept)
        if self._details:
            self._copy_btn = btns.addButton(
                t("error.copy_details"), QDialogButtonBox.ButtonRole.ActionRole
            )
            self._copy_btn.clicked.connect(self.copy_details)
        if on_open_console is not None:
            oc = btns.addButton(
                t("error.open_console"), QDialogButtonBox.ButtonRole.ActionRole
            )
            oc.clicked.connect(self.open_console)
        lay.addWidget(btns)

    # -- accessors (callers + tests) --------------------------------------

    def message_text(self) -> str:
        return self._msg.text()

    def details_text(self) -> str:
        return self._details_box.toPlainText() if self._details_box else ""

    def details_visible(self) -> bool:
        return bool(self._details_box and not self._details_box.isHidden())

    def details_toggle(self) -> QToolButton | None:
        return self._details_toggle

    def copy_button(self) -> QPushButton | None:
        return self._copy_btn

    # -- actions --------------------------------------------------------

    def set_details_visible(self, on: bool) -> None:
        if not self._details_box:
            return
        self._details_box.setVisible(on)
        if self._details_toggle:
            self._details_toggle.blockSignals(True)
            self._details_toggle.setChecked(on)
            self._details_toggle.blockSignals(False)
            self._details_toggle.setText(
                t("error.details.hide") if on else t("error.details.show")
            )
            self._details_toggle.setArrowType(
                Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow
            )
        self.adjustSize()

    def copy_details(self) -> None:
        cb = QApplication.clipboard()
        if cb is not None and self._details:
            cb.setText(self._details)

    def open_console(self) -> None:
        if self._on_open_console is not None:
            self._on_open_console()
        self.accept()
