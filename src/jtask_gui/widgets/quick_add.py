"""Always-visible quick-add input with a live parse preview."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from jtask import taskwarrior

from .. import icons
from .. import tokens as tok
from ..bidi import bind_auto_direction
from ..i18n import t
from ..quickadd import ParsedQuickAdd, parse_quick_add, preview_text
from .autocomplete import make_token_completer


class QuickAddBar(QWidget):
    """Emits ``taskRequested(list[str])`` (Gregorian args) when committed."""

    taskRequested = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_2)

        self._edit = QLineEdit()
        self._edit.setObjectName("QuickAdd")
        self._edit.setClearButtonEnabled(True)
        self._edit.addAction(
            icons.icon("add", "text_muted"), QLineEdit.ActionPosition.LeadingPosition
        )
        self._edit.setPlaceholderText(t("quickadd.bar.placeholder"))
        self._edit.textChanged.connect(self._update_preview)
        self._edit.returnPressed.connect(self._commit)
        bind_auto_direction(self._edit)
        lay.addWidget(self._edit)

        self._preview = QLabel()
        self._preview.setObjectName("Muted")
        self._preview.setMinimumHeight(16)
        lay.addWidget(self._preview)

        self._parsed: ParsedQuickAdd = ParsedQuickAdd()
        self.refresh_completions()

    def refresh_completions(self) -> None:
        try:
            projects = taskwarrior.list_projects()
            tags = taskwarrior.list_tags()
        except Exception:  # noqa: BLE001
            projects, tags = [], []
        self._edit.setCompleter(make_token_completer(projects, tags))

    def _update_preview(self, text: str) -> None:
        self._parsed = parse_quick_add(text)
        self._preview.setText(preview_text(self._parsed))

    def _commit(self) -> None:
        if self._parsed.ok:
            self.taskRequested.emit(self._parsed.raw_args)
            self._edit.clear()
            self._preview.clear()

    def focus(self) -> None:
        self._edit.setFocus()
