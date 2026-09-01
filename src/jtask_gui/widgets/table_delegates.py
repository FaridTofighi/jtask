"""Inline cell editors for the task table (project / priority / due).

Each delegate wraps a widget that already exists elsewhere in the app — the
shared project autocompleter, the detail panel's priority combo pattern, and
the calendar-system-aware :class:`JalaliDatePicker` — never a fresh one-off.
Commits flow: delegate → ``model.setData(EditRole)`` → ``TaskTableModel``
emits ``cellEdited`` → ``MainWindow`` runs one ``task <uuid> modify`` write.
Escape cancels with no write (Qt default). A freshly opened editor shows the
current value and no validation error (mission-d rule).
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QStyledItemDelegate

from ..i18n import t
from .autocomplete import make_token_completer
from .jalali_date_picker import JalaliDatePicker

_PRIORITIES: list[tuple[str, str]] = [
    ("col.priority.none", ""),
    ("col.priority.l", "L"),
    ("col.priority.m", "M"),
    ("col.priority.h", "H"),
]


class _ProjectDelegate(QStyledItemDelegate):
    def __init__(self, projects: Callable[[], list[str]], parent=None) -> None:
        super().__init__(parent)
        self._projects = projects

    def createEditor(self, parent, option, index):  # noqa: N802
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.addItems(["", *self._projects()])
        combo.setCompleter(make_token_completer(self._projects(), []))
        return combo

    def setEditorData(self, editor, index):  # noqa: N802
        editor.setCurrentText(index.data(Qt.ItemDataRole.EditRole) or "")

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.currentText().strip(), Qt.ItemDataRole.EditRole)


class _PriorityDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):  # noqa: N802
        combo = QComboBox(parent)
        for label_key, _code in _PRIORITIES:
            combo.addItem(t(label_key))
        return combo

    def setEditorData(self, editor, index):  # noqa: N802
        code = (index.data(Qt.ItemDataRole.EditRole) or "").upper()
        editor.setCurrentIndex(
            next((i for i, (_, c) in enumerate(_PRIORITIES) if c == code), 0)
        )

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, _PRIORITIES[editor.currentIndex()][1], Qt.ItemDataRole.EditRole)


class _DueDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):  # noqa: N802
        return JalaliDatePicker(parent)

    def setEditorData(self, editor, index):  # noqa: N802
        editor.set_from_taskwarrior(index.data(Qt.ItemDataRole.EditRole) or "")

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.gregorian_string(), Qt.ItemDataRole.EditRole)


def install_inline_editors(view, projects: Callable[[], list[str]]) -> None:
    """Attach the three inline delegates to *view* by column key."""
    src = view.model()
    # unwrap proxies to reach TaskTableModel for the column order
    while hasattr(src, "sourceModel") and src.sourceModel() is not None:
        src = src.sourceModel()
    keys = src.visible_columns()
    by_key = {
        "project": _ProjectDelegate(projects, view),
        "priority": _PriorityDelegate(view),
        "due": _DueDelegate(view),
    }
    for key, deleg in by_key.items():
        if key in keys:
            view.setItemDelegateForColumn(keys.index(key), deleg)
