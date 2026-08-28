"""The application shell: sidebar, task table, detail panel, console, toolbars."""

from __future__ import annotations

import functools
import logging

from PyQt6.QtCore import QEasingCurve, QSize, Qt, QVariantAnimation
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolBar,
)

from jtask import reports, taskwarrior
from jtask.rtl import set_digit_mode

from . import fmt, icons
from .models.task_model import TaskTableModel
from .settings import Settings
from .theme import other_theme, render_qss
from .widgets.command_console import CommandConsole
from .widgets.detail_panel import DetailPanel
from .widgets.filter_bar import FilterBar
from .widgets.quick_add import QuickAddBar
from .widgets.reports_view import ReportsView
from .widgets.sidebar import Sidebar
from .widgets.task_table import TaskTable
from .workers import submit

log = logging.getLogger("jtask_gui.window")

_DEFAULT_VIEW = {"kind": "report", "title": "اقدامات بعدی", "fn": "report_ready"}
_DETAIL_WIDTH = 460
_MIN_SIZE = QSize(940, 620)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        icons.set_theme(self.settings.theme)
        set_digit_mode(self.settings.persian_digits)
        self.setWindowTitle("jtask — مدیریت کارها")
        self.setMinimumSize(_MIN_SIZE)
        self.resize(1240, 800)

        self._view_spec: dict = dict(_DEFAULT_VIEW)
        self._extra_filter: list[str] = []
        self._pending_ops = 0

        self._model = TaskTableModel(
            self.settings.theme,
            self.settings.persian_digits,
            self.settings.due_soon_days,
        )
        self._table = TaskTable(self._model)
        self._detail = DetailPanel()
        self._reports = ReportsView(self.settings.theme)

        self._build_central()
        self._build_toolbars()
        self._build_sidebar()
        self._build_console()
        self._build_statusbar()
        self._wire()

        self._ensure_styled()
        self._restore_state()
        self.refresh_all()

    def _ensure_styled(self) -> None:
        """Apply the theme stylesheet if the app was created without one."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None and not app.styleSheet():
            app.setStyleSheet(render_qss(self.settings.theme))

    # --- construction ----------------------------------------

    def _build_central(self) -> None:
        self._content = QStackedWidget()

        self._split = QSplitter(Qt.Orientation.Horizontal)
        self._split.setObjectName("MainSplit")
        self._split.setHandleWidth(1)
        self._split.addWidget(self._table)
        self._split.addWidget(self._detail)
        self._split.setStretchFactor(0, 1)
        self._split.setStretchFactor(1, 0)
        self._split.setCollapsible(0, False)
        self._split.setCollapsible(1, True)
        for w in (self._table, self._detail):
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._detail.setVisible(False)
        self._split.setSizes([1_000_000, 0])

        self._content.addWidget(self._split)     # index 0: tasks
        self._content.addWidget(self._reports)   # index 1: reports & charts
        self.setCentralWidget(self._content)

        from PyQt6.QtWidgets import QApplication

        headless = (
            QApplication.instance() is not None
            and QApplication.instance().platformName() == "offscreen"
        )
        self._detail_anim = QVariantAnimation(self)
        self._detail_anim.setDuration(0 if headless else 170)
        self._detail_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._detail_anim.valueChanged.connect(self._apply_detail_width)
        self._detail_anim.finished.connect(self._detail_anim_done)

    def _build_toolbars(self) -> None:
        # ---- row one: quick-add ----
        row1 = QToolBar("افزودن")
        row1.setObjectName("RowOne")
        row1.setMovable(False)
        row1.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, row1)

        add_lbl = QLabel("افزودن سریع")
        add_lbl.setObjectName("ToolLabel")
        row1.addWidget(add_lbl)
        self._quick_add = QuickAddBar()
        self._quick_add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row1.addWidget(self._quick_add)

        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        # ---- row two: filter + actions ----
        row2 = QToolBar("ابزار")
        row2.setObjectName("RowTwo")
        row2.setMovable(False)
        row2.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, row2)

        flt_lbl = QLabel("فیلتر")
        flt_lbl.setObjectName("ToolLabel")
        row2.addWidget(flt_lbl)
        self._filter_bar = FilterBar()
        self._filter_bar.setMinimumWidth(320)
        self._filter_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row2.addWidget(self._filter_bar)

        row2.addSeparator()

        grp_lbl = QLabel("گروه‌بندی بر اساس")
        grp_lbl.setObjectName("ToolLabel")
        row2.addWidget(grp_lbl)
        self._group_combo = QComboBox()
        for label, key in [("بدون گروه", "none"), ("پروژه", "project"),
                           ("اولویت", "priority"), ("هفتهٔ سررسید", "due"), ("وضعیت", "status")]:
            self._group_combo.addItem(label, key)
        self._group_combo.setToolTip("گروه‌بندی فهرست کارها")
        self._group_combo.currentIndexChanged.connect(
            lambda: self._table.set_group_key(self._group_combo.currentData())
        )
        row2.addWidget(self._group_combo)
        row2.addSeparator()

        self._undo_action = QAction(icons.icon("undo"), "واگرد آخرین عملیات", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.setToolTip("واگرد آخرین عملیات (Ctrl+Z)")
        self._undo_action.triggered.connect(self._undo)
        row2.addAction(self._undo_action)

        row2.addSeparator()

        self._theme_action = QAction(self)
        self._theme_action.triggered.connect(self._toggle_theme)
        self._sync_theme_action()
        row2.addAction(self._theme_action)

        self._settings_action = QAction(icons.icon("settings"), "تنظیمات", self)
        self._settings_action.setToolTip("تنظیمات")
        self._settings_action.triggered.connect(self._open_settings)
        row2.addAction(self._settings_action)

        self._console_action = QAction(icons.icon("console"), "کنسول فرمان", self)
        self._console_action.setToolTip("کنسول فرمان خام (task …)")
        self._console_action.setCheckable(True)
        self._console_action.toggled.connect(self._toggle_console)
        row2.addAction(self._console_action)

        self._toolbars = [row1, row2]

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
        dock.setMinimumWidth(240)
        # Persian reading order: navigation sits on the right.
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
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
        sb = self.statusBar()
        self._status_count = QLabel("")
        self._status_count.setObjectName("StatusCount")
        sb.addPermanentWidget(self._status_count)

        self._status_binary = QLabel()
        ok = _has_task()
        self._status_binary.setObjectName("StatusOk" if ok else "StatusBad")
        self._status_binary.setText(
            "Taskwarrior آماده است" if ok else "Taskwarrior یافت نشد"
        )
        sb.addWidget(self._status_binary)

        self._status_busy = QLabel("")
        self._status_busy.setObjectName("Muted")
        sb.addWidget(self._status_busy)

    def _wire(self) -> None:
        self._sidebar.activated.connect(self._on_view_selected)
        self._sidebar.contextChangeRequested.connect(self._change_context)
        self._quick_add.taskRequested.connect(self._add_task)
        self._filter_bar.filterChanged.connect(self._on_filter_changed)
        self._table.taskActivated.connect(self._show_detail)
        self._table.doneRequested.connect(
            lambda uuids: self._bulk(uuids, "done", "کارها انجام‌شده شدند")
        )
        self._table.deleteRequested.connect(
            lambda uuids: self._bulk(uuids, "delete", "کارها حذف شدند")
        )
        self._table.startStopRequested.connect(self._start_stop)
        self._reports.filterRequested.connect(self._drill_into_filter)
        self._detail.closed.connect(self._hide_detail)
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

    # --- detail panel show / hide --------------------------

    def _detail_width(self) -> int:
        sizes = self._split.sizes()
        return sizes[1] if len(sizes) > 1 else 0

    def _apply_detail_width(self, width) -> None:
        width = int(width)
        total = max(self._split.width(), 1)
        self._split.setSizes([max(1, total - width), width])

    def _animate_detail(self, target: int) -> None:
        self._detail_anim.stop()
        self._detail_anim.setStartValue(self._detail_width())
        self._detail_anim.setEndValue(target)
        self._detail_anim.start()

    def _detail_anim_done(self) -> None:
        end = int(self._detail_anim.endValue() or 0)
        self._apply_detail_width(end)
        if end == 0:
            self._detail.setVisible(False)

    def _show_detail(self, task: dict) -> None:
        self._detail.load_task(task)
        self._detail.setVisible(True)
        self._animate_detail(_DETAIL_WIDTH)

    def _hide_detail(self) -> None:
        self._animate_detail(0)

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
        if spec.get("kind") == "reports":
            self._content.setCurrentIndex(1)
            self._status_count.setText("گزارش‌ها و نمودارها")
            self._reports.set_filter(self._extra_filter)
            return
        self._content.setCurrentIndex(0)

        base_filter = list(spec.get("filter") or [])
        fn_name = spec.get("fn")
        extra = self._extra_filter

        if fn_name:
            fetch = functools.partial(getattr(reports, fn_name), extra or None)
        else:
            fetch = functools.partial(reports.report_list, base_filter + extra)

        self._begin_busy("در حال بارگذاری…")
        submit(fetch, self._populate_table, self._on_load_error)

    def _populate_table(self, tasks: list[dict]) -> None:
        self._end_busy()
        self._model.set_tasks(tasks)
        self._table.show_empty_state(self._view_spec.get("title", ""), len(tasks) == 0)
        title = self._view_spec.get("title", "کارها")
        self._status_count.setText(f"{fmt.num(len(tasks))} کار · {title}")

    def _on_load_error(self, message: str) -> None:
        self._end_busy()
        self._error(message)

    # --- events --------------------------------------------

    def _on_view_selected(self, spec: dict) -> None:
        self._view_spec = spec
        self._load_current_view()

    def _on_filter_changed(self, tokens: list[str]) -> None:
        self._extra_filter = tokens
        self._load_current_view()

    def _drill_into_filter(self, tokens: list[str]) -> None:
        """A projects/tags report row was activated — show it in the task list."""
        self._filter_bar.set_text(" ".join(tokens))
        self._extra_filter = tokens
        self._view_spec = {"kind": "report", "title": "نتایج فیلتر", "fn": "report_list"}
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
        # The detail panel already emits Taskwarrior-ready tokens: its Jalali
        # date pickers hand back Gregorian strings, so mods must NOT be run
        # through rewrite_args again (that would reject the Gregorian dates).
        self._write(
            functools.partial(taskwarrior.command, [uuid], "modify", mods),
            "کار به‌روزرسانی شد",
        )

    def _undo(self) -> None:
        self._write(functools.partial(taskwarrior.run, ["undo"]), "واگرد انجام شد")

    def _change_context(self, name: str) -> None:
        verb = ["context", "none"] if not name else ["context", name]
        self._write(functools.partial(taskwarrior.run, verb), "زمینه تغییر کرد")

    # --- theme --------------------------------------------

    def _sync_theme_action(self) -> None:
        nxt = other_theme(self.settings.theme)
        glyph = "theme_light" if nxt == "روز" else "theme_dark"
        self._theme_action.setIcon(icons.icon(glyph))
        self._theme_action.setText(f"پوستهٔ {nxt}")
        self._theme_action.setToolTip(f"تغییر پوسته به «{nxt}»")

    def _toggle_theme(self) -> None:
        self._apply_theme(other_theme(self.settings.theme))

    def _apply_theme(self, name: str) -> None:
        from PyQt6.QtWidgets import QApplication

        self.settings.theme = name
        icons.set_theme(name)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(render_qss(name))
        else:  # pragma: no cover
            self.setStyleSheet(render_qss(name))
        self._model.set_theme(name)
        self._sidebar.retint()
        self._filter_bar.retint()
        self._reports.set_theme(name)
        self._sync_theme_action()
        self._undo_action.setIcon(icons.icon("undo"))
        self._settings_action.setIcon(icons.icon("settings"))
        self._console_action.setIcon(icons.icon("console"))

    def _toggle_console(self, visible: bool) -> None:
        self._console_dock.setVisible(visible)
        self.settings.console_visible = visible

    def _open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            set_digit_mode(self.settings.persian_digits)
            self._model.set_persian_digits(self.settings.persian_digits)
            self._model.set_due_soon_days(self.settings.due_soon_days)
            self._reports.refresh_digits()
            self._apply_theme(self.settings.theme)
            self.refresh_all()

    # --- busy / helpers ----------------------------------

    def _begin_busy(self, message: str) -> None:
        self._pending_ops += 1
        self._status_busy.setText("⟳ " + message)

    def _end_busy(self) -> None:
        self._pending_ops = max(0, self._pending_ops - 1)
        if self._pending_ops == 0:
            self._status_busy.setText("")

    def _write(self, fn, success_msg: str) -> None:
        self._begin_busy("در حال اعمال…")

        def done(_result):
            self._end_busy()
            self.statusBar().showMessage(success_msg, 2500)
            self.refresh_all()

        def failed(message):
            self._end_busy()
            self._error(message)

        submit(fn, done, failed)

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "خطا", message)

    def _restore_state(self) -> None:
        geo = self.settings.window_geometry()
        if geo:
            self.restoreGeometry(geo)
        state = self.settings.window_state()
        if state:
            self.restoreState(state)
        self._console_action.setChecked(self._console_dock.isVisible())

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
