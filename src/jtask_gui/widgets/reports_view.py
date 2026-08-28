"""Reports & Charts area — a report picker + the matching chart/table/calendar."""

from __future__ import annotations

import functools
import tempfile

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from jtask import reports

from .. import icons
from ..workers import submit
from .calendar_report import CalendarReport
from .charts.burndown_chart import BurndownChart
from .charts.history_chart import HistoryChart
from .charts.summary_view import SummaryView
from .table_reports import ProjectsReport, TagsReport

_REPORTS = [
    ("burndown", "نمودار سوختن", "reports"),
    ("ghistory", "گراف تاریخچه", "reports"),
    ("history", "تاریخچه", "reports"),
    ("summary", "خلاصهٔ پروژه‌ها", "projects"),
    ("calendar", "تقویم جلالی", "calendar"),
    ("projects", "گزارش پروژه‌ها", "project"),
    ("tags", "گزارش برچسب‌ها", "tag"),
]
_PERIODS = [("روزانه", "daily"), ("هفتگی", "weekly"), ("ماهانه", "monthly")]
_PERIOD_REPORTS = {"burndown", "ghistory", "history"}
_MPL_REPORTS = {"burndown", "ghistory", "history"}


class ReportsView(QWidget):
    filterRequested = pyqtSignal(list)  # user drilled into a project/tag

    def __init__(self, theme_name: str = "شب", parent=None) -> None:
        super().__init__(parent)
        self._theme = theme_name
        self._filter: list[str] = []
        self._period = "daily"
        self._active = "burndown"
        self._gen = 0  # guards against a stale async response overwriting a fresh one

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- report picker rail (right, RTL) ---
        self._rail = QListWidget()
        self._rail.setObjectName("Sidebar")
        self._rail.setFixedWidth(190)
        for key, label, glyph in _REPORTS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setData(Qt.ItemDataRole.UserRole + 5, glyph)
            self._rail.addItem(item)
        self._rail.currentRowChanged.connect(self._on_pick)

        # --- content ---
        content = QVBoxLayout()
        content.setContentsMargins(16, 12, 16, 16)
        content.setSpacing(10)

        bar = QHBoxLayout()
        self._title = QLabel("نمودار سوختن")
        self._title.setObjectName("H1")
        bar.addWidget(self._title, 1)

        self._period_combo = QComboBox()
        for label, key in _PERIODS:
            self._period_combo.addItem(label, key)
        self._period_combo.currentIndexChanged.connect(self._on_period)
        bar.addWidget(self._period_combo)

        self._hist_mode = QComboBox()
        self._hist_mode.addItem("انباشته", "ghistory")
        self._hist_mode.addItem("گروهی", "history")
        self._hist_mode.currentIndexChanged.connect(self._on_hist_mode)
        bar.addWidget(self._hist_mode)

        self._export_btn = QPushButton("خروجی PNG")
        self._export_btn.clicked.connect(self._export)
        bar.addWidget(self._export_btn)
        content.addLayout(bar)

        self._stack = QStackedWidget()
        self._burndown = BurndownChart(theme_name)
        self._history = HistoryChart(theme_name)
        self._summary = SummaryView(theme_name)
        self._calendar = CalendarReport(theme_name)
        self._projects = ProjectsReport()
        self._tags = TagsReport()
        for w in (self._burndown, self._history, self._summary, self._calendar,
                  self._projects, self._tags):
            self._stack.addWidget(w)
        self._projects.rowActivated.connect(self.filterRequested)
        self._tags.rowActivated.connect(self.filterRequested)
        content.addWidget(self._stack, 1)

        cwrap = QWidget()
        cwrap.setLayout(content)
        root.addWidget(cwrap, 1)
        root.addWidget(self._rail)

        self._widget_for = {
            "burndown": self._burndown, "ghistory": self._history,
            "history": self._history, "summary": self._summary,
            "calendar": self._calendar, "projects": self._projects,
            "tags": self._tags,
        }
        self._retint_rail()
        self._rail.setCurrentRow(0)

    # --- API -------------------------------------------------

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        for w in (self._burndown, self._history, self._summary, self._calendar):
            w.set_theme(theme_name)
        self._retint_rail()

    def set_filter(self, tokens: list[str]) -> None:
        self._filter = tokens
        self._calendar.set_filter(tokens)
        self.reload()

    def reload(self) -> None:
        self._load_active()

    # --- internals -----------------------------------------

    def _retint_rail(self) -> None:
        for i in range(self._rail.count()):
            it = self._rail.item(i)
            it.setIcon(icons.icon(it.data(Qt.ItemDataRole.UserRole + 5), "text_muted"))

    def _on_pick(self, row: int) -> None:
        if row < 0:
            return
        key = self._rail.item(row).data(Qt.ItemDataRole.UserRole)
        self._active = key
        self._title.setText(self._rail.item(row).text())
        self._stack.setCurrentWidget(self._widget_for[key])
        self._period_combo.setVisible(key in _PERIOD_REPORTS)
        self._hist_mode.setVisible(key in ("history", "ghistory"))
        self._export_btn.setVisible(key in _MPL_REPORTS)
        if key in ("history", "ghistory"):
            self._history.set_mode("ghistory" if key == "ghistory" else "history")
        self._load_active()

    def _on_period(self) -> None:
        self._period = self._period_combo.currentData()
        self._load_active()

    def _on_hist_mode(self) -> None:
        if self._active in ("history", "ghistory"):
            self._history.set_mode(self._hist_mode.currentData())

    def _load_active(self) -> None:
        key = self._active
        flt = self._filter or None
        self._gen += 1
        gen = self._gen

        def guarded(setter):
            def apply(result):
                if gen == self._gen:
                    setter(result)
            return apply

        if key == "burndown":
            submit(functools.partial(reports.report_burndown, self._period, flt),
                   guarded(self._burndown.set_data))
        elif key in ("history", "ghistory"):
            submit(functools.partial(reports.report_history, self._period, flt),
                   guarded(self._history.set_data))
        elif key == "summary":
            submit(functools.partial(reports.report_summary, flt),
                   guarded(self._summary.set_data))
        elif key == "calendar":
            self._calendar.reload()
        elif key == "projects":
            submit(functools.partial(reports.report_projects, flt),
                   guarded(self._projects.set_data))
        elif key == "tags":
            submit(functools.partial(reports.report_tags, flt),
                   guarded(self._tags.set_data))

    def _export(self) -> None:
        widget = self._widget_for[self._active]
        if not hasattr(widget, "export_png"):
            return
        default = f"{tempfile.gettempdir()}/{self._active}.png"
        path, _ = QFileDialog.getSaveFileName(self, "ذخیرهٔ نمودار", default, "PNG (*.png)")
        if path:
            widget.export_png(path)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(900, 560)
