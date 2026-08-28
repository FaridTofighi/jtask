"""Task table view: sorting, grouping, multi-select, bulk actions, row actions."""

from __future__ import annotations

from PyQt6.QtCore import QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableView,
)

from ..models.task_model import TASK_ROLE, UUID_ROLE, TaskTableModel

_GROUP_KEYS = {
    "none": None,
    "project": "project",
    "priority": "priority",
    "due": "due",
    "status": "status",
}


class _GroupProxy(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self._group_key: str | None = None
        self.setSortRole(Qt.ItemDataRole.DisplayRole)

    def set_group_key(self, key: str | None) -> None:
        self._group_key = key
        self.invalidate()
        self.sort(self.sortColumn() if self.sortColumn() >= 0 else 0)

    def lessThan(self, left, right):  # noqa: N802
        model: TaskTableModel = self.sourceModel()
        if self._group_key:
            lt = model.task_at(left.row()) or {}
            rt = model.task_at(right.row()) or {}
            lg, rg = str(lt.get(self._group_key, "")), str(rt.get(self._group_key, ""))
            if lg != rg:
                return lg < rg
        return super().lessThan(left, right)


class TaskTable(QTableView):
    taskActivated = pyqtSignal(dict)         # double-click / selection -> task dict
    doneRequested = pyqtSignal(list)         # list[uuid]
    deleteRequested = pyqtSignal(list)
    startStopRequested = pyqtSignal(str, bool)   # uuid, start?

    def __init__(self, model: TaskTableModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._proxy = _GroupProxy()
        self._proxy.setSourceModel(model)
        self.setModel(self._proxy)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double)
        self.selectionModel().selectionChanged.connect(self._on_selection)

    # --- API ---------------------------------------------------

    def set_group_key(self, key: str) -> None:
        self._proxy.set_group_key(_GROUP_KEYS.get(key))

    def selected_uuids(self) -> list[str]:
        rows = {i.row() for i in self.selectionModel().selectedRows()}
        out = []
        for r in rows:
            src = self._proxy.mapToSource(self._proxy.index(r, 0))
            uuid = self._model.data(src, UUID_ROLE)
            if uuid:
                out.append(uuid)
        return out

    def current_task(self) -> dict | None:
        idx = self.currentIndex()
        if not idx.isValid():
            return None
        src = self._proxy.mapToSource(idx)
        return self._model.data(src, TASK_ROLE)

    # --- events -----------------------------------------------

    def _on_double(self, index) -> None:
        src = self._proxy.mapToSource(index)
        task = self._model.data(src, TASK_ROLE)
        if task:
            self.taskActivated.emit(task)

    def _on_selection(self, *_a) -> None:
        task = self.current_task()
        if task:
            self.taskActivated.emit(task)

    def _context_menu(self, pos) -> None:
        uuids = self.selected_uuids()
        if not uuids:
            return
        menu = QMenu(self)
        act_done = menu.addAction(f"انجام‌شده ({len(uuids)})")
        act_del = menu.addAction(f"حذف ({len(uuids)})")
        menu.addSeparator()
        act_start = menu.addAction("شروع زمان‌سنجی")
        act_stop = menu.addAction("توقف زمان‌سنجی")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_done:
            self.doneRequested.emit(uuids)
        elif chosen == act_del:
            self.deleteRequested.emit(uuids)
        elif chosen == act_start:
            self.startStopRequested.emit(uuids[0], True)
        elif chosen == act_stop:
            self.startStopRequested.emit(uuids[0], False)
