"""Collapsible group-header proxy for the task table.

Wraps the (already group-sorted) source model and injects one spanning
*header* row before each run of rows that share a group value. Headers can be
collapsed to hide their children. Only used while a group-by is active — with
``group = none`` the table binds straight to the flat model and this proxy is
out of the picture entirely.
"""

from __future__ import annotations

from PyQt6.QtCore import QAbstractProxyModel, QModelIndex, Qt

from ..i18n import t
from .task_model import TASK_ROLE

GROUP_HEADER_ROLE = Qt.ItemDataRole.UserRole + 20
GROUP_KEY_ROLE = Qt.ItemDataRole.UserRole + 21
GROUP_COLLAPSED_ROLE = Qt.ItemDataRole.UserRole + 22

_NONE = object()


def group_value(task: dict, key: str) -> str:
    """The bucket a task falls in for *key* (project / priority / due / status)."""
    if key == "priority":
        return task.get("priority") or t("group.value.no_priority")
    if key == "status":
        return task.get("status") or "—"
    if key == "project":
        return task.get("project") or t("group.value.no_project")
    if key == "due":
        due = task.get("due")
        return str(due) if due else t("group.value.no_due")
    return str(task.get(key) or "—")


class GroupProxyModel(QAbstractProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._key: str | None = None
        self._collapsed: set[str] = set()
        # layout entries: ("header", group, count) | ("row", source_row)
        self._layout: list[tuple] = []

    # --- configuration -------------------------------------------------

    def set_group_key(self, key: str | None) -> None:
        self._key = key or None
        self._rebuild()

    def toggle(self, group: str) -> None:
        if group in self._collapsed:
            self._collapsed.discard(group)
        else:
            self._collapsed.add(group)
        self._rebuild()

    def is_header(self, row: int) -> bool:
        return 0 <= row < len(self._layout) and self._layout[row][0] == "header"

    def header_rows(self) -> list[int]:
        return [i for i, e in enumerate(self._layout) if e[0] == "header"]

    # --- rebuild -----------------------------------------------------

    def _source_task(self, source_row: int) -> dict:
        src = self.sourceModel()
        return src.data(src.index(source_row, 0), TASK_ROLE) or {}

    def _rebuild(self) -> None:
        self.beginResetModel()
        self._layout = []
        src = self.sourceModel()
        if src is not None and self._key:
            n = src.rowCount()
            groups: list[tuple[str, list[int]]] = []
            current = _NONE
            for r in range(n):
                gv = group_value(self._source_task(r), self._key)
                if gv != current:
                    groups.append((gv, []))
                    current = gv
                groups[-1][1].append(r)
            for gv, rows in groups:
                self._layout.append(("header", gv, len(rows)))
                if gv not in self._collapsed:
                    for r in rows:
                        self._layout.append(("row", r))
        self.endResetModel()

    # --- QAbstractProxyModel ---------------------------------------

    def setSourceModel(self, model) -> None:  # noqa: N802
        old = self.sourceModel()
        if old is not None:
            for sig in (
                old.modelReset, old.rowsInserted, old.rowsRemoved,
                old.layoutChanged, old.dataChanged,
            ):
                try:
                    sig.disconnect(self._on_source_changed)
                except TypeError:
                    pass
        super().setSourceModel(model)
        if model is not None:
            model.modelReset.connect(self._on_source_changed)
            model.rowsInserted.connect(self._on_source_changed)
            model.rowsRemoved.connect(self._on_source_changed)
            model.layoutChanged.connect(self._on_source_changed)
            model.dataChanged.connect(self._on_source_changed)
        self._rebuild()

    def _on_source_changed(self, *_a) -> None:
        self._rebuild()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._layout)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        src = self.sourceModel()
        return src.columnCount() if src is not None else 0

    def index(self, row, column, parent=QModelIndex()):
        if parent.isValid() or not (0 <= row < len(self._layout)):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, _index):  # noqa: N802
        return QModelIndex()

    def mapToSource(self, proxy_index):  # noqa: N802
        if not proxy_index.isValid():
            return QModelIndex()
        entry = self._layout[proxy_index.row()]
        if entry[0] != "row":
            return QModelIndex()
        src = self.sourceModel()
        return src.index(entry[1], proxy_index.column())

    def mapFromSource(self, source_index):  # noqa: N802
        if not source_index.isValid():
            return QModelIndex()
        for i, entry in enumerate(self._layout):
            if entry[0] == "row" and entry[1] == source_index.row():
                return self.createIndex(i, source_index.column())
        return QModelIndex()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        src = self.sourceModel()
        return src.headerData(section, orientation, role) if src is not None else None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if self._layout[index.row()][0] == "header":
            return Qt.ItemFlag.ItemIsEnabled
        return super().flags(index)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._layout[index.row()]
        if entry[0] == "header":
            _, group, count = entry
            if role == GROUP_HEADER_ROLE:
                return True
            if role == GROUP_KEY_ROLE:
                return group
            if role == GROUP_COLLAPSED_ROLE:
                return group in self._collapsed
            if role == Qt.ItemDataRole.DisplayRole and index.column() == 0:
                caret = "▸" if group in self._collapsed else "▾"
                return f"{caret}  {group}  ({count})"
            if role == Qt.ItemDataRole.FontRole:
                from PyQt6.QtGui import QFont

                f = QFont()
                f.setBold(True)
                return f
            return None
        if role == GROUP_HEADER_ROLE:
            return False
        return super().data(index, role)
