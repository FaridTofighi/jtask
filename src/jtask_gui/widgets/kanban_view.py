"""The Kanban board — a third task view (alongside the table and Reports).

Grouping is selectable (status / priority / project); every drag between
columns is one real Taskwarrior write, emitted as ``taskMoved`` and applied by
``MainWindow`` through the normal ``_write`` / undo path. No invented state —
the ``status`` board's "Doing" column is ``+ACTIVE`` (the ``start`` attribute).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as tok
from ..i18n import t
from .kanban_card import UUID_MIME, KanbanCard
from .segmented import SegmentedControl

# grouping key -> ordered list of (column_id, i18n label key)
_STATUS_COLS = [("todo", "kanban.col.todo"), ("doing", "kanban.col.doing"),
                ("done", "kanban.col.done"), ("waiting", "kanban.col.waiting")]
_PRIORITY_COLS = [("", "col.priority.none"), ("L", "col.priority.l"),
                  ("M", "col.priority.m"), ("H", "col.priority.h")]

_DROPPABLE = {  # columns that accept drops, per grouping
    "status": {"todo", "doing", "done"},
    "priority": {"", "L", "M", "H"},
    "project": None,  # any
}


def _bucket(task: dict, grouping: str) -> str:
    if grouping == "priority":
        return task.get("priority", "") or ""
    if grouping == "project":
        return task.get("project", "") or ""
    st = task.get("status")
    if st == "completed":
        return "done"
    if st == "waiting":
        return "waiting"
    if task.get("start"):          # a running timer == the "Doing" column
        return "doing"
    return "todo"


class _Column(QFrame):
    dropped = pyqtSignal(str, str)  # uuid, this column's id

    def __init__(self, col_id: str, title: str, droppable: bool, parent=None) -> None:
        super().__init__(parent)
        self.col_id = col_id
        self._droppable = droppable
        self.setObjectName("KanbanColumn")
        self.setAcceptDrops(droppable)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_6)
        self._title = QLabel(title)
        self._title.setObjectName("KanbanColTitle")
        lay.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("KanbanColScroll")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self._cards = QVBoxLayout(body)
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(tok.SP_6)
        self._cards.addStretch(1)
        self._scroll.setWidget(body)
        lay.addWidget(self._scroll, 1)
        self._base_title = title

    def add_card(self, card: KanbanCard) -> None:
        self._cards.insertWidget(self._cards.count() - 1, card)

    def clear(self) -> None:
        while self._cards.count() > 1:
            w = self._cards.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def set_count(self, n: int) -> None:
        self._title.setText(f"{self._base_title}  ·  {n}")

    def dragEnterEvent(self, event):  # noqa: N802
        if self._droppable and event.mimeData().hasFormat(UUID_MIME):
            event.acceptProposedAction()
            self.setProperty("dropTarget", True)
            self._restyle()

    def dragLeaveEvent(self, event):  # noqa: N802
        self.setProperty("dropTarget", False)
        self._restyle()

    def dropEvent(self, event):  # noqa: N802
        self.setProperty("dropTarget", False)
        self._restyle()
        if self._droppable and event.mimeData().hasFormat(UUID_MIME):
            uuid = bytes(event.mimeData().data(UUID_MIME)).decode().strip()
            if uuid:
                self.dropped.emit(uuid, self.col_id)
                event.acceptProposedAction()

    def _restyle(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


class KanbanView(QWidget):
    # (task_dict, grouping, target_column_id)
    taskMoved = pyqtSignal(dict, str, str)
    taskActivated = pyqtSignal(str)
    starToggled = pyqtSignal(str, bool)

    def __init__(self, theme_name: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("KanbanView")
        self._theme = theme_name
        self._tasks: list[dict] = []
        self._grouping = "status"

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_PANEL)
        root.setSpacing(tok.SP_10)

        bar = QHBoxLayout()
        bar.addWidget(QLabel(t("kanban.group_by")))
        self._seg = SegmentedControl([
            (t("kanban.by.status"), "status"),
            (t("kanban.by.priority"), "priority"),
            (t("kanban.by.project"), "project"),
        ])
        self._seg.changed.connect(self._on_grouping)
        bar.addWidget(self._seg)
        bar.addStretch(1)
        root.addLayout(bar)

        self._hscroll = QScrollArea()
        self._hscroll.setWidgetResizable(True)
        self._hscroll.setObjectName("KanbanBoard")
        self._board = QWidget()
        self._cols_lay = QHBoxLayout(self._board)
        self._cols_lay.setContentsMargins(0, 0, 0, 0)
        self._cols_lay.setSpacing(tok.SP_10)
        self._hscroll.setWidget(self._board)
        root.addWidget(self._hscroll, 1)

        self._columns: list[_Column] = []

    # --- API -------------------------------------------------

    def set_theme(self, name: str) -> None:
        self._theme = name
        self._rebuild()

    def set_tasks(self, tasks: list[dict]) -> None:
        self._tasks = list(tasks)
        self._rebuild()

    def grouping(self) -> str:
        return self._grouping

    # --- internals ------------------------------------------

    def _on_grouping(self, value: object) -> None:
        self._grouping = str(value)
        self._rebuild()

    def _column_defs(self) -> list[tuple[str, str]]:
        if self._grouping == "status":
            return [(cid, t(k)) for cid, k in _STATUS_COLS]
        if self._grouping == "priority":
            return [(cid, t(k)) for cid, k in _PRIORITY_COLS]
        projects = sorted({tk.get("project", "") or "" for tk in self._tasks})
        return [(p, p or t("group.value.no_project")) for p in projects] or \
               [("", t("group.value.no_project"))]

    def _rebuild(self) -> None:
        while self._cols_lay.count():
            w = self._cols_lay.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._columns = []

        droppable_set = _DROPPABLE.get(self._grouping)
        buckets: dict[str, list[dict]] = {}
        for tk in self._tasks:
            buckets.setdefault(_bucket(tk, self._grouping), []).append(tk)

        for cid, title in self._column_defs():
            droppable = droppable_set is None or cid in droppable_set
            col = _Column(cid, title, droppable)
            col.dropped.connect(self._on_dropped)
            items = buckets.get(cid, [])
            for tk in items:
                card = KanbanCard(tk, self._theme)
                card.activated.connect(self.taskActivated)
                card.starToggled.connect(self.starToggled)
                col.add_card(card)
            col.set_count(len(items))
            self._cols_lay.addWidget(col, 1)
            self._columns.append(col)
        self._cols_lay.addStretch(0)

    def _on_dropped(self, uuid: str, col_id: str) -> None:
        task = next((tk for tk in self._tasks if tk.get("uuid") == uuid), None)
        if task is not None and _bucket(task, self._grouping) != col_id:
            self.taskMoved.emit(task, self._grouping, col_id)
