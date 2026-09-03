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
from jtask.rtl import bidi_isolate, set_digit_mode

from . import fmt, icons
from . import tokens as tok
from .i18n import t
from .models.task_model import TaskTableModel
from .settings import Settings
from .theme import other_theme, render_qss
from .widgets.annotations_view import AnnotationsView
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

_DEFAULT_VIEW = {"kind": "report", "key": "next", "fn": "report_ready"}
_DETAIL_WIDTH = 400
_MIN_SIZE = QSize(940, 620)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        from .i18n import lang as _ui_lang

        # The language this window was laid out for. A language change is
        # restart-gated, so if the user switches then closes without restarting,
        # the window state must still be saved under the *old* language's bucket
        # — not the newly-persisted one (that would poison the other layout).
        self._built_language = _ui_lang()
        icons.set_theme(self.settings.theme)
        set_digit_mode(self.settings.persian_digits)
        self.setWindowTitle(t("win.title"))
        self.setMinimumSize(_MIN_SIZE)
        self.resize(1240, 800)

        self._view_spec: dict = dict(_DEFAULT_VIEW, title=t("view.next"))
        self._extra_filter: list[str] = []
        self._pending_ops = 0

        self._model = TaskTableModel(
            self.settings.theme,
            self.settings.persian_digits,
            self.settings.due_soon_days,
        )
        self._table = TaskTable(self._model)
        self._table.set_density(self.settings.density)
        self._detail = DetailPanel()
        self._history_view = TaskHistoryView()
        self._raw_view = RawDataView()
        self._annotations_view = AnnotationsView()
        self._reports = ReportsView(self.settings.theme)
        from .widgets.board_view import BoardView
        self._board = BoardView(self.settings.theme)
        self._board_mode = False

        self._really_quit = False
        self._build_central()
        self._build_toolbars()
        self._build_sidebar()
        self._build_console()
        self._build_review()
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
        self._detail_host.addTab(self._detail, t("detail.tab.edit"))
        self._detail_host.addTab(self._annotations_view, t("detail.tab.annotations"))
        self._detail_host.addTab(self._history_view, t("detail.tab.history"))
        self._detail_host.addTab(self._raw_view, t("detail.tab.raw"))

        self._split = QSplitter(Qt.Orientation.Horizontal)
        self._split.setObjectName("MainSplit")
        self._split.setHandleWidth(4)  # grabbable — drag to widen the edit panel
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

        self._content.addWidget(self._split)     # index 0: tasks (table)
        self._content.addWidget(self._reports)   # index 1: reports & charts
        self._content.addWidget(self._board)     # index 2: board engine

        # A gutter of the window background around the content so the task
        # table / reports read as an elevated card, distinct from the chrome
        # (toolbars, sidebar) rather than blended into one flat plane.
        from PyQt6.QtWidgets import QVBoxLayout, QWidget

        frame = QWidget()
        frame.setObjectName("ContentFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(tok.SP_10, tok.SP_10, tok.SP_10, tok.SP_10)
        fl.setSpacing(0)
        fl.addWidget(self._content)
        self.setCentralWidget(frame)

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
        row1 = QToolBar(t("toolbar.add"))
        row1.setObjectName("RowOne")
        row1.setMovable(False)
        row1.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, row1)

        self._quick_add = QuickAddBar()
        self._quick_add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row1.addWidget(self._quick_add)

        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        # ---- row two: filter + actions ----
        row2 = QToolBar(t("toolbar.tools"))
        row2.setObjectName("RowTwo")
        row2.setMovable(False)
        row2.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, row2)

        self._filter_bar = FilterBar()
        self._filter_bar.setMinimumWidth(200)
        self._filter_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row2.addWidget(self._filter_bar)

        row2.addSeparator()

        self._group_combo = QComboBox()
        for label, key in [
            (t("group.none"), "none"), (t("group.project"), "project"),
            (t("group.priority"), "priority"), (t("group.due_week"), "due"),
            (t("group.status"), "status"),
        ]:
            self._group_combo.addItem(label, key)
        self._group_combo.setToolTip(t("toolbar.group.tip"))
        self._group_combo.setMinimumWidth(120)
        self._group_combo.currentIndexChanged.connect(
            lambda: self._table.set_group_key(self._group_combo.currentData())
        )
        row2.addWidget(self._group_combo)

        self._board_action = QAction(icons.icon("board"), t("action.board"), self)
        self._board_action.setCheckable(True)
        self._board_action.setShortcut("Ctrl+B")
        self._board_action.setToolTip(t("action.board.tip"))
        self._board_action.toggled.connect(self._toggle_board)
        row2.addAction(self._board_action)
        row2.addSeparator()

        self._add_full_action = QAction(
            icons.icon("add", "primary_fg"), t("action.add_full"), self
        )
        self._add_full_action.setShortcut("Ctrl+Shift+N")
        self._add_full_action.setToolTip(t("action.add_full.tip"))
        self._add_full_action.triggered.connect(lambda: self._open_task_form("add"))
        row2.addAction(self._add_full_action)
        _add_btn = row2.widgetForAction(self._add_full_action)
        if _add_btn is not None:
            _add_btn.setObjectName("PrimaryAction")
            _add_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self._log_action = QAction(icons.icon("completed"), t("action.log"), self)
        self._log_action.setToolTip(t("action.log.tip"))
        self._log_action.triggered.connect(lambda: self._open_task_form("log"))
        row2.addAction(self._log_action)

        row2.addSeparator()

        self._undo_action = QAction(icons.icon("undo"), t("action.undo"), self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.setToolTip(t("action.undo.tip"))
        self._undo_action.triggered.connect(self._undo)
        row2.addAction(self._undo_action)

        row2.addSeparator()

        from PyQt6.QtWidgets import QMenu, QToolButton

        self._data_btn = QToolButton()
        self._data_btn.setIcon(icons.icon("data"))
        self._data_btn.setText(t("action.data"))
        self._data_btn.setToolTip(t("action.data.tip"))
        self._data_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        data_menu = QMenu(self._data_btn)
        self._export_action = data_menu.addAction(
            icons.icon("export"), t("action.export")
        )
        self._export_action.triggered.connect(self._open_export)
        self._import_action = data_menu.addAction(
            icons.icon("import"), t("action.import")
        )
        self._import_action.triggered.connect(self._open_import)
        data_menu.addSeparator()
        self._sync_action = data_menu.addAction(icons.icon("sync"), t("action.sync"))
        self._sync_action.triggered.connect(self._open_sync)
        self._data_btn.setMenu(data_menu)
        row2.addWidget(self._data_btn)

        row2.addSeparator()

        # -- view cluster: theme + console toggle (both stateful, stay visible)
        self._theme_action = QAction(self)
        self._theme_action.triggered.connect(self._toggle_theme)
        self._sync_theme_action()
        row2.addAction(self._theme_action)

        self._console_action = QAction(icons.icon("console"), t("action.console"), self)
        self._console_action.setToolTip(t("action.console.tip"))
        self._console_action.setCheckable(True)
        self._console_action.setShortcuts(
            [QKeySequence("Ctrl+`"), QKeySequence(Qt.Key.Key_F12)]
        )
        self._console_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self._console_action.toggled.connect(self._toggle_console)
        row2.addAction(self._console_action)

        self._review_action = QAction(icons.icon("review"), t("action.review"), self)
        self._review_action.setToolTip(t("action.review.tip"))
        self._review_action.setShortcut(QKeySequence("Ctrl+R"))
        self._review_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self._review_action.triggered.connect(self._open_review)
        row2.addAction(self._review_action)

        row2.addSeparator()

        # -- config cluster: settings + a flat "more" menu for the rarely-used
        #    Manage / Diagnostics entry points (one extra click, no submenu)
        self._settings_action = QAction(icons.icon("settings"), t("action.settings"), self)
        self._settings_action.setToolTip(t("action.settings.tip"))
        self._settings_action.triggered.connect(self._open_settings)
        row2.addAction(self._settings_action)

        self._manage_action = QAction(icons.icon("manage"), t("action.manage"), self)
        self._manage_action.setToolTip(t("action.manage.tip"))
        self._manage_action.triggered.connect(self._open_manager)
        self._tools_action = QAction(icons.icon("tools"), t("action.tools"), self)
        self._tools_action.setToolTip(t("action.tools.tip"))
        self._tools_action.triggered.connect(self._open_tools)

        self._more_btn = QToolButton()
        self._more_btn.setIcon(icons.icon("more"))
        self._more_btn.setToolTip(t("toolbar.more.tip"))
        self._more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self._more_btn)
        more_menu.addAction(self._manage_action)
        more_menu.addAction(self._tools_action)
        self._more_btn.setMenu(more_menu)
        row2.addWidget(self._more_btn)

        self._toolbars = [row1, row2]

        add_sc = QAction(self)
        add_sc.setShortcut("Ctrl+N")
        add_sc.triggered.connect(self._quick_add.focus)
        self.addAction(add_sc)

        self._palette_action = QAction(t("action.command_palette"), self)
        self._palette_action.setShortcut("Ctrl+K")
        self._palette_action.setToolTip(t("action.command_palette.tip"))
        self._palette_action.triggered.connect(self._open_command_palette)
        self.addAction(self._palette_action)

    def _build_sidebar(self) -> None:
        self._sidebar = Sidebar()
        dock = QDockWidget(t("dock.navigation"), self)
        dock.setObjectName("SidebarDock")
        dock.setWidget(self._sidebar)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.setMinimumWidth(190)
        # Navigation sits on the reading-start edge: right for RTL, left for LTR.
        from .i18n import is_rtl

        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea
            if is_rtl()
            else Qt.DockWidgetArea.LeftDockWidgetArea,
            dock,
        )
        self._sidebar_dock = dock

    def _build_console(self) -> None:
        self._console = CommandConsole()
        self._console.stateChanged.connect(self._after_console_command)
        dock = QDockWidget(t("dock.console"), self)
        dock.setObjectName("ConsoleDock")
        dock.setWidget(self._console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setVisible(self.settings.console_visible)
        self._console_dock = dock

    def _build_review(self) -> None:
        from .widgets.review_wizard import ReviewWizard

        self._review = ReviewWizard()
        self._review.stepEntered.connect(self._on_review_step)
        self._review.exited.connect(self._exit_review)
        self._review.addNextActionRequested.connect(
            lambda proj: self._open_task_form("add", project=proj)
        )
        self._review_active = False
        self._pre_review_spec: dict | None = None
        dock = QDockWidget(t("dock.review"), self)
        dock.setObjectName("ReviewDock")
        dock.setWidget(self._review)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock)
        dock.setVisible(False)
        dock.visibilityChanged.connect(
            lambda vis: self._exit_review() if not vis and self._review_active else None
        )
        self._review_dock = dock

    def _open_review(self) -> None:
        import datetime

        from PyQt6.QtWidgets import QMessageBox

        at = 0
        started, step = self.settings.review_started, self.settings.review_step
        fresh = False
        if started:
            try:
                fresh = datetime.datetime.now() - datetime.datetime.fromisoformat(
                    started
                ) < datetime.timedelta(hours=48)
            except ValueError:
                fresh = False
        if fresh and step > 0 and not self._review_active:
            box = QMessageBox(self)
            box.setWindowTitle(t("review.resume.title"))
            box.setText(t("review.resume.body", n=fmt.num(step + 1)))
            resume = box.addButton(t("review.resume.yes"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(t("review.resume.restart"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            at = step if box.clickedButton() is resume else 0
        if at == 0:
            self.settings.review_started = datetime.datetime.now().isoformat(
                timespec="seconds"
            )
        if not self._review_active:
            self._pre_review_spec = dict(self._view_spec)
        self._review_active = True
        self._review_dock.setVisible(True)
        self._review_dock.raise_()
        self._review.start(at)

    def _on_review_step(self, index: int) -> None:
        key = self._review.key(index)
        self.settings.review_step = index
        if key == "reports":
            self._on_view_selected({"kind": "reports", "title": t("review.step.reports")})
            return
        from jtask.gtd import review_step, stuck_projects

        if key == "stuck_projects":
            # the dock lists the *stuck* projects; the table shows the pickable
            # work (next actions) so you can see which projects have none.
            self._on_view_selected({
                "kind": "filter", "key": "review_stuck",
                "title": t("review.step.stuck_projects"),
                "filter": review_step("next_actions").filter() or [],
            })
            submit(stuck_projects, self._review.show_stuck, lambda _e: None)
            return

        self._on_view_selected({
            "kind": "filter", "key": f"review_{key}",
            "title": t(f"review.step.{key}"),
            "filter": review_step(key).filter() or [],
        })

    def _exit_review(self) -> None:
        if not self._review_active:
            return
        self._review_active = False
        self.settings.review_step = 0
        self.settings.review_started = ""
        self._review_dock.setVisible(False)
        if self._pre_review_spec is not None:
            self._on_view_selected(self._pre_review_spec)
        self._toast.show_message(t("msg.review_closed"))

    def _build_tray(self) -> None:
        from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

        from .app import app_icon
        from .notifications import NotificationManager

        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("jtask")
        menu = QMenu(self)
        act_show = menu.addAction(t("tray.toggle_window"))
        act_show.triggered.connect(self._toggle_window)
        act_add = menu.addAction(t("tray.quick_add"))
        act_add.triggered.connect(self._focus_quick_add_from_tray)
        menu.addSeparator()
        act_quit = menu.addAction(t("tray.quit"))
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
            t("status.tw_ready") if ok else t("status.tw_missing")
        )
        sb.addWidget(self._status_binary)
        if ok:
            submit(
                taskwarrior.version,
                lambda v: self._status_binary.setText(
                    t("status.tw_version", v=v) if v else t("status.tw_ready")
                ),
                lambda _e: None,
            )

        self._timer = TimerIndicator()
        self._timer.stopRequested.connect(lambda uuid: self._start_stop(uuid, False))
        sb.addWidget(self._timer)

        self._op_status = OperationStatus()
        self._status_busy = self._op_status  # back-compat alias
        sb.addWidget(self._op_status)

        from .widgets.toast import Toast

        self._toast = Toast(self)

    def _wire(self) -> None:
        self._sidebar.activated.connect(self._on_view_selected)
        self._sidebar.contextChangeRequested.connect(self._change_context)
        self._quick_add.taskRequested.connect(self._add_task)
        self._filter_bar.filterChanged.connect(self._on_filter_changed)
        self._table.taskActivated.connect(self._show_detail)
        self._table.doneRequested.connect(
            lambda uuids: self._bulk(uuids, "done", t("msg.tasks_done"))
        )
        self._table.deleteRequested.connect(self._delete)
        self._table.duplicateRequested.connect(self._duplicate)
        self._table.appendRequested.connect(
            lambda uuids: self._append_like(uuids, "append", t("verb.append"))
        )
        self._table.prependRequested.connect(
            lambda uuids: self._append_like(uuids, "prepend", t("verb.prepend"))
        )
        self._table.annotateRequested.connect(self._annotate_bulk)
        self._table.purgeRequested.connect(self._purge)
        self._table.bulkEditRequested.connect(self._bulk_edit)
        self._table.startStopRequested.connect(self._start_stop)
        self._table.saveTemplateRequested.connect(self._save_task_as_template)
        self._reports.filterRequested.connect(self._drill_into_filter)
        self._reports._calendar.taskRescheduled.connect(self._reschedule)
        self._sidebar.tasksDroppedOnProject.connect(self._reassign_project)
        self._sidebar.tasksDroppedOnTag.connect(self._add_tag_to)
        self._sidebar.tagRenameRequested.connect(self._rename_tag)
        self._sidebar.tagRemoveRequested.connect(self._remove_tag)
        self._sidebar.projectRenameRequested.connect(self._rename_project)
        self._sidebar.projectDeleteRequested.connect(self._delete_project)
        self._sidebar.projectColorRequested.connect(self._set_project_color)
        self._sidebar.projectColorClearRequested.connect(self._clear_project_color)
        self._sidebar.addNextActionRequested.connect(
            lambda proj: self._open_task_form("add", project=proj)
        )
        self._sidebar.savedFilterActivated.connect(self._apply_saved_filter)
        self._sidebar.boardActivated.connect(self._show_board)
        self._sidebar.boardManageRequested.connect(self._open_board_manager)
        self._sidebar.savedFilterRenameRequested.connect(self._rename_filter)
        self._sidebar.savedFilterDeleteRequested.connect(self._delete_filter)
        self._filter_bar.saveRequested.connect(self._save_filter)
        self._detail.closed.connect(self._hide_detail)
        self._detail.saveRequested.connect(self._save_task)
        self._detail.starToggled.connect(self._toggle_star)
        self._model.cellEdited.connect(self._inline_edit)
        self._model.starToggled.connect(self._toggle_star)
        self._board.boardDrop.connect(self._board_drop)
        self._board.starToggled.connect(self._toggle_star)
        self._board.taskActivated.connect(self._open_card)

        from PyQt6.QtGui import QShortcut

        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WindowShortcut)
        esc.activated.connect(self._escape_pressed)

        for seq, slot in (
            ("?", self._open_shortcut_sheet),
            ("Ctrl+F", self._focus_filter),
            ("Ctrl+1", lambda: self._goto_view("today")),
            ("Ctrl+2", lambda: self._goto_view("next")),
            ("Ctrl+3", lambda: self._goto_view("completed")),
            ("Ctrl+.", self._table.toggle_star_on_selection),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(slot)
        self._annotations_view.annotateRequested.connect(
            lambda uuid, text: self._write(
                functools.partial(taskwarrior.command, [uuid], "annotate", [text]),
                t("msg.note_added"),
            )
        )
        self._annotations_view.denotateRequested.connect(
            lambda uuid, text: self._write(
                functools.partial(taskwarrior.command, [uuid], "denotate", [text]),
                t("msg.note_removed"),
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
        self._annotations_view.load_task(task)
        self._history_view.load_task(task)
        self._raw_view.load_task(task)
        self._detail_host.setVisible(True)
        self._animate_detail(_DETAIL_WIDTH)

    def _hide_detail(self) -> None:
        self._animate_detail(0)

    def _escape_pressed(self) -> None:
        """Esc closes the edit panel when it is open (and nothing else has
        claimed the key)."""
        if self._detail_host.isVisible():
            self._hide_detail()

    # --- drag & drop / saved filters ----------------------

    def _reassign_project(self, uuids: list[str], project: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"project:{project}"]),
            t("msg.moved_to_project", project=project),
        )

    def _reschedule(self, uuids: list[str], gregorian: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"due:{gregorian}"]),
            t("msg.due_updated"),
        )

    # --- tag management -----------------------------------

    def _add_tag_to(self, uuids: list[str], tag: str) -> None:
        """Drop tasks onto a sidebar tag → add that tag to them."""
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"+{tag}"]),
            t("msg.tagged", tag=tag),
        )

    def _rename_tag(self, old: str, new: str) -> None:
        def check() -> int:
            return taskwarrior.tag_count(old)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.tag_unused", tag=old))
                return
            if not confirm(
                self,
                title=t("sidebar.tag_rename.title"),
                body=t("confirm.tag_rename.body", old=old, new=new),
                count=n,
                count_noun=t("confirm.tag.noun"),
            ):
                return
            self._write(
                functools.partial(taskwarrior.rename_tag, old, new),
                t("msg.tag_renamed", old=old, new=new),
            )

        submit(check, ask, self._error)

    def _remove_tag(self, tag: str) -> None:
        def check() -> int:
            return taskwarrior.tag_count(tag)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.tag_unused", tag=tag))
                return
            if not confirm(
                self,
                title=t("sidebar.tag_remove.title"),
                body=t("confirm.tag_remove.body", tag=tag),
                count=n,
                count_noun=t("confirm.tag.noun"),
                destructive=True,
            ):
                return
            self._write(
                functools.partial(taskwarrior.remove_tag, tag),
                t("msg.tag_removed", tag=tag),
            )

        submit(check, ask, self._error)

    # --- project management ------------------------------

    def _rename_project(self, old: str, new: str) -> None:
        def check() -> int:
            return taskwarrior.project_task_count(old)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.project_empty", project=old))
                return
            if not confirm(
                self,
                title=t("sidebar.project_rename.title"),
                body=t("confirm.project_rename.body", old=old, new=new),
                count=n,
                count_noun=t("confirm.tag.noun"),
            ):
                return
            self._write(
                functools.partial(taskwarrior.rename_project, old, new),
                t("msg.project_renamed", old=old, new=new),
            )

        submit(check, ask, self._error)

    def _delete_project(self, name: str) -> None:
        def check() -> int:
            return taskwarrior.project_task_count(name)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.project_empty", project=name))
                return
            if not confirm(
                self,
                title=t("sidebar.project_delete.title"),
                body=t("confirm.project_delete.body", project=name),
                count=n,
                count_noun=t("confirm.tag.noun"),
                destructive=True,
                require_phrase=name,
            ):
                return
            self._write(
                functools.partial(taskwarrior.delete_project, name),
                t("msg.project_deleted", project=name),
            )

        submit(check, ask, self._error)

    def _set_project_color(self, name: str, color: str) -> None:
        self._write(
            functools.partial(taskwarrior.set_project_color, name, color),
            t("msg.project_colored", project=name),
        )

    def _clear_project_color(self, name: str) -> None:
        self._write(
            functools.partial(taskwarrior.clear_project_color, name),
            t("msg.project_color_cleared", project=name),
        )

    def _save_filter(self, name: str, raw: str) -> None:
        self.settings.save_filter(name, raw)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())
        self._toast.show_message(t("msg.filter_saved", name=name))

    def _rename_filter(self, old: str, new: str) -> None:
        self.settings.rename_filter(old, new)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())
        self._toast.show_message(t("msg.filter_renamed", name=new))

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
        submit(
            lambda: (reports.report_projects(), taskwarrior.project_colors()),
            lambda r: self._sidebar.populate_projects(*r),
            self._error,
        )
        submit(reports.report_tags, self._sidebar.populate_tags, self._error)
        submit(
            lambda: (taskwarrior.list_contexts(), taskwarrior.current_context()),
            lambda r: self._sidebar.populate_contexts(*r),
            self._error,
        )
        submit(
            taskwarrior.list_projects,
            lambda p: (self._detail.set_projects(p), self._table.set_projects(p)),
            self._error,
        )
        submit(taskwarrior.list_tags, self._detail.set_tag_completions, self._error)
        self._sidebar.populate_boards(self._board_names())
        self._sidebar.populate_saved_filters(self.settings.saved_filters())
        submit(self._view_counts, self._sidebar.set_view_counts, lambda _e: None)
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
            self._status_count.setText(t("status.reports"))
            self._reports.set_filter(self._extra_filter)
            return

        base_filter = list(spec.get("filter") or [])
        fn_name = spec.get("fn")
        extra = self._extra_filter

        if self._board_mode:
            self._content.setCurrentIndex(2)
            self._board.set_extra_filter(extra)
            self._board.reload()
            self._status_count.setText(
                self._board.current_board().name
                if self._board.current_board() else t("status.boards")
            )
            return

        self._content.setCurrentIndex(0)
        if fn_name:
            fetch = functools.partial(getattr(reports, fn_name), extra or None)
        else:
            fetch = functools.partial(reports.report_list, base_filter + extra)

        self._begin_busy(t("status.loading"))
        submit(fetch, self._populate_table, self._on_load_error)

    def _board_names(self) -> list[str]:
        from . import boards as B

        return [b.name for b in B.all_builtins()] + list(self.settings.boards())

    def _resolve_board(self, name: str):
        from . import boards as B

        spec = self.settings.boards().get(name)
        if spec is not None:
            return B.Board.from_dict({"name": name, **spec})
        for b in B.all_builtins():
            if b.name == name:
                return b
        return None

    def _toggle_board(self, on: bool) -> None:
        self._board_mode = on
        self._group_combo.setEnabled(not on)
        if on and self._board.current_board() is None:
            from .boards import builtin_board
            self._board.set_board(builtin_board("gtd"))
        self._load_current_view()

    def _show_board(self, name: str) -> None:
        board = self._resolve_board(name)
        if board is None:
            return
        self._board.set_board(board)
        self._board_mode = True
        self._group_combo.setEnabled(False)
        self._board_action.setChecked(True)
        self._load_current_view()

    def _open_board_manager(self) -> None:
        from .widgets.board_manager import BoardManagerDialog

        dlg = BoardManagerDialog(self.settings, self)
        dlg.changed.connect(self._on_boards_changed)
        dlg.exec()

    def _on_boards_changed(self) -> None:
        self._sidebar.populate_boards(self._board_names())
        cur = self._board.current_board()
        if self._board_mode and cur is not None:
            refreshed = self._resolve_board(cur.name)
            if refreshed is not None:
                self._board.set_board(refreshed)

    def _open_card(self, uuid: str) -> None:
        self._board_action.setChecked(False)  # back to the table

        def show(rows: list[dict]) -> None:
            if rows:
                self._show_detail(rows[0])

        submit(functools.partial(taskwarrior.export, [uuid]), show, self._error)

    def _board_drop(self, task: dict, drop: dict) -> None:
        from .boards import compile_drop

        uuid = task.get("uuid")
        compiled = compile_drop(drop)
        if not uuid or compiled is None:
            return
        verb, mods = compiled
        self._write(
            functools.partial(taskwarrior.command, [uuid], verb, mods),
            t("msg.task_updated"),
        )

    def _populate_table(self, tasks: list[dict]) -> None:
        self._end_busy()
        self._model.set_tasks(tasks)
        self._detail.set_all_tasks(tasks)
        self._table.show_empty_state(self._view_spec.get("key", ""), len(tasks) == 0)
        title = self._view_spec.get("title") or t("view.tasks")
        self._status_count.setText(t("status.count", n=fmt.num(len(tasks)), title=title))

    def _on_load_error(self, err: object) -> None:
        self._end_busy()
        self._op_status.failed(t("op.load_failed"))
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
        self._view_spec = {"kind": "report", "title": t("view.filter_results"), "fn": "report_list"}
        self._load_current_view()

    def _add_task(self, args: list[str]) -> None:
        self._write(functools.partial(taskwarrior.add, args), t("msg.task_added"))

    # --- M7 data safety: export / import / sync -----------

    def _open_export(self) -> None:
        from .widgets.export_dialog import ExportDialog, write_export

        dlg = ExportDialog(self._extra_filter, self)
        if not dlg.exec():
            return
        spec = dlg.spec()
        if not spec["path"]:
            self.statusBar().showMessage(t("msg.export.no_path"), 2500)
            return
        self._begin_busy(t("op.exporting"))

        def done(res: dict) -> None:
            self._end_busy()
            self._op_status.success(t("msg.export.done"))
            self.statusBar().showMessage(
                t("msg.export.saved", n=fmt.num(res["count"]),
                  path=bidi_isolate(res["path"])), 5000
            )

        submit(functools.partial(write_export, spec), done, self._op_failed)

    def _open_import(self) -> None:
        from .widgets.import_dialog import ImportDialog

        dlg = ImportDialog(self)
        if not dlg.exec():
            return
        path = dlg.path()
        self._begin_busy(t("op.importing"))

        def done(res: dict) -> None:
            self._end_busy()
            self._op_status.success(t("msg.import.done"))
            self.statusBar().showMessage(
                t("msg.import.summary", added=fmt.num(res["added"]),
                  modified=fmt.num(res["modified"])),
                5000,
            )
            self.refresh_all()

        submit(functools.partial(taskwarrior.import_file, path), done, self._op_failed)

    def _open_sync(self) -> None:
        from .widgets.sync_dialog import SyncManagerDialog

        dlg = SyncManagerDialog(self.settings, self)
        dlg.synced.connect(self.refresh_all)
        dlg.exec()

    def _open_manager(self) -> None:
        from .widgets.manager_dialog import ManagerDialog

        dlg = ManagerDialog(self)
        dlg.changed.connect(self.refresh_all)
        dlg.exec()

    def _open_tools(self) -> None:
        from .widgets.tools_dialog import ToolsDialog

        dlg = ToolsDialog(self)
        dlg.sendToConsole.connect(self._send_to_console)
        dlg.exec()

    def _send_to_console(self, text: str) -> None:
        self._reveal_console()
        self._console.prefill(text)

    def _open_task_form(self, mode: str, *, project: str | None = None) -> None:
        from .widgets.task_form import TaskFormDialog

        dlg = TaskFormDialog(
            mode, taskwarrior.list_projects(), taskwarrior.list_tags(), self,
            settings=self.settings,
        )
        if project:
            dlg._project.setCurrentText(project)
            dlg._description.setFocus()
        if not dlg.exec():
            return
        args = dlg.args()
        verb = taskwarrior.log if mode == "log" else taskwarrior.add
        self._write(
            functools.partial(verb, args),
            t("msg.log_added") if mode == "log" else t("msg.task_added"),
        )

    def _bulk(self, uuids: list[str], verb: str, msg: str) -> None:
        if not uuids:
            return
        self._write(functools.partial(taskwarrior.command, uuids, verb), msg)

    def _save_task_as_template(self, task: dict) -> None:
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, t("form.template.save.title"), t("form.template.save.label")
        )
        if not (ok and name.strip()):
            return
        spec = {
            "description": task.get("description", ""),
            "project": task.get("project", "") or "",
            "tags": [x for x in (task.get("tags") or []) if not x.isupper()],
            "priority": task.get("priority", "") or "",
        }
        self.settings.save_template(name.strip(), spec)
        self._toast.show_message(t("msg.template_saved", name=name.strip()))

    # --- M5 task-lifecycle verbs --------------------------

    def _delete(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if not confirm(
            self,
            title=t("confirm.delete.title"),
            body=(
                t("confirm.delete.body")
            ),
            count=len(uuids),
            destructive=True,
            confirm_label=t("confirm.delete.ok"),
        ):
            return
        self._bulk(uuids, "delete", t("msg.tasks_deleted"))

    def _duplicate(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if len(uuids) == 1:
            self._begin_busy(t("op.duplicating"))

            def done(res: dict) -> None:
                self._end_busy()
                self._op_status.success(t("msg.duplicated"))
                new = res.get("id") or res.get("uuid") or ""
                self.statusBar().showMessage(
                    t("msg.duplicated_id", new=new) if new else t("msg.duplicated"), 3000
                )
                self.refresh_all()

            submit(
                functools.partial(taskwarrior.duplicate, uuids), done, self._op_failed
            )
        else:
            self._write(
                functools.partial(taskwarrior.command, uuids, "duplicate"),
                t("msg.duplicated_many"),
            )

    def _append_like(self, uuids: list[str], verb: str, title: str) -> None:
        if not uuids:
            return
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(self, title, t("prompt.append.label"))
        text = text.strip()
        if not ok or not text:
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=title,
            body=t("confirm.append.body", text=text, verb=title),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, verb, [text]),
            t("msg.description_updated"),
        )

    def _annotate_bulk(self, uuids: list[str]) -> None:
        if not uuids:
            return
        from PyQt6.QtWidgets import QInputDialog

        title = t("verb.annotate")
        text, ok = QInputDialog.getText(self, title, t("detail.annotation.new"))
        text = text.strip()
        if not ok or not text:
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=title,
            body=t("confirm.append.body", text=text, verb=title),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, "annotate", [text]),
            t("msg.note_added"),
        )

    def _purge(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if not confirm(
            self,
            title=t("confirm.purge.title"),
            body=(
                t("confirm.purge.body")
            ),
            count=len(uuids),
            destructive=True,
            confirm_label=t("confirm.purge.ok"),
            require_phrase=t("confirm.purge.phrase"),
        ):
            return
        self._write(
            functools.partial(taskwarrior.purge, uuids), t("msg.purged")
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
            self.statusBar().showMessage(t("msg.no_change_selected"), 2000)
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=t("confirm.bulk.title"),
            body=t("confirm.bulk.body", mods=" ".join(mods)),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", mods),
            t("msg.tasks_updated"),
        )

    def _start_stop(self, uuid: str, start: bool) -> None:
        self._write(
            functools.partial(taskwarrior.command, [uuid], "start" if start else "stop"),
            t("msg.timer_updated"),
        )

    def _toggle_star(self, uuid: str, on: bool) -> None:
        self._write(
            functools.partial(
                taskwarrior.command, [uuid], "modify",
                ["+starred" if on else "-starred"],
            ),
            t("msg.starred") if on else t("msg.unstarred"),
        )

    def _inline_edit(self, uuid: str, field: str, value: str) -> None:
        mod = f"{field}:{value}"  # empty value clears the attribute
        self._write(
            functools.partial(taskwarrior.command, [uuid], "modify", [mod]),
            t("msg.task_updated"),
        )

    def _save_task(self, uuid: str, mods: list[str]) -> None:
        # The detail panel already emits Taskwarrior-ready tokens: its Jalali
        # date pickers hand back Gregorian strings, so mods must NOT be run
        # through rewrite_args again (that would reject the Gregorian dates).
        self._write(
            functools.partial(taskwarrior.command, [uuid], "modify", mods),
            t("msg.task_updated"),
        )

    def _undo(self) -> None:
        """Show what the last transaction reverts, then confirm before applying."""
        self._begin_busy(t("op.undo_preparing"))
        submit(taskwarrior.undo_preview, self._confirm_undo, self._on_load_error)

    def _confirm_undo(self, preview: dict) -> None:
        self._end_busy()
        if preview.get("empty"):
            self._op_status.idle()
            self.statusBar().showMessage(t("msg.nothing_to_undo"), 2500)
            return
        ok = confirm(
            self,
            title=t("confirm.undo.title"),
            body=(
                t("confirm.undo.body")
            ),
            count=preview.get("count"),
            count_noun=t("confirm.undo.noun"),
            destructive=True,
            confirm_label=t("confirm.undo.ok"),
            details=preview.get("text"),
        )
        if ok:
            self._write(
                functools.partial(taskwarrior.run, ["undo"]), t("msg.undo_done")
            )

    def _change_context(self, name: str) -> None:
        self._write(
            functools.partial(taskwarrior.context_activate, name or None),
            t("msg.context_changed"),
        )

    # --- theme --------------------------------------------

    def _sync_theme_action(self) -> None:
        nxt = other_theme(self.settings.theme)
        glyph = "theme_light" if nxt == "light" else "theme_dark"
        self._theme_action.setIcon(icons.icon(glyph))
        self._theme_action.setText(t("theme.switch_label", name=t(f"theme.{nxt}")))
        self._theme_action.setToolTip(t("theme.switch_tip", name=t(f"theme.{nxt}")))

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
        self._table.set_theme(name)
        self._detail.set_theme(name)
        self._sidebar.retint()
        self._filter_bar.retint()
        self._reports.set_theme(name)
        self._board.set_theme(name)
        self._sync_theme_action()
        self._undo_action.setIcon(icons.icon("undo"))
        self._settings_action.setIcon(icons.icon("settings"))
        self._console_action.setIcon(icons.icon("console"))
        self._add_full_action.setIcon(icons.icon("add", "primary_fg"))
        self._log_action.setIcon(icons.icon("completed"))
        self._manage_action.setIcon(icons.icon("manage"))
        self._tools_action.setIcon(icons.icon("tools"))
        self._data_btn.setIcon(icons.icon("data"))
        self._export_action.setIcon(icons.icon("export"))
        self._import_action.setIcon(icons.icon("import"))
        self._sync_action.setIcon(icons.icon("sync"))

    def _after_console_command(self) -> None:
        """A mutating command ran in the console — re-read everything so the
        change (a new context, task, config value…) shows immediately.
        ``refresh_all`` already drops the lookup caches."""
        self.refresh_all()
        self._toast.show_message(t("msg.console_synced"))

    def _toggle_console(self, visible: bool) -> None:
        self._console_dock.setVisible(visible)
        self.settings.console_visible = visible

    def _collect_commands(self) -> list:
        from .widgets.command_palette import Command

        cmds: list[Command] = []
        seen: set[str] = set()
        for act in self.findChildren(QAction):
            text = act.text().replace("&", "").strip()
            if not text or act.isSeparator() or not act.isEnabled() or text in seen:
                continue
            seen.add(text)
            sc = act.shortcut().toString()
            cmds.append(
                Command(text, t("palette.cat.action"), act.trigger, hint=sc)
            )
        for label, section, spec in self._sidebar.navigation_targets():
            if spec.get("kind") == "saved":
                continue  # added from settings below, with a stable category
            cmds.append(
                Command(
                    label, section or t("palette.cat.view"),
                    functools.partial(self._sidebar.activate_spec, spec),
                )
            )
        for name, raw in self.settings.saved_filters().items():
            cmds.append(
                Command(
                    name, t("palette.cat.filter"),
                    functools.partial(self._apply_saved_filter, raw),
                )
            )
        for name in self._board_names():
            cmds.append(
                Command(name, t("status.boards"),
                        functools.partial(self._show_board, name))
            )
        return cmds

    def _open_command_palette(self) -> None:
        from .widgets.command_palette import CommandPalette

        pal = CommandPalette(self._collect_commands(), self)
        pal.move(
            self.geometry().center().x() - pal.width() // 2,
            self.geometry().top() + self.height() // 6,
        )
        pal.exec()

    def _open_shortcut_sheet(self) -> None:
        from PyQt6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QTextEdit

        # "?" must not fire while the user is typing it into a field
        fw = self.focusWidget()
        if isinstance(fw, QLineEdit | QComboBox | QTextEdit | QPlainTextEdit):
            return
        from .widgets.shortcut_sheet import ShortcutSheet

        ShortcutSheet(self).exec()

    def _focus_filter(self) -> None:
        self._filter_bar._edit.setFocus()
        self._filter_bar._edit.selectAll()

    _FN_COUNT_FILTER = {
        "report_ready": ["+READY"],
        "report_waiting": ["+WAITING"],
        "report_blocked": ["+BLOCKED"],
        "report_completed": ["status:completed"],
    }

    def _view_counts(self) -> dict:
        """Match counts for the quick views + saved filters (runs off-thread)."""
        import shlex

        from .widgets.sidebar import QUICK_VIEWS

        out: dict[str, int] = {}
        for _lbl, _glyph, spec in QUICK_VIEWS:
            if spec.get("fn"):
                flt = self._FN_COUNT_FILTER.get(spec["fn"])
                if flt is None:
                    continue
            else:
                flt = spec.get("filter")
                flt = flt() if callable(flt) else list(flt or [])
            out[spec["key"]] = taskwarrior.count(flt)
        for name, raw in self.settings.saved_filters().items():
            try:
                out[name] = taskwarrior.count(shlex.split(raw))
            except ValueError:
                out[name] = taskwarrior.count(raw.split())
        return out

    def _goto_view(self, key: str) -> None:
        from .widgets.sidebar import QUICK_VIEWS

        for label_key, _glyph, spec in QUICK_VIEWS:
            if spec.get("key") == key:
                self._sidebar.activate_spec(dict(spec, title=t(label_key)))
                return

    def _open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            set_digit_mode(self.settings.persian_digits)
            self._model.set_persian_digits(self.settings.persian_digits)
            self._model.set_due_soon_days(self.settings.due_soon_days)
            self._table.set_density(self.settings.density)
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
        self._begin_busy(t("op.applying"))

        def done(_result):
            self._end_busy()
            self._op_status.success(success_msg)
            self.statusBar().showMessage(success_msg, 2500)
            self._toast.show_message(success_msg)
            self.refresh_all()

        submit(fn, done, self._op_failed)

    def _op_failed(self, err: object) -> None:
        self._end_busy()
        self._op_status.failed(t("op.failed"))
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
        self._enforce_sidebar_side()
        self._console_action.setChecked(self._console_dock.isVisible())

    def _enforce_sidebar_side(self) -> None:
        """The nav sidebar always sits on the reading-start edge for the current
        language — right for RTL (fa), left for LTR (en). A persisted dock
        layout from another language (or an older build) must never win here."""
        from .i18n import is_rtl

        want = (
            Qt.DockWidgetArea.RightDockWidgetArea
            if is_rtl()
            else Qt.DockWidgetArea.LeftDockWidgetArea
        )
        if (
            self._sidebar_dock.isFloating()
            or self.dockWidgetArea(self._sidebar_dock) != want
        ):
            self.addDockWidget(want, self._sidebar_dock)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._toast.parent_resized()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings.save_window(
            self.saveGeometry(), self.saveState(), language=self._built_language
        )
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
                "jtask", t("tray.background"),
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
