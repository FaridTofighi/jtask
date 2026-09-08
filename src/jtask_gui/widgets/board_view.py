"""A board — a named, ordered set of filter-defined columns.

Every column is a raw Taskwarrior filter (`boards.Column.filter`); membership is
just ``reports.report_list(filter + extra)`` run per column off the UI thread.
Every drag between columns emits ``boardDrop(task, drop_config)`` which
``MainWindow`` compiles (``boards.compile_drop``) into one write through the
normal ``_write`` / undo path. No board-specific engine behaviour.
"""

from __future__ import annotations

import shlex

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from jtask import reports

from .. import icons
from .. import tokens as tok
from ..boards import (
    SORT_LABEL_KEYS,
    SORT_ORDERS,
    Board,
    drop_label,
    is_review_capable,
    normalize_sort,
    sort_rows,
)
from ..i18n import t
from ..workers import submit
from .board_card import UUID_MIME, BoardCard


class _Column(QFrame):
    dropped = pyqtSignal(str, int)     # uuid, column index
    triageRequested = pyqtSignal(int)  # column index — "process one by one"
    sortChanged = pyqtSignal(int, str) # column index, sort order

    def __init__(self, index: int, title: str, subtitle: str, droppable: bool,
                 color: str | None = None, sort: str = "", parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self._droppable = droppable
        self._uuids: set[str] = set()
        self.setObjectName("BoardColumn")
        self.setAcceptDrops(droppable)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_6)

        # accent strip — a curated theme role (boards.COLUMN_ACCENT_ROLES) drawn
        # via QSS tokens, so it re-colours itself on a theme switch. Hidden when
        # the column has no colour, leaving the neutral appearance untouched.
        self._accent = QFrame()
        self._accent.setObjectName("BoardColAccent")
        self._accent.setProperty("accent", color or "")
        self._accent.setVisible(bool(color))
        lay.addWidget(self._accent)

        head = QVBoxLayout()
        head.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(title)
        self._title.setObjectName("BoardColTitle")
        title_row.addWidget(self._title, 1)

        self._sort_btn = QToolButton()
        self._sort_btn.setObjectName("BoardColSort")
        self._sort_btn.setIcon(icons.icon("sort", "text_muted"))
        self._sort_btn.setToolTip(t("board.sort"))
        self._sort_btn.setAutoRaise(True)
        self._sort_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self._sort_btn)
        group = QActionGroup(menu)
        group.setExclusive(True)
        current = normalize_sort(sort)
        self._sort_actions: dict[str, object] = {}
        for order in SORT_ORDERS:
            act = menu.addAction(t(SORT_LABEL_KEYS[order]))
            act.setCheckable(True)
            act.setChecked(order == current)
            act.triggered.connect(lambda _c=False, o=order: self.sortChanged.emit(self.index, o))
            group.addAction(act)
            self._sort_actions[order] = act
        self._sort_btn.setMenu(menu)
        title_row.addWidget(self._sort_btn, 0)

        self._triage_btn = QToolButton()
        self._triage_btn.setObjectName("BoardColTriage")
        self._triage_btn.setIcon(icons.icon("triage", "text_muted"))
        self._triage_btn.setToolTip(t("triage.start.tip"))
        self._triage_btn.setAutoRaise(True)
        self._triage_btn.clicked.connect(lambda: self.triageRequested.emit(self.index))
        title_row.addWidget(self._triage_btn, 0)
        head.addLayout(title_row)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("BoardColSub")
            head.addWidget(sub)
        lay.addLayout(head)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("BoardColScroll")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self._cards = QVBoxLayout(body)
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(tok.SP_6)
        self._cards.addStretch(1)
        self._scroll.setWidget(body)
        lay.addWidget(self._scroll, 1)
        self._base_title = title

    def add_card(self, card: BoardCard) -> None:
        self._cards.insertWidget(self._cards.count() - 1, card)
        if card.uuid:
            self._uuids.add(card.uuid)

    def clear_cards(self) -> None:
        self._uuids.clear()
        while self._cards.count() > 1:            # keep the trailing stretch
            item = self._cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_sort_checked(self, order: str) -> None:
        act = self._sort_actions.get(normalize_sort(order))
        if act is not None:
            act.setChecked(True)

    def set_count(self, n: int) -> None:
        self._title.setText(f"{self._base_title}  ·  {n}")

    def has(self, uuid: str) -> bool:
        return uuid in self._uuids

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
            if uuid and not self.has(uuid):
                self.dropped.emit(uuid, self.index)
                event.acceptProposedAction()

    def _restyle(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


class BoardView(QWidget):
    boardDrop = pyqtSignal(dict, dict)   # (task, drop_config)
    taskActivated = pyqtSignal(str)
    starToggled = pyqtSignal(str, bool)
    triageRequested = pyqtSignal(int)    # column index
    columnSortChanged = pyqtSignal(int, str)  # column index, sort order
    reviewRequested = pyqtSignal()       # GTD board header — open the review pass

    def __init__(self, theme_name: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BoardView")
        self._theme = theme_name
        self._board: Board | None = None
        self._extra: list[str] = []
        self._col_tasks: list[list[dict]] = []
        self._gen = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_PANEL)
        root.setSpacing(tok.SP_10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._heading = QLabel("")
        self._heading.setObjectName("H2")
        header.addWidget(self._heading)
        header.addStretch(1)
        self._review_btn = QPushButton(t("action.review"))
        self._review_btn.setObjectName("BoardReviewButton")
        self._review_btn.setToolTip(t("action.review.tip"))
        self._review_btn.clicked.connect(self.reviewRequested)
        self._review_btn.hide()
        header.addWidget(self._review_btn, 0)
        root.addLayout(header)

        self._hscroll = QScrollArea()
        self._hscroll.setWidgetResizable(True)
        self._hscroll.setObjectName("Board")
        self._surface = QWidget()
        self._cols_lay = QHBoxLayout(self._surface)
        self._cols_lay.setContentsMargins(0, 0, 0, 0)
        self._cols_lay.setSpacing(tok.SP_10)
        self._hscroll.setWidget(self._surface)
        root.addWidget(self._hscroll, 1)

        self._empty = QLabel(t("board.empty"))
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.hide()
        root.addWidget(self._empty)

        self._columns: list[_Column] = []

    # --- API -------------------------------------------------

    def set_theme(self, name: str) -> None:
        self._theme = name
        self.reload()

    def set_extra_filter(self, tokens: list[str]) -> None:
        self._extra = list(tokens or [])

    def set_board(self, board: Board | None) -> None:
        self._board = board
        self.reload()

    def current_board(self) -> Board | None:
        return self._board

    def reload(self) -> None:
        board = self._board
        for c in self._columns:
            c.setParent(None)
            c.deleteLater()
        self._columns = []
        while self._cols_lay.count():
            self._cols_lay.takeAt(0)
        review = is_review_capable(board)
        self._review_btn.setVisible(review)
        if review:
            self._review_btn.setIcon(icons.icon("review"))
        if board is None or not board.columns:
            self._empty.setVisible(True)
            self._hscroll.setVisible(False)
            self._heading.clear()
            return
        self._empty.setVisible(False)
        self._hscroll.setVisible(True)
        self._heading.setText(board.name)

        for i, col in enumerate(board.columns):
            droppable = col.drop.get("type", "none") != "none"
            column = _Column(i, col.title, drop_label(col.drop), droppable,
                             col.color, col.sort)
            column.dropped.connect(self._on_dropped)
            column.triageRequested.connect(self.triageRequested)
            column.sortChanged.connect(self._on_sort_changed)
            self._cols_lay.addWidget(column, 1)
            self._columns.append(column)
        self._cols_lay.addStretch(0)

        self._gen += 1
        gen = self._gen
        self._col_tasks = [[] for _ in board.columns]
        for i, col in enumerate(board.columns):
            flt = self._column_filter(col.filter)
            submit(
                (lambda f=flt: reports.report_list(f)),
                (lambda rows, idx=i: self._fill_column(gen, idx, rows)),
                lambda _e: None,
            )

    def _column_filter(self, raw: str) -> list[str]:
        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()
        return [*tokens, *self._extra]

    def _fill_column(self, gen: int, idx: int, rows: list[dict]) -> None:
        if gen != self._gen or idx >= len(self._columns):
            return
        order = self._board.columns[idx].sort if self._board else None
        self._col_tasks[idx] = sort_rows(rows, order or "")
        self._render_cards(idx)

    def _render_cards(self, idx: int) -> None:
        col = self._columns[idx]
        col.clear_cards()
        rows = self._col_tasks[idx]
        for tk in rows:
            card = BoardCard(tk, self._theme)
            card.activated.connect(self.taskActivated)
            card.starToggled.connect(self.starToggled)
            col.add_card(card)
        col.set_count(len(rows))

    def _on_sort_changed(self, idx: int, order: str) -> None:
        """Live re-sort of the column's *current* cards — no board reload."""
        if self._board is None or not 0 <= idx < len(self._board.columns):
            return
        self._board.columns[idx].sort = order
        self._col_tasks[idx] = sort_rows(self._col_tasks[idx], order)
        self._render_cards(idx)
        self.columnSortChanged.emit(idx, order)

    def _on_dropped(self, uuid: str, col_index: int) -> None:
        if self._board is None or col_index >= len(self._board.columns):
            return
        task = None
        for rows in self._col_tasks:
            for tk in rows:
                if tk.get("uuid") == uuid:
                    task = tk
                    break
        if task is None:
            task = {"uuid": uuid}
        self.boardDrop.emit(task, self._board.columns[col_index].drop)
