"""Task table view: sorting, grouping, multi-select, bulk actions, row actions."""

from __future__ import annotations

from PyQt6.QtCore import QMimeData, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDrag, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QTableView,
)

from .. import icons
from ..i18n import t
from ..models.group_proxy import (
    GROUP_HEADER_ROLE,
    GROUP_KEY_ROLE,
    GroupProxyModel,
)
from ..models.task_model import TASK_ROLE, UUID_ROLE, TaskTableModel
from ..theme import palette

UUID_MIME = "application/x-jtask-uuids"

# keyed by the sidebar quick-view *stable key* (i2), not its display label
_EMPTY_KEYS = frozenset({
    "today", "week", "overdue", "waiting", "blocked", "completed", "next",
})

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
    annotateRequested = pyqtSignal(list)     # list[uuid] — caller prompts for text
    purgeRequested = pyqtSignal(list)        # list[uuid] (deleted tasks only)
    bulkEditRequested = pyqtSignal(list)     # list[uuid]

    def __init__(self, model: TaskTableModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._proxy = _GroupProxy()
        self._proxy.setSourceModel(model)
        self._group_model = GroupProxyModel(self)
        self._group_model.setSourceModel(self._proxy)
        self._group_model.modelReset.connect(self._apply_group_spans)
        self._grouped = False
        self.setModel(self._proxy)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)  # zebra (M1 design decision, @row_alt@)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        vh = self.verticalHeader()
        vh.setVisible(False)
        self._row_h = {"comfortable": 40, "compact": 30}
        vh.setDefaultSectionSize(self._row_h["comfortable"])

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        hh.setHighlightSections(False)
        self._apply_column_sizing()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double)
        self.clicked.connect(self._on_click)
        self._connect_selection()

        # keyboard shortcuts on the selected task(s)
        for seq, slot in (
            ("Ctrl+S", lambda: self._timer_shortcut(True)),
            ("Ctrl+Shift+S", lambda: self._timer_shortcut(False)),
            ("Ctrl+D", self._done_shortcut),
            ("Ctrl+E", self._open_detail_shortcut),
            ("Return", self._open_detail_shortcut),
            ("Enter", self._open_detail_shortcut),
            (QKeySequence.StandardKey.Delete, self._delete_shortcut),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)

        self._empty = QLabel("", self.viewport())
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()

        self._accent = QColor(palette(icons._theme)["primary"])

        # inline cell editors (project / priority / due) — double-click a cell
        self._projects: list[str] = []
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        from .table_delegates import install_inline_editors

        install_inline_editors(self, lambda: self._projects)

    _SELECTION_BAR_W = 3

    def set_projects(self, projects: list[str]) -> None:
        """Feed the inline project editor's autocomplete (shared TW source)."""
        self._projects = list(projects)

    def set_theme(self, name: str) -> None:
        """Keep the selected-row accent bar in sync with the active theme."""
        self._accent = QColor(palette(name)["primary"])
        self.viewport().update()

    def set_density(self, mode: str) -> None:
        """``comfortable`` | ``compact`` — row height only, live."""
        h = self._row_h.get(mode, self._row_h["comfortable"])
        vh = self.verticalHeader()
        vh.setDefaultSectionSize(h)
        for r in range(self.model().rowCount() if self.model() else 0):
            vh.resizeSection(r, h)
        self.viewport().update()

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

    def show_empty_state(self, view_key: str, is_empty: bool) -> None:
        if not is_empty:
            self._empty.hide()
            return
        msg = (
            t(f"view.empty.{view_key}")
            if view_key in _EMPTY_KEYS
            else t("table.empty.generic")
        )
        self._empty.setText(msg)
        self._position_empty()
        self._empty.show()
        self._empty.raise_()

    def _position_empty(self) -> None:
        vp = self.viewport().rect()
        self._empty.setGeometry(vp.adjusted(40, 40, -40, -40))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._position_empty()

    def _bar_x(self) -> int:
        """Left offset of the selected-row accent bar — the reading-start edge:
        left in LTR, right in RTL (reuses the app's layout direction)."""
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        return self.viewport().width() - self._SELECTION_BAR_W if rtl else 0

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        sel = self.selectionModel()
        if sel is None or not sel.hasSelection():
            return
        rows = {i.row() for i in sel.selectedRows()}
        if not rows:
            return
        x, w, vp_h = self._bar_x(), self._SELECTION_BAR_W, self.viewport().height()
        p = QPainter(self.viewport())
        for r in rows:
            if self.model() is self._group_model and self._group_model.is_header(r):
                continue
            y = self.rowViewportPosition(r)
            h = self.rowHeight(r)
            if h > 0 and -h < y < vp_h:
                p.fillRect(x, y, w, h, self._accent)
        p.end()

    def startDrag(self, actions):  # noqa: N802
        uuids = self.selected_uuids()
        if not uuids:
            return
        mime = QMimeData()
        mime.setData(UUID_MIME, " ".join(uuids).encode())
        mime.setText(t("list.sep").join(uuids))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    # --- API ---------------------------------------------------

    def set_group_key(self, key: str) -> None:
        group = _GROUP_KEYS.get(key)
        self._proxy.set_group_key(group)
        want_grouped = group is not None
        if want_grouped:
            self._group_model.set_group_key(key)
        if want_grouped != self._grouped:
            self._grouped = want_grouped
            self.setModel(self._group_model if want_grouped else self._proxy)
            self._connect_selection()
        if want_grouped:
            self._apply_group_spans()

    def _connect_selection(self) -> None:
        self.selectionModel().selectionChanged.connect(self._on_selection)

    def _apply_group_spans(self) -> None:
        if self.model() is not self._group_model:
            return
        cols = self._group_model.columnCount()
        for r in range(self._group_model.rowCount()):
            if self._group_model.is_header(r):
                self.setSpan(r, 0, 1, cols)

    def _map_to_flat(self, index):
        """Map a view index (through whatever proxies) to a source-model index."""
        m = index.model()
        idx = index
        from PyQt6.QtCore import QAbstractProxyModel

        while isinstance(m, QAbstractProxyModel):
            idx = m.mapToSource(idx)
            m = idx.model()
        return idx

    def _selected_flat_rows(self):
        seen = set()
        for i in self.selectionModel().selectedRows():
            src = self._map_to_flat(i)
            if src.isValid() and src.row() not in seen:
                seen.add(src.row())
                yield src

    def selected_uuids(self) -> list[str]:
        return [
            u for src in self._selected_flat_rows()
            if (u := self._model.data(src, UUID_ROLE))
        ]

    def current_task(self) -> dict | None:
        src = self._map_to_flat(self.currentIndex())
        return self._model.data(src, TASK_ROLE) if src.isValid() else None

    def selected_tasks(self) -> list[dict]:
        return [
            task for src in self._selected_flat_rows()
            if (task := self._model.data(src, TASK_ROLE))
        ]

    def _timer_shortcut(self, start: bool) -> None:
        uuids = self.selected_uuids()
        if uuids:
            self.startStopRequested.emit(uuids[0], start)

    def _delete_shortcut(self) -> None:
        uuids = self.selected_uuids()
        if uuids:
            self.deleteRequested.emit(uuids)  # _delete() runs the confirm dialog

    def _done_shortcut(self) -> None:
        uuids = self.selected_uuids()
        if uuids:
            self.doneRequested.emit(uuids)

    def _open_detail_shortcut(self) -> None:
        task = self.current_task()
        if task:
            self.taskActivated.emit(task)

    def _on_click(self, index) -> None:
        if self.model() is self._group_model and index.data(GROUP_HEADER_ROLE):
            self._group_model.toggle(index.data(GROUP_KEY_ROLE))
            self._apply_group_spans()

    # --- events -----------------------------------------------

    def _on_double(self, index) -> None:
        src = self._map_to_flat(index)
        task = self._model.data(src, TASK_ROLE) if src.isValid() else None
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
        act_done = menu.addAction(t("table.menu.done", n=n))
        act_del = menu.addAction(t("table.menu.delete", n=n))
        act_del.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        act_dup = menu.addAction(t("table.menu.duplicate", n=n))
        menu.addSeparator()
        act_bulk = menu.addAction(t("table.menu.bulk_edit", n=n))
        act_append = menu.addAction(t("table.menu.append"))
        act_prepend = menu.addAction(t("table.menu.prepend"))
        act_annotate = menu.addAction(t("table.menu.annotate"))
        menu.addSeparator()
        act_start = menu.addAction(t("table.menu.start"))
        act_start.setShortcut(QKeySequence("Ctrl+S"))
        act_stop = menu.addAction(t("table.menu.stop"))
        act_stop.setShortcut(QKeySequence("Ctrl+Shift+S"))
        for _a in (act_del, act_start, act_stop):
            _a.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)  # display only
        act_purge = None
        if deleted:
            menu.addSeparator()
            act_purge = menu.addAction(t("table.menu.purge", n=len(deleted)))

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
        elif chosen == act_annotate:
            self.annotateRequested.emit(uuids)
        elif chosen == act_start:
            self.startStopRequested.emit(uuids[0], True)
        elif chosen == act_stop:
            self.startStopRequested.emit(uuids[0], False)
        elif act_purge is not None and chosen == act_purge:
            self.purgeRequested.emit(deleted)
