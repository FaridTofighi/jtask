"""QAbstractTableModel over the task dicts produced by ``jtask.reports``."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont

from jtask import jalali
from jtask.rtl import bidi_isolate, en_digits

from ..theme import palette
from .column_spec import COLUMNS, Column

_UUID_ROLE = Qt.ItemDataRole.UserRole + 1
_TASK_ROLE = Qt.ItemDataRole.UserRole + 2
_STATE_ROLE = Qt.ItemDataRole.UserRole + 3

_INDICATOR_ICON = {"annotations": "annotation", "recur": "recur", "depends": "depends"}
# hyphen-separated / colon-separated tokens that bidi must not reorder
_STRUCTURED_KEYS = frozenset({"due", "scheduled", "wait", "until", "start", "entry", "end"})


def _mix(a: str, b: str, t: float) -> str:
    """Blend hex colour *a* toward *b* by fraction *t* (0..1)."""
    ai = [int(a.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    bi = [int(b.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ai, bi, strict=True))


class TaskTableModel(QAbstractTableModel):
    def __init__(self, theme_name: str = "dark", persian_digits: bool = True,
                 due_soon_days: int = 3) -> None:
        super().__init__()
        self._tasks: list[dict] = []
        self._columns: list[Column] = [c for c in COLUMNS if c.default_visible]
        self._persian_digits = persian_digits
        self._due_soon = due_soon_days
        self._theme = theme_name
        self._apply_theme(theme_name)

    # --- configuration ------------------------------------------------

    def _apply_theme(self, theme_name: str) -> None:
        self._pal = palette(theme_name)
        bg = self._pal["bg"]
        # row tints: a wash of the state colour over the base background
        _strength = {"overdue": 0.20, "blocked": 0.16, "due_soon": 0.14, "waiting": 0.10}
        self._tint = {
            state: QColor(_mix(bg, self._pal[state], t))
            for state, t in _strength.items()
        }

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self._apply_theme(theme_name)
        self._emit_all_changed()

    def set_persian_digits(self, value: bool) -> None:
        self._persian_digits = value
        self._emit_all_changed()

    def set_due_soon_days(self, days: int) -> None:
        self._due_soon = days
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
        if orientation != Qt.Orientation.Horizontal:
            return None
        col = self._columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return col.header
        if role == Qt.ItemDataRole.ToolTipRole:
            from .column_spec import INDICATOR_TOOLTIP

            return INDICATOR_TOOLTIP.get(col.key, col.header)
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        col = self._columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(task, col)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._decoration(task, col)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            flag = Qt.AlignmentFlag.AlignVCenter | (
                Qt.AlignmentFlag.AlignHCenter if col.indicator
                else Qt.AlignmentFlag.AlignRight
            )
            return int(flag)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(task, col)
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background(task)
        if role == Qt.ItemDataRole.FontRole:
            return self._font(task, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            return task.get("description")
        if role == _UUID_ROLE:
            return task.get("uuid")
        if role == _TASK_ROLE:
            return task
        if role == _STATE_ROLE:
            return self._row_state(task)
        return None

    # --- rendering helpers --------------------------------------

    def _display(self, task: dict, col: Column) -> str:
        if col.indicator:
            return ""
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
        digits = en_digits(text) if (col.is_id or not self._persian_digits) \
            else jalali.to_persian_digits(text)
        # dates, ids and (possibly signed) numbers are structured tokens: keep
        # them atomic so bidi never floats a '-' or a separator to the wrong end.
        if text and (col.is_id or col.numeric or col.key in _STRUCTURED_KEYS):
            return bidi_isolate(digits)
        return digits

    def _decoration(self, task: dict, col: Column):
        if not col.indicator:
            return None
        present = bool(task.get(col.key))
        if not present:
            return None
        from ..icons import icon

        state = self._row_state(task)
        role = state if state in ("overdue", "blocked", "waiting") else "text_muted"
        return icon(_INDICATOR_ICON.get(col.key, "annotation"), role)

    def _due_dt(self, task: dict) -> datetime.datetime | None:
        raw = task.get("due_gregorian")
        m = jalali._TW_TS_RE.match(raw or "")
        if not m:
            return None
        y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
        return datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)

    def _row_state(self, task: dict) -> str | None:
        status = task.get("status")
        if status == "completed":
            return "completed"
        if status == "waiting":
            return "waiting"
        if task.get("depends") and status == "pending":
            return "blocked"
        due = self._due_dt(task)
        if due and status == "pending":
            now = datetime.datetime.now(datetime.timezone.utc)
            if due < now:
                return "overdue"
            if due - now <= datetime.timedelta(days=self._due_soon):
                return "due_soon"
        return None

    def _foreground(self, task: dict, col: Column) -> QColor | None:
        state = self._row_state(task)
        if state == "completed":
            return QColor(self._pal["completed"])
        if state == "waiting":
            return QColor(self._pal["waiting"])
        if col.key == "due" and state in ("overdue", "due_soon"):
            return QColor(self._pal[state])
        if col.key == "description" and state == "blocked":
            return QColor(self._pal["blocked"])
        return None

    def _background(self, task: dict) -> QColor | None:
        state = self._row_state(task)
        return self._tint.get(state) if state in self._tint else None

    def _font(self, task: dict, col: Column) -> QFont | None:
        f = QFont()
        touched = False
        if task.get("status") == "completed" and col.key == "description":
            f.setStrikeOut(True)
            touched = True
        if col.key == "description":
            f.setWeight(QFont.Weight.DemiBold)
            touched = True
        return f if touched else None

    def _emit_all_changed(self) -> None:
        if self._tasks:
            top = self.index(0, 0)
            bottom = self.index(len(self._tasks) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top, bottom)


UUID_ROLE = _UUID_ROLE
TASK_ROLE = _TASK_ROLE
STATE_ROLE = _STATE_ROLE
