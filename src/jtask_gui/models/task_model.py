"""QAbstractTableModel over the task dicts produced by ``jtask.reports``."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap

from jtask import jalali
from jtask.rtl import auto_isolate, bidi_isolate, en_digits, first_strong_dir

from ..theme import palette
from .column_spec import COLUMNS, Column

_UUID_ROLE = Qt.ItemDataRole.UserRole + 1
_TASK_ROLE = Qt.ItemDataRole.UserRole + 2
_STATE_ROLE = Qt.ItemDataRole.UserRole + 3

_INDICATOR_ICON = {"annotations": "annotation", "recur": "recur", "depends": "depends"}
# hyphen-separated / colon-separated tokens that bidi must not reorder
_STRUCTURED_KEYS = frozenset({"due", "scheduled", "wait", "until", "start", "entry", "end"})
# free-text columns that follow their *own* content direction, not the app's:
# "Meeting with Arash" reads LTR, "جلسه با آرش" reads RTL.
_AUTO_DIR_KEYS = frozenset({"description", "project"})


def _mix(a: str, b: str, t: float) -> str:
    """Blend hex colour *a* toward *b* by fraction *t* (0..1)."""
    ai = [int(a.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    bi = [int(b.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ai, bi, strict=True))


class TaskTableModel(QAbstractTableModel):
    # (uuid, field, value) — an inline cell edit; MainWindow turns it into a
    # `task <uuid> modify <field>:<value>` write. The model never writes.
    cellEdited = pyqtSignal(str, str, str)
    # (uuid, starred) — the ⭐ column was clicked
    starToggled = pyqtSignal(str, bool)

    #: columns that accept an inline editor (delegates in widgets/table_delegates)
    EDITABLE = ("project", "priority", "due")

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
        # row tints: a wash of the state colour over the *row* surface (rows
        # paint on `surface`, not the window `bg` — mixing against `bg` made
        # the wash vanish).
        base = self._pal["surface"]
        _strength = {"overdue": 0.22, "blocked": 0.16, "due_soon": 0.16, "waiting": 0.10}
        self._tint = {
            state: QColor(_mix(base, self._pal[state], t))
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
        if role == Qt.ItemDataRole.EditRole:
            if col.key == "due":
                return task.get("due_gregorian", "")  # raw TW timestamp
            return task.get(col.key, "") or ""
        if role == Qt.ItemDataRole.DecorationRole:
            return self._decoration(task, col)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | self._halign(task, col))
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

    def flags(self, index: QModelIndex):
        base = super().flags(index)
        if index.isValid() and self._columns[index.column()].key in self.EDITABLE:
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        col = self._columns[index.column()]
        if col.key not in self.EDITABLE:
            return False
        task = self._tasks[index.row()]
        uuid = task.get("uuid")
        new = "" if value is None else str(value).strip()
        current = task.get("due_gregorian", "") if col.key == "due" else (task.get(col.key) or "")
        if not uuid or new == current:
            return False
        self.cellEdited.emit(uuid, col.key, new)
        return True

    # --- rendering helpers --------------------------------------

    # ``AlignLeft`` / ``AlignRight`` are *direction-relative* unless
    # ``AlignAbsolute`` is set: in an RTL view Qt silently flips a bare
    # ``AlignRight`` to the visual left (``QStyle.visualAlignment``). The
    # content-direction columns below need a fixed *visual* edge — a Persian
    # description reads right whatever the UI language — so they pin it absolute.
    _ABS = Qt.AlignmentFlag.AlignAbsolute
    _LEFT = Qt.AlignmentFlag.AlignLeft | _ABS
    _RIGHT = Qt.AlignmentFlag.AlignRight | _ABS

    @classmethod
    def _leading(cls) -> Qt.AlignmentFlag:
        """The reading-start edge for the current app layout direction."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        rtl = app is not None and app.layoutDirection() == Qt.LayoutDirection.RightToLeft
        return cls._RIGHT if rtl else cls._LEFT

    def _halign(self, task: dict, col: Column) -> Qt.AlignmentFlag:
        if col.indicator:
            return Qt.AlignmentFlag.AlignHCenter
        if col.is_id or col.numeric:
            return Qt.AlignmentFlag.AlignRight        # trailing — numeric convention
        if col.key in _AUTO_DIR_KEYS:
            d = first_strong_dir(task.get(col.key) or "")
            if d == "ltr":
                return self._LEFT
            if d == "rtl":
                return self._RIGHT
        return self._leading()

    @staticmethod
    def _is_starred(task: dict) -> bool:
        return "starred" in (task.get("tags") or [])

    def _display(self, task: dict, col: Column) -> str:
        if col.indicator or col.star:
            return ""
        if col.formatter is not None:
            text = col.formatter(task)
        elif col.key in _STRUCTURED_KEYS and f"{col.key}_gregorian" in task:
            # Re-render the stored Gregorian/UTC value through the active
            # calendar system, ignoring reports.py's pre-formatted Jalali string.
            from ..calendar_system import active
            text = active().format_utc(task.get(f"{col.key}_gregorian") or "", "short")
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
        # free text follows its own first-strong direction, not the paragraph's
        if text and col.key in _AUTO_DIR_KEYS:
            return auto_isolate(digits)
        return digits

    _PRIORITY_DOT = {"H": "overdue", "M": "due_soon", "L": "text_muted"}

    def _decoration(self, task: dict, col: Column):
        if col.star:
            from ..icons import icon
            if self._is_starred(task):
                return icon("star", "due_soon").pixmap(15, 15)
            return icon("star_outline", "text_muted").pixmap(15, 15)
        if col.key == "priority":
            role = self._PRIORITY_DOT.get(task.get("priority", ""))
            if role is None:
                return None
            d = 8
            pm = QPixmap(d, d)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self._pal[role]))
            p.drawEllipse(0, 0, d, d)
            p.end()
            return pm
        if col.key != "indicators":
            return None
        marks = [m for m in ("annotations", "recur", "depends") if task.get(m)]
        if not marks:
            return None
        from ..icons import icon

        state = self._row_state(task)
        role = state if state in ("overdue", "blocked", "waiting") else "text_muted"
        px, gap = 15, 3
        pm = QPixmap((px + gap) * len(marks) - gap, px)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        for i, m in enumerate(marks):
            icon(_INDICATOR_ICON[m], role).paint(p, i * (px + gap), 0, px, px)
        p.end()
        return pm

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
        # secondary / derived columns read as muted so the description leads
        if col.key in ("urgency", "id"):
            return QColor(self._pal["text_muted"])
        if col.key == "priority":
            pr = task.get("priority", "")
            return QColor(self._pal[
                {"H": "overdue", "M": "due_soon"}.get(pr, "text_muted")
            ])
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
