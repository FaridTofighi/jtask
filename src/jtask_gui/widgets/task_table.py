"""Task table view: sorting, grouping, multi-select, bulk actions, row actions."""

from __future__ import annotations

from PyQt6.QtCore import QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QTableView,
)

from ..models.task_model import TASK_ROLE, UUID_ROLE, TaskTableModel

_EMPTY_MESSAGES = {
    "امروز": "برای امروز کاری سررسید نشده. نفسی تازه کن یا کاری برنامه‌ریزی کن.",
    "این هفته": "این هفته کاری سررسید ندارد.",
    "معوق": "هیچ کار عقب‌افتاده‌ای نداری — عالی!",
    "در انتظار": "چیزی در انتظارِ دیگران نیست.",
    "مسدودشده": "هیچ کاری مسدود نشده است.",
    "تکمیل‌شده": "هنوز کاری تکمیل نکرده‌ای.",
    "اقدامات بعدی": "فهرست اقدامات بعدی خالی است. با نوار «افزودن سریع» کاری اضافه کن.",
}

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
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(40)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        hh.setHighlightSections(False)
        self._apply_column_sizing()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double)
        self.selectionModel().selectionChanged.connect(self._on_selection)

        self._empty = QLabel("", self.viewport())
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()

    def _apply_column_sizing(self) -> None:
        from ..models.column_spec import BY_KEY

        hh = self.horizontalHeader()
        for i, key in enumerate(self._model.visible_columns()):
            col = BY_KEY.get(key)
            if col is None:
                continue
            if key == "description":
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif col.indicator:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.setColumnWidth(i, col.width)
            else:
                self.setColumnWidth(i, col.width)

    def show_empty_state(self, view_title: str, is_empty: bool) -> None:
        if not is_empty:
            self._empty.hide()
            return
        self._empty.setText(
            _EMPTY_MESSAGES.get(view_title, "موردی برای نمایش نیست.")
        )
        self._position_empty()
        self._empty.show()
        self._empty.raise_()

    def _position_empty(self) -> None:
        vp = self.viewport().rect()
        self._empty.setGeometry(vp.adjusted(40, 40, -40, -40))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._position_empty()

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
