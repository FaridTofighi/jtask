"""GUI-enforced confirmation layer (§ M5).

Every destructive or bulk action routes through :func:`confirm` *before* any
``task`` command runs.  This gate is independent of the user's
``rc.confirmation`` / ``rc.bulk`` settings — jtask always calls Taskwarrior with
``rc.confirmation=off rc.bulk=0`` (so ``task`` never blocks on its own prompt),
which makes this dialog the single, predictable place a user says yes or no.

- ``count`` shows exactly how many tasks are affected (Persian digits).
- ``destructive`` styles the confirm button as dangerous.
- ``require_phrase`` adds a hard confirmation: the button stays disabled until
  the user types the given word (used by purge).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import fmt, icons
from .. import tokens as tok
from ..i18n import t


class ConfirmDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        body: str,
        count: int | None = None,
        count_noun: str = "",
        destructive: bool = False,
        confirm_label: str = "",
        require_phrase: str | None = None,
        details: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ConfirmDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self._require_phrase = (require_phrase or "").strip() or None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_DIALOG)
        lay.setSpacing(tok.SP_12)

        head = QHBoxLayout()
        head.setSpacing(tok.SP_10)
        glyph = QLabel()
        role = "overdue" if destructive else "due_soon"
        name = "delete" if destructive else "overdue"
        glyph.setPixmap(icons.icon(name, role).pixmap(24, 24))
        head.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

        noun = count_noun or t("confirm.count_noun")
        text = body
        if count is not None:
            text = t(
                "confirm.affects", body=body, count=fmt.num(count), noun=noun
            )
        self._body = QLabel(text)
        self._body.setObjectName("ConfirmBody")
        self._body.setWordWrap(True)
        head.addWidget(self._body, 1)
        lay.addLayout(head)

        self._details_box: QPlainTextEdit | None = None
        if details:
            box = QPlainTextEdit(details.strip())
            box.setObjectName("ConfirmDetails")
            box.setReadOnly(True)
            box.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            box.setMaximumHeight(160)
            box.moveCursor(QTextCursor.MoveOperation.Start)
            box.ensureCursorVisible()
            self._details_box = box
            lay.addWidget(box)

        self._phrase_edit: QLineEdit | None = None
        if self._require_phrase:
            hint = QLabel(t("confirm.phrase_hint", phrase=self._require_phrase))
            hint.setObjectName("Muted")
            lay.addWidget(hint)
            self._phrase_edit = QLineEdit()
            self._phrase_edit.setObjectName("ConfirmPhrase")
            self._phrase_edit.textChanged.connect(self._sync_enabled)
            lay.addWidget(self._phrase_edit)

        btns = QDialogButtonBox()
        self._cancel_btn = btns.addButton(
            t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._cancel_btn.clicked.connect(self.reject)
        self._confirm_btn = btns.addButton(
            confirm_label or t("btn.confirm"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._confirm_btn.setObjectName("Danger" if destructive else "Primary")
        self._confirm_btn.clicked.connect(self.accept)
        self._confirm_btn.setDefault(not bool(self._require_phrase))
        lay.addWidget(btns)

        self._sync_enabled()

    def _sync_enabled(self) -> None:
        ok = True
        if self._require_phrase and self._phrase_edit is not None:
            ok = self._phrase_edit.text().strip() == self._require_phrase
        self._confirm_btn.setEnabled(ok)

    # -- accessors (callers + tests) --

    def body_text(self) -> str:
        return self._body.text()


def confirm(
    parent: QWidget | None,
    *,
    title: str,
    body: str,
    count: int | None = None,
    count_noun: str = "",
    destructive: bool = False,
    confirm_label: str = "",
    require_phrase: str | None = None,
    details: str | None = None,
) -> bool:
    """Show the confirmation dialog; return ``True`` only if the user confirmed."""
    dlg = ConfirmDialog(
        title=title,
        body=body,
        count=count,
        count_noun=count_noun,
        destructive=destructive,
        confirm_label=confirm_label,
        require_phrase=require_phrase,
        details=details,
        parent=parent,
    )
    return dlg.exec() == QDialog.DialogCode.Accepted
