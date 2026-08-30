"""Interactive Jalali calendar report — month grid + click-a-day task list.

Reuses ``JalaliMonthGrid`` (the same engine the date picker uses) with a
task-density cell factory; clicking a day shows that day's due/scheduled tasks
in the side list.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali, reports

from .. import fmt, icons
from ..calendar_system import active
from ..i18n import t
from ..workers import submit
from .jalali_calendar import DayCellContext, JalaliMonthGrid
from .task_table import UUID_MIME


class _DayCell(QFrame):
    clicked = pyqtSignal(object)              # (year, month, day)
    tasksDropped = pyqtSignal(list, object)   # (uuids, (y, m, d))

    def __init__(self, ctx: DayCellContext, count: int, overdue: bool, pal: dict) -> None:
        super().__init__()
        self._key = (ctx.year, ctx.month, ctx.day)
        self.setObjectName("DayCell")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(3)

        num = QLabel(fmt.digits(str(ctx.day)))
        num.setAlignment(Qt.AlignmentFlag.AlignRight)
        if ctx.is_today:
            num.setStyleSheet(f"color:{pal['primary']}; font-weight:700;")
        lay.addWidget(num)

        if count:
            colour = pal["overdue"] if overdue else pal["primary"]
            dot = QLabel(fmt.digits(t("calendar.n_tasks", count=count)))
            dot.setStyleSheet(f"color:{colour}; font-size:11px;")
            dot.setAlignment(Qt.AlignmentFlag.AlignRight)
            lay.addWidget(dot)
            self.setStyleSheet(
                f"QFrame#DayCell {{ background:{colour}22; border-radius:6px; }}"
            )
        lay.addStretch(1)

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit(self._key)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(UUID_MIME):
            event.acceptProposedAction()
            self.setStyleSheet("QFrame#DayCell { border: 2px solid palette(highlight); }")

    def dragLeaveEvent(self, event):  # noqa: N802
        self.setStyleSheet("")

    def dropEvent(self, event):  # noqa: N802
        self.setStyleSheet("")
        uuids = bytes(event.mimeData().data(UUID_MIME)).decode().split()
        if uuids:
            self.tasksDropped.emit(uuids, self._key)
            event.acceptProposedAction()


class CalendarReport(QWidget):
    taskRescheduled = pyqtSignal(list, str)  # (uuids, gregorian YYYY-MM-DD)

    def __init__(self, theme_name: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self._theme = theme_name
        self._filter: list[str] = []
        self._data: dict = {"days": {}}
        self._cal = active()
        today = self._cal.today()
        self._year, self._month = today.year, today.month
        self._gen = 0

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        self._grid = JalaliMonthGrid(self._year, self._month)
        self._grid.monthChanged.connect(self._on_month)
        self._grid.set_cell_factory(self._make_cell)
        root.addWidget(self._grid, 3)

        side = QVBoxLayout()
        self._day_title = QLabel(t("calendar.pick_day"))
        self._day_title.setObjectName("H2")
        side.addWidget(self._day_title)
        self._day_list = QListWidget()
        side.addWidget(self._day_list, 1)
        wrap = QWidget()
        wrap.setLayout(side)
        wrap.setMinimumWidth(240)
        root.addWidget(wrap, 2)

    # --- API --------------------------------------------------

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self._grid.refresh()

    def set_filter(self, tokens: list[str]) -> None:
        self._filter = tokens
        self.reload()

    def reload(self) -> None:
        y, m = self._year, self._month
        self._gen += 1
        gen = self._gen

        def apply(data):
            if gen == self._gen:
                self._on_data(data)

        greg = self._cal.id == "gregorian"
        ws = self._cal.week_start_pyweekday()
        submit(
            lambda: reports.report_calendar(
                y, m, self._filter or None, gregorian=greg, week_start=ws
            ),
            apply,
        )

    # --- internals ------------------------------------------

    def _on_month(self, year: int, month: int) -> None:
        self._year, self._month = year, month
        self.reload()

    def _on_data(self, data: dict) -> None:
        self._data = data
        self._grid.refresh()

    def _make_cell(self, ctx: DayCellContext):
        from ..theme import palette

        pal = palette(self._theme)
        tasks = self._data.get("days", {}).get((ctx.year, ctx.month, ctx.day), [])
        overdue = any(self._is_overdue(t) for t in tasks)
        cell = _DayCell(ctx, len(tasks), overdue, pal)
        cell.clicked.connect(self._show_day)
        cell.tasksDropped.connect(self._on_drop)
        return cell

    def _on_drop(self, uuids: list[str], key) -> None:
        y, m, d = key
        greg = self._cal.to_gregorian_date(y, m, d).strftime("%Y-%m-%d")
        self.taskRescheduled.emit(uuids, greg)

    @staticmethod
    def _is_overdue(task: dict) -> bool:
        import datetime

        m = jalali._TW_TS_RE.match(task.get("due_gregorian", "") or "")
        if not m:
            return False
        y, mo, d, hh, mi, ss = (int(x) for x in m.groups())
        return datetime.datetime(y, mo, d, hh, mi, ss,
                                 tzinfo=datetime.timezone.utc) < datetime.datetime.now(
            datetime.timezone.utc) and task.get("status") == "pending"

    def _show_day(self, key) -> None:
        y, m, d = key
        self._day_title.setText(
            fmt.digits(f"{d} {self._cal.month_names()[m - 1]} {y}")
        )
        self._day_list.clear()
        for task in self._data.get("days", {}).get(key, []):
            item = QListWidgetItem(f"{task.get('description', '')}")
            over = self._is_overdue(task)
            item.setIcon(icons.icon(
                "overdue" if over else "today",
                "overdue" if over else "text_muted",
            ))
            self._day_list.addItem(item)
        if self._day_list.count() == 0:
            self._day_list.addItem(QListWidgetItem(t("calendar.no_tasks_day")))
