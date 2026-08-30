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
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolBar,
)

from jtask import reports, taskwarrior
from jtask.errors import TaskCommandError
from jtask.rtl import set_digit_mode

from . import fmt, icons
from .models.task_model import TaskTableModel
from .settings import Settings
from .theme import other_theme, render_qss
from .widgets.command_console import CommandConsole
from .widgets.confirm import confirm
from .widgets.detail_panel import DetailPanel
from .widgets.error_dialog import ErrorDialog
from .widgets.filter_bar import FilterBar
from .widgets.history_view import TaskHistoryView
from .widgets.op_status import OperationStatus
from .widgets.quick_add import QuickAddBar
from .widgets.raw_data_view import RawDataView
from .widgets.reports_view import ReportsView
from .widgets.sidebar import Sidebar
from .widgets.task_table import TaskTable
from .widgets.timer_indicator import TimerIndicator
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
        self._history_view = TaskHistoryView()
        self._raw_view = RawDataView()
        self._reports = ReportsView(self.settings.theme)

        self._really_quit = False
        self._build_central()
        self._build_toolbars()
        self._build_sidebar()
        self._build_console()
        self._build_statusbar()
        self._build_tray()
        self._wire()

        self._ensure_styled()
        self._restore_state()
        self.refresh_all()
        if self.settings.notifications_enabled:
            self._notify.reconfigure()

    def _ensure_styled(self) -> None:
        """Apply the theme stylesheet if the app was created without one."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None and not app.styleSheet():
            app.setStyleSheet(render_qss(self.settings.theme))

    # --- construction ----------------------------------------

    def _build_central(self) -> None:
        self._content = QStackedWidget()

        self._detail_host = QTabWidget()
        self._detail_host.setObjectName("DetailTabs")
        self._detail_host.setDocumentMode(True)
        self._detail_host.addTab(self._detail, "ویرایش")
        self._detail_host.addTab(self._history_view, "تاریخچه")
        self._detail_host.addTab(self._raw_view, "دادهٔ خام")

        self._split = QSplitter(Qt.Orientation.Horizontal)
        self._split.setObjectName("MainSplit")
        self._split.setHandleWidth(1)
        self._split.addWidget(self._table)
        self._split.addWidget(self._detail_host)
        self._split.setStretchFactor(0, 1)
        self._split.setStretchFactor(1, 0)
        self._split.setCollapsible(0, False)
        self._split.setCollapsible(1, True)
        for w in (self._table, self._detail_host):
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._detail_host.setVisible(False)
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

        self._add_full_action = QAction(icons.icon("add"), "افزودن کار…", self)
        self._add_full_action.setShortcut("Ctrl+Shift+N")
        self._add_full_action.setToolTip("افزودن کار با همهٔ فیلدها (Ctrl+Shift+N)")
        self._add_full_action.triggered.connect(lambda: self._open_task_form("add"))
        row2.addAction(self._add_full_action)

        self._log_action = QAction(icons.icon("completed"), "ثبت کار انجام‌شده…", self)
        self._log_action.setToolTip("ثبت کاری که همین حالا انجام شده است (task log)")
        self._log_action.triggered.connect(lambda: self._open_task_form("log"))
        row2.addAction(self._log_action)

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

    def _build_tray(self) -> None:
        from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

        from .app import app_icon
        from .notifications import NotificationManager

        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("jtask")
        menu = QMenu(self)
        act_show = menu.addAction("نمایش / پنهان‌کردن پنجره")
        act_show.triggered.connect(self._toggle_window)
        act_add = menu.addAction("افزودن سریع")
        act_add.triggered.connect(self._focus_quick_add_from_tray)
        menu.addSeparator()
        act_quit = menu.addAction("خروج")
        act_quit.triggered.connect(self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()

        self._notify = NotificationManager(self.settings, self._tray, self)
        self._notify.taskActivated.connect(self._raise_window)

    def _on_tray_activated(self, reason) -> None:
        from PyQt6.QtWidgets import QSystemTrayIcon

        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self._raise_window()

    def _raise_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _focus_quick_add_from_tray(self) -> None:
        self._raise_window()
        self._quick_add.focus()

    def _quit(self) -> None:
        from PyQt6.QtWidgets import QApplication

        self._really_quit = True
        QApplication.quit()

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

        self._timer = TimerIndicator()
        self._timer.stopRequested.connect(lambda uuid: self._start_stop(uuid, False))
        sb.addWidget(self._timer)

        self._op_status = OperationStatus()
        self._status_busy = self._op_status  # back-compat alias
        sb.addWidget(self._op_status)

    def _wire(self) -> None:
        self._sidebar.activated.connect(self._on_view_selected)
        self._sidebar.contextChangeRequested.connect(self._change_context)
        self._quick_add.taskRequested.connect(self._add_task)
        self._filter_bar.filterChanged.connect(self._on_filter_changed)
        self._table.taskActivated.connect(self._show_detail)
        self._table.doneRequested.connect(
            lambda uuids: self._bulk(uuids, "done", "کارها انجام‌شده شدند")
        )
        self._table.deleteRequested.connect(self._delete)
        self._table.duplicateRequested.connect(self._duplicate)
        self._table.appendRequested.connect(
            lambda uuids: self._append_like(uuids, "append", "افزودن به شرح")
        )
        self._table.prependRequested.connect(
            lambda uuids: self._append_like(uuids, "prepend", "پیش‌افزودن به شرح")
        )
        self._table.purgeRequested.connect(self._purge)
        self._table.bulkEditRequested.connect(self._bulk_edit)
        self._table.startStopRequested.connect(self._start_stop)
        self._reports.filterRequested.connect(self._drill_into_filter)
        self._reports._calendar.taskRescheduled.connect(self._reschedule)
        self._sidebar.tasksDroppedOnProject.connect(self._reassign_project)
        self._sidebar.savedFilterActivated.connect(self._apply_saved_filter)
        self._sidebar.savedFilterRenameRequested.connect(self._rename_filter)
        self._sidebar.savedFilterDeleteRequested.connect(self._delete_filter)
        self._filter_bar.saveRequested.connect(self._save_filter)
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
            self._detail_host.setVisible(False)

    def _show_detail(self, task: dict) -> None:
        self._detail.load_task(task)
        self._history_view.load_task(task)
        self._raw_view.load_task(task)
        self._detail_host.setVisible(True)
        self._animate_detail(_DETAIL_WIDTH)

    def _hide_detail(self) -> None:
        self._animate_detail(0)

    # --- drag & drop / saved filters ----------------------

    def _reassign_project(self, uuids: list[str], project: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"project:{project}"]),
            f"به پروژهٔ «{project}» منتقل شد",
        )

    def _reschedule(self, uuids: list[str], gregorian: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"due:{gregorian}"]),
            "سررسید به‌روزرسانی شد",
        )

    def _save_filter(self, name: str, raw: str) -> None:
        self.settings.save_filter(name, raw)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())

    def _rename_filter(self, old: str, new: str) -> None:
        self.settings.rename_filter(old, new)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())

    def _delete_filter(self, name: str) -> None:
        self.settings.delete_filter(name)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())

    def _apply_saved_filter(self, raw: str) -> None:
        self._filter_bar.set_text(raw)
        self._filter_bar._apply()

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
        self._sidebar.populate_saved_filters(self.settings.saved_filters())
        self._reports.discover_custom_reports()
        submit(
            lambda: taskwarrior.export(["+ACTIVE"]),
            self._timer.set_active_tasks,
            lambda _e: None,
        )
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
        self._detail.set_all_tasks(tasks)
        self._table.show_empty_state(self._view_spec.get("title", ""), len(tasks) == 0)
        title = self._view_spec.get("title", "کارها")
        self._status_count.setText(f"{fmt.num(len(tasks))} کار · {title}")

    def _on_load_error(self, err: object) -> None:
        self._end_busy()
        self._op_status.failed("بارگذاری ناموفق بود")
        self._error(err)

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

    def _open_task_form(self, mode: str) -> None:
        from .widgets.task_form import TaskFormDialog

        dlg = TaskFormDialog(
            mode, taskwarrior.list_projects(), taskwarrior.list_tags(), self
        )
        if not dlg.exec():
            return
        args = dlg.args()
        verb = taskwarrior.log if mode == "log" else taskwarrior.add
        self._write(
            functools.partial(verb, args),
            "کار انجام‌شده ثبت شد" if mode == "log" else "کار افزوده شد",
        )

    def _bulk(self, uuids: list[str], verb: str, msg: str) -> None:
        if not uuids:
            return
        self._write(functools.partial(taskwarrior.command, uuids, verb), msg)

    # --- M5 task-lifecycle verbs --------------------------

    def _delete(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if not confirm(
            self,
            title="حذف کارها",
            body=(
                "کارهای انتخاب‌شده حذف می‌شوند. با «واگرد» یا از نمای "
                "«تکمیل‌شده» قابل بازیابی‌اند."
            ),
            count=len(uuids),
            destructive=True,
            confirm_label="حذف",
        ):
            return
        self._bulk(uuids, "delete", "کارها حذف شدند")

    def _duplicate(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if len(uuids) == 1:
            self._begin_busy("در حال تکثیر…")

            def done(res: dict) -> None:
                self._end_busy()
                self._op_status.success("کار تکثیر شد")
                new = res.get("id") or res.get("uuid") or ""
                self.statusBar().showMessage(
                    f"کار تکثیر شد ({new})" if new else "کار تکثیر شد", 3000
                )
                self.refresh_all()

            submit(
                functools.partial(taskwarrior.duplicate, uuids), done, self._op_failed
            )
        else:
            self._write(
                functools.partial(taskwarrior.command, uuids, "duplicate"),
                "کارها تکثیر شدند",
            )

    def _append_like(self, uuids: list[str], verb: str, title: str) -> None:
        if not uuids:
            return
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(self, title, "متن:")
        text = text.strip()
        if not ok or not text:
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=title,
            body=f"«{text}» به شرح کارهای انتخاب‌شده {title} می‌شود.",
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, verb, [text]),
            "شرح به‌روزرسانی شد",
        )

    def _purge(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if not confirm(
            self,
            title="پاک‌سازی برای همیشه",
            body=(
                "این کارهای حذف‌شده برای همیشه از پایگاه‌دادهٔ Taskwarrior پاک "
                "می‌شوند و دیگر با «واگرد» بازیابی نمی‌شوند."
            ),
            count=len(uuids),
            destructive=True,
            confirm_label="پاک‌سازی برای همیشه",
            require_phrase="پاک‌سازی",
        ):
            return
        self._write(
            functools.partial(taskwarrior.purge, uuids), "کارهای حذف‌شده پاک شدند"
        )

    def _bulk_edit(self, uuids: list[str]) -> None:
        if not uuids:
            return
        from .widgets.bulk_edit import BulkEditDialog

        dlg = BulkEditDialog(
            len(uuids),
            taskwarrior.list_projects(),
            taskwarrior.list_tags(),
            self,
        )
        if not dlg.exec():
            return
        mods = dlg.mods()
        if not mods:
            self.statusBar().showMessage("تغییری انتخاب نشد.", 2000)
            return
        if len(uuids) > 1 and not confirm(
            self,
            title="ویرایش گروهی",
            body="تغییرات زیر اعمال می‌شود:\n" + " ".join(mods),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", mods),
            "کارها به‌روزرسانی شدند",
        )

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
        """Show what the last transaction reverts, then confirm before applying."""
        self._begin_busy("در حال آماده‌سازی واگرد…")
        submit(taskwarrior.undo_preview, self._confirm_undo, self._on_load_error)

    def _confirm_undo(self, preview: dict) -> None:
        self._end_busy()
        if preview.get("empty"):
            self._op_status.idle()
            self.statusBar().showMessage("چیزی برای واگرد وجود ندارد.", 2500)
            return
        ok = confirm(
            self,
            title="واگرد آخرین تغییر",
            body=(
                "آخرین تراکنش Taskwarrior به وضعیت پیش از آن بازگردانده می‌شود.\n"
                "این عمل بازگشت‌پذیر نیست."
            ),
            count=preview.get("count"),
            count_noun="عملیات",
            destructive=True,
            confirm_label="واگرد",
            details=preview.get("text"),
        )
        if ok:
            self._write(
                functools.partial(taskwarrior.run, ["undo"]), "واگرد انجام شد"
            )

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
        self._detail.set_theme(name)
        self._sidebar.retint()
        self._filter_bar.retint()
        self._reports.set_theme(name)
        self._sync_theme_action()
        self._undo_action.setIcon(icons.icon("undo"))
        self._settings_action.setIcon(icons.icon("settings"))
        self._console_action.setIcon(icons.icon("console"))
        self._add_full_action.setIcon(icons.icon("add"))
        self._log_action.setIcon(icons.icon("completed"))

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
            self._notify.reconfigure()
            self.refresh_all()

    # --- busy / helpers ----------------------------------

    def _begin_busy(self, message: str) -> None:
        self._pending_ops += 1
        self._op_status.running(message)

    def _end_busy(self) -> None:
        self._pending_ops = max(0, self._pending_ops - 1)
        if self._pending_ops == 0 and self._op_status.state == "running":
            self._op_status.idle()

    def _write(self, fn, success_msg: str) -> None:
        self._begin_busy("در حال اعمال…")

        def done(_result):
            self._end_busy()
            self._op_status.success(success_msg)
            self.statusBar().showMessage(success_msg, 2500)
            self.refresh_all()

        submit(fn, done, self._op_failed)

    def _op_failed(self, err: object) -> None:
        self._end_busy()
        self._op_status.failed("عملیات ناموفق بود")
        self._error(err)

    def _error(self, err: object) -> None:
        """Surface a failure without ever crashing — real exit code + stderr
        behind a disclosure, with copy + open-console (§23)."""
        message = str(err)
        details = err.details() if isinstance(err, TaskCommandError) else None
        ErrorDialog(
            message, details, parent=self, on_open_console=self._reveal_console
        ).exec()

    def _reveal_console(self) -> None:
        self._console_action.setChecked(True)
        self._console_dock.setVisible(True)
        self._console_dock.raise_()
        self._console._in.setFocus()

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
        # keep running in the tray so notifications continue, unless the user
        # picked "خروج" from the tray menu
        if (
            not self._really_quit
            and self.settings.notifications_enabled
            and self._tray.isVisible()
        ):
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "jtask", "برنامه در نوار وظیفه فعال است.",
                self._tray.MessageIcon.Information, 3000,
            )
            return
        self._notify.stop()
        super().closeEvent(event)


def _has_task() -> bool:
    try:
        taskwarrior.binary()
        return True
    except Exception:  # noqa: BLE001
        return False
