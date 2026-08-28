"""The application shell: sidebar, task table, detail panel, console, toolbar."""

from __future__ import annotations

import functools

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QToolBar,
)

from jtask import reports, taskwarrior

from .models.task_model import TaskTableModel
from .settings import Settings
from .theme import THEMES, render_qss
from .widgets.command_console import CommandConsole
from .widgets.detail_panel import DetailPanel
from .widgets.filter_bar import FilterBar
from .widgets.quick_add import QuickAddBar
from .widgets.reports_placeholder import ReportsPlaceholder
from .widgets.sidebar import Sidebar
from .widgets.task_table import TaskTable
from .workers import submit

_DEFAULT_VIEW = {"kind": "report", "title": "اقدامات بعدی", "fn": "report_ready"}


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self.setWindowTitle("jtask — مدیریت کارها")
        self.resize(1200, 760)

        self._view_spec: dict = dict(_DEFAULT_VIEW)
        self._extra_filter: list[str] = []

        self._model = TaskTableModel(
            self.settings.theme,
            self.settings.persian_digits,
            self.settings.due_soon_days,
        )
        self._table = TaskTable(self._model)
        self._detail = DetailPanel()
        self._placeholder = ReportsPlaceholder()

        self._content = QStackedWidget()
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._table)
        split.addWidget(self._detail)
        split.setStretchFactor(0, 1)
        self._content.addWidget(split)          # index 0: tasks
        self._content.addWidget(self._placeholder)  # index 1: reports placeholder
        self.setCentralWidget(self._content)

        self._build_toolbar()
        self._build_sidebar()
        self._build_console()
        self._build_statusbar()
        self._wire()

        self._restore_state()
        self.refresh_all()

    # --- construction ----------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("اصلی")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        self._quick_add = QuickAddBar()
        tb.addWidget(self._quick_add)
        tb.addSeparator()

        self._filter_bar = FilterBar()
        self._filter_bar.setMinimumWidth(260)
        tb.addWidget(self._filter_bar)
        tb.addSeparator()

        self._undo_action = QAction("واگرد آخرین عملیات", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._undo)
        tb.addAction(self._undo_action)

        self._group_combo = QComboBox()
        for label, key in [("بدون گروه", "none"), ("پروژه", "project"),
                           ("اولویت", "priority"), ("سررسید", "due"), ("وضعیت", "status")]:
            self._group_combo.addItem(label, key)
        self._group_combo.currentIndexChanged.connect(
            lambda: self._table.set_group_key(self._group_combo.currentData())
        )
        tb.addWidget(QLabel("گروه‌بندی:"))
        tb.addWidget(self._group_combo)
        tb.addSeparator()

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(THEMES))
        self._theme_combo.setCurrentText(self.settings.theme)
        self._theme_combo.currentTextChanged.connect(self._change_theme)
        tb.addWidget(QLabel("پوسته:"))
        tb.addWidget(self._theme_combo)

        settings_action = QAction("تنظیمات", self)
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

        self._console_action = QAction("کنسول فرمان", self)
        self._console_action.setCheckable(True)
        self._console_action.toggled.connect(self._toggle_console)
        tb.addAction(self._console_action)

        add_sc = QAction(self)
        add_sc.setShortcut("Ctrl+N")
        add_sc.triggered.connect(self._quick_add.focus)
        self.addAction(add_sc)

    def _build_sidebar(self) -> None:
        self._sidebar = Sidebar()
        dock = QDockWidget("پیمایش", self)
        dock.setObjectName("SidebarDock")
        dock.setWidget(self._sidebar)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        # RTL: the "left" dock area renders on the right
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._sidebar_dock = dock

    def _build_console(self) -> None:
        self._console = CommandConsole()
        dock = QDockWidget("کنسول فرمان", self)
        dock.setObjectName("ConsoleDock")
        dock.setWidget(self._console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setVisible(self.settings.console_visible)
        self._console_dock = dock

    def _build_statusbar(self) -> None:
        self._status_count = QLabel("—")
        self.statusBar().addPermanentWidget(self._status_count)
        binary = "task یافت شد" if _has_task() else "task یافت نشد!"
        self.statusBar().addWidget(QLabel(binary))

    def _wire(self) -> None:
        self._sidebar.activated.connect(self._on_view_selected)
        self._sidebar.contextChangeRequested.connect(self._change_context)
        self._quick_add.taskRequested.connect(self._add_task)
        self._filter_bar.filterChanged.connect(self._on_filter_changed)
        self._table.taskActivated.connect(self._detail.load_task)
        self._table.doneRequested.connect(
            lambda uuids: self._bulk(uuids, "done", "کارها انجام‌شده شدند")
        )
        self._table.deleteRequested.connect(
            lambda uuids: self._bulk(uuids, "delete", "کارها حذف شدند")
        )
        self._table.startStopRequested.connect(self._start_stop)
        self._detail.saveRequested.connect(self._save_task)
        self._detail.annotateRequested.connect(
            lambda uuid, text: self._write(
                functools.partial(taskwarrior.command, [uuid], "annotate", [text]),
                "یادداشت افزوده شد",
            )
        )
        self._detail.denotateRequested.connect(
            lambda uuid, text: self._write(
                functools.partial(taskwarrior.command, [uuid], "denotate", [text]),
                "یادداشت حذف شد",
            )
        )

    # --- data flow ------------------------------------------

    def refresh_all(self) -> None:
        taskwarrior.refresh_lookups()
        self._quick_add.refresh_completions()
        self._filter_bar.refresh_completions()
        submit(reports.report_projects, self._sidebar.populate_projects, self._error)
        submit(reports.report_tags, self._sidebar.populate_tags, self._error)
        submit(
            lambda: (taskwarrior.list_contexts(), taskwarrior.current_context()),
            lambda r: self._sidebar.populate_contexts(*r),
            self._error,
        )
        submit(taskwarrior.list_projects, self._detail.set_projects, self._error)
        submit(taskwarrior.list_tags, self._detail.set_tag_completions, self._error)
        self._load_current_view()

    def _load_current_view(self) -> None:
        spec = self._view_spec
        if spec.get("kind") == "placeholder":
            self._content.setCurrentIndex(1)
            self._status_count.setText("")
            return
        self._content.setCurrentIndex(0)

        base_filter = list(spec.get("filter") or [])
        fn_name = spec.get("fn")
        extra = self._extra_filter

        if fn_name:
            fetch = functools.partial(getattr(reports, fn_name), extra or None)
        else:
            fetch = functools.partial(reports.report_list, base_filter + extra)

        self.statusBar().showMessage("در حال بارگذاری…", 1500)
        submit(fetch, self._populate_table, self._error)

    def _populate_table(self, tasks: list[dict]) -> None:
        self._model.set_tasks(tasks)
        title = self._view_spec.get("title", "کارها")
        self._status_count.setText(f"{len(tasks)} کار — {title}")

    # --- events --------------------------------------------

    def _on_view_selected(self, spec: dict) -> None:
        self._view_spec = spec
        self._load_current_view()

    def _on_filter_changed(self, tokens: list[str]) -> None:
        self._extra_filter = tokens
        self._load_current_view()

    def _add_task(self, args: list[str]) -> None:
        self._write(functools.partial(taskwarrior.add, args), "کار افزوده شد")

    def _bulk(self, uuids: list[str], verb: str, msg: str) -> None:
        if not uuids:
            return
        self._write(functools.partial(taskwarrior.command, uuids, verb), msg)

    def _start_stop(self, uuid: str, start: bool) -> None:
        self._write(
            functools.partial(taskwarrior.command, [uuid], "start" if start else "stop"),
            "زمان‌سنجی به‌روزرسانی شد",
        )

    def _save_task(self, uuid: str, mods: list[str]) -> None:
        from jtask import rewrite

        self._write(
            functools.partial(
                taskwarrior.command, [uuid], "modify", rewrite.rewrite_args(mods)
            ),
            "کار به‌روزرسانی شد",
        )

    def _undo(self) -> None:
        self._write(functools.partial(taskwarrior.run, ["undo"]), "واگرد انجام شد")

    def _change_context(self, name: str) -> None:
        verb = ["context", "none"] if not name else ["context", name]
        self._write(functools.partial(taskwarrior.run, verb), "زمینه تغییر کرد")

    def _change_theme(self, name: str) -> None:
        from PyQt6.QtWidgets import QApplication

        self.settings.theme = name
        qss = render_qss(name)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        else:  # pragma: no cover
            self.setStyleSheet(qss)
        self._model.set_theme(name)

    def _toggle_console(self, visible: bool) -> None:
        self._console_dock.setVisible(visible)
        self.settings.console_visible = visible

    def _open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self._model.set_persian_digits(self.settings.persian_digits)
            self._model._due_soon = self.settings.due_soon_days
            self._change_theme(self.settings.theme)
            self._theme_combo.setCurrentText(self.settings.theme)
            self.refresh_all()

    # --- helpers ------------------------------------------

    def _write(self, fn, success_msg: str) -> None:
        def done(_result):
            self.statusBar().showMessage(success_msg, 2500)
            self.refresh_all()

        submit(fn, done, self._error)

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "خطا", message)

    def _restore_state(self) -> None:
        geo = self.settings.window_geometry()
        if geo:
            self.restoreGeometry(geo)
        state = self.settings.window_state()
        if state:
            self.restoreState(state)
        self._console_action.setChecked(self.settings.console_visible)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings.save_window(self.saveGeometry(), self.saveState())
        self.settings.save_columns(self._model.visible_columns(), [], {})
        self.settings.sync()
        super().closeEvent(event)


def _has_task() -> bool:
    try:
        taskwarrior.binary()
        return True
    except Exception:  # noqa: BLE001
        return False
