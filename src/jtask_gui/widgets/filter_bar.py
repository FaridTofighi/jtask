"""Raw Taskwarrior filter input + a visual filter builder + save-as."""

from __future__ import annotations

import shlex

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QInputDialog, QLineEdit, QToolButton, QWidget

from jtask import rewrite, taskwarrior

from .. import icons
from ..i18n import t
from .autocomplete import make_token_completer
from .filter_builder import FilterBuilder


class _FilterLineEdit(QLineEdit):
    """A QLineEdit that keeps a middle-elided view of long queries when unfocused
    and always exposes the complete query as its tooltip."""

    def focusOutEvent(self, event):  # noqa: N802
        super().focusOutEvent(event)
        self.setCursorPosition(0)

    def focusInEvent(self, event):  # noqa: N802
        super().focusInEvent(event)
        self.setCursorPosition(len(self.text()))


class FilterBar(QWidget):
    """Emits ``filterChanged(list[str])`` — Gregorian-rewritten filter tokens."""

    filterChanged = pyqtSignal(list)
    saveRequested = pyqtSignal(str, str)  # (name, raw filter string)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._builder_btn = QToolButton()
        self._builder_btn.setToolTip(t("filterbar.builder_tip"))
        self._builder_btn.clicked.connect(self._open_builder)
        row.addWidget(self._builder_btn)

        self._edit = _FilterLineEdit()
        self._edit.setObjectName("FilterEdit")
        self._edit.setClearButtonEnabled(True)
        self._edit.setPlaceholderText(
            t("filterbar.placeholder")
        )
        self._edit.textChanged.connect(self._on_text)
        self._edit.returnPressed.connect(self._apply)
        row.addWidget(self._edit, 1)

        self._apply_btn = QToolButton()
        self._apply_btn.setToolTip(t("filterbar.apply_tip"))
        self._apply_btn.clicked.connect(self._apply)
        row.addWidget(self._apply_btn)

        self._save_btn = QToolButton()
        self._save_btn.setText("★")
        self._save_btn.setToolTip(t("filterbar.save_tip"))
        self._save_btn.clicked.connect(self._save)
        row.addWidget(self._save_btn)

        self._clear_btn = QToolButton()
        self._clear_btn.setToolTip(t("filterbar.clear_tip"))
        self._clear_btn.clicked.connect(self.clear)
        row.addWidget(self._clear_btn)

        self.retint()
        self.refresh_completions()

    def retint(self) -> None:
        self._apply_btn.setIcon(icons.icon("filter"))
        self._clear_btn.setIcon(icons.icon("clear"))
        self._builder_btn.setIcon(icons.icon("group"))

    def _open_builder(self) -> None:
        dlg = FilterBuilder(self._edit.text().strip(), self)
        dlg.applied.connect(self._builder_applied)
        dlg.exec()

    def _builder_applied(self, tokens: list[str], raw_display: str) -> None:
        self._edit.setText(raw_display)
        self.filterChanged.emit(tokens)

    def _save(self) -> None:
        raw = self._edit.text().strip()
        if not raw:
            return
        name, ok = QInputDialog.getText(self, t("filterbar.save.title"), t("filterbar.save.label"))
        if ok and name.strip():
            self.saveRequested.emit(name.strip(), raw)

    def _on_text(self, text: str) -> None:
        self._edit.setToolTip(text or t("filterbar.none_applied"))

    def refresh_completions(self) -> None:
        try:
            projects = taskwarrior.list_projects()
            tags = taskwarrior.list_tags()
            udas = list(taskwarrior.uda_definitions())
        except Exception:  # noqa: BLE001
            projects, tags, udas = [], [], []
        self._edit.setCompleter(make_token_completer(projects, tags, udas))

    def raw_text(self) -> str:
        return self._edit.text().strip()

    def set_text(self, text: str) -> None:
        self._edit.setText(text)

    def clear(self) -> None:
        self._edit.clear()
        self.filterChanged.emit([])

    def current_filter(self) -> list[str]:
        text = self._edit.text().strip()
        if not text:
            return []
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()
        return rewrite.rewrite_args(tokens)

    def _apply(self) -> None:
        self.filterChanged.emit(self.current_filter())
