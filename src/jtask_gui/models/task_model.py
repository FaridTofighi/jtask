"""QAbstractTableModel over the task dicts produced by ``jtask.reports``."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont

from jtask import jalali
from jtask.rtl import en_digits

from ..theme import palette
from .column_spec import COLUMNS, Column

_UUID_ROLE = Qt.ItemDataRole.UserRole + 1
_TASK_ROLE = Qt.ItemDataRole.UserRole + 2


class TaskTableModel(QAbstractTableModel):
    def __init__(self, theme_name: str = "شب", persian_digits: bool = True,
                 due_soon_days: int = 3) -> None:
        super().__init__()
        self._tasks: list[dict] = []
        self._columns: list[Column] = [c for c in COLUMNS if c.default_visible]
        self._pal = palette(theme_name)
        self._persian_digits = persian_digits
        self._due_soon = due_soon_days

    # --- configuration ------------------------------------------------

    def set_theme(self, theme_name: str) -> None:
        self._pal = palette(theme_name)
        self._emit_all_changed()

    def set_persian_digits(self, value: bool) -> None:
        self._persian_digits = value
        self._emit_all_changed()

    def set_columns(self, keys: list[str]) -> None:
        from .column_spec import BY_KEY

        self.beginResetModel()
        self._columns = [BY_KEY[k] for k in keys if k in BY_KEY]
        self.endResetModel()

    def visible_columns(self) -> list[str]:
        return [c.key for c in self._columns]

    # --- data -------------------------------------------------------

    def set_tasks(self, tasks: list[dict]) -> None:
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()

    def task_at(self, row: int) -> dict | None:
        return self._tasks[row] if 0 <= row < len(self._tasks) else None

    # --- Qt model interface ---------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._columns[section].header
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        col = self._columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(task, col)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(task, col)
        if role == Qt.ItemDataRole.FontRole:
            return self._font(task)
        if role == _UUID_ROLE:
            return task.get("uuid")
        if role == _TASK_ROLE:
            return task
        return None

    # --- rendering helpers --------------------------------------

    def _display(self, task: dict, col: Column) -> str:
        if col.formatter is not None:
            text = col.formatter(task)
        else:
            value = task.get(col.key, "")
            text = "" if value is None else str(value)
        if col.numeric and text:
            try:
                text = f"{float(text):.1f}"
            except ValueError:
                pass
        if col.is_id or not self._persian_digits:
            return en_digits(text)
        return jalali.to_persian_digits(text)

    def _due_dt(self, task: dict) -> datetime.datetime | None:
        raw = task.get("due_gregorian")
        m = jalali._TW_TS_RE.match(raw or "")
        if not m:
            return None
        y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
        return datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)

    def _foreground(self, task: dict, col: Column) -> QColor | None:
        status = task.get("status")
        if status == "completed":
            return QColor(self._pal["completed"])
        if status == "waiting":
            return QColor(self._pal["waiting"])
        if task.get("depends") and status == "pending":
            if col.key in ("description", "due"):
                return QColor(self._pal["blocked"])
        if col.key == "due":
            due = self._due_dt(task)
            if due and status == "pending":
                now = datetime.datetime.now(datetime.timezone.utc)
                if due < now:
                    return QColor(self._pal["overdue"])
                if due - now <= datetime.timedelta(days=self._due_soon):
                    return QColor(self._pal["due_soon"])
        return None

    def _font(self, task: dict) -> QFont | None:
        if task.get("status") == "completed":
            f = QFont()
            f.setStrikeOut(True)
            return f
        return None

    def _emit_all_changed(self) -> None:
        if self._tasks:
            top = self.index(0, 0)
            bottom = self.index(len(self._tasks) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top, bottom)


UUID_ROLE = _UUID_ROLE
TASK_ROLE = _TASK_ROLE
