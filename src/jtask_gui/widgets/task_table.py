"""Task table view: sorting, grouping, multi-select, bulk actions, row actions."""

from __future__ import annotations

from PyQt6.QtCore import QMimeData, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QTableView,
)

from ..models.task_model import TASK_ROLE, UUID_ROLE, TaskTableModel

UUID_MIME = "application/x-jtask-uuids"

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
    duplicateRequested = pyqtSignal(list)    # list[uuid]
    appendRequested = pyqtSignal(list)       # list[uuid] — caller prompts for text
    prependRequested = pyqtSignal(list)      # list[uuid]
    purgeRequested = pyqtSignal(list)        # list[uuid] (deleted tasks only)
    bulkEditRequested = pyqtSignal(list)     # list[uuid]

    def __init__(self, model: TaskTableModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._proxy = _GroupProxy()
        self._proxy.setSourceModel(model)
        self.setModel(self._proxy)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
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

    def startDrag(self, actions):  # noqa: N802
        uuids = self.selected_uuids()
        if not uuids:
            return
        mime = QMimeData()
        mime.setData(UUID_MIME, " ".join(uuids).encode())
        mime.setText("، ".join(uuids))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

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

    def selected_tasks(self) -> list[dict]:
        rows = {i.row() for i in self.selectionModel().selectedRows()}
        out = []
        for r in rows:
            src = self._proxy.mapToSource(self._proxy.index(r, 0))
            task = self._model.data(src, TASK_ROLE)
            if task:
                out.append(task)
        return out

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
        tasks = self.selected_tasks()
        uuids = [t.get("uuid") for t in tasks if t.get("uuid")]
        if not uuids:
            return
        n = len(uuids)
        deleted = [t["uuid"] for t in tasks if t.get("status") == "deleted"]

        menu = QMenu(self)
        act_done = menu.addAction(f"انجام‌شده ({n})")
        act_del = menu.addAction(f"حذف ({n})")
        act_dup = menu.addAction(f"تکثیر ({n})")
        menu.addSeparator()
        act_bulk = menu.addAction(f"ویرایش گروهی… ({n})")
        act_append = menu.addAction("افزودن به شرح…")
        act_prepend = menu.addAction("پیش‌افزودن به شرح…")
        menu.addSeparator()
        act_start = menu.addAction("شروع زمان‌سنجی")
        act_stop = menu.addAction("توقف زمان‌سنجی")
        act_purge = None
        if deleted:
            menu.addSeparator()
            act_purge = menu.addAction(f"پاک‌سازی برای همیشه… ({len(deleted)})")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_done:
            self.doneRequested.emit(uuids)
        elif chosen == act_del:
            self.deleteRequested.emit(uuids)
        elif chosen == act_dup:
            self.duplicateRequested.emit(uuids)
        elif chosen == act_bulk:
            self.bulkEditRequested.emit(uuids)
        elif chosen == act_append:
            self.appendRequested.emit(uuids)
        elif chosen == act_prepend:
            self.prependRequested.emit(uuids)
        elif chosen == act_start:
            self.startStopRequested.emit(uuids[0], True)
        elif chosen == act_stop:
            self.startStopRequested.emit(uuids[0], False)
        elif act_purge is not None and chosen == act_purge:
            self.purgeRequested.emit(deleted)
