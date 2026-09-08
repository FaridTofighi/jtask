"""The application shell: sidebar, task table, detail panel, console, toolbars."""

from __future__ import annotations

import functools
import logging

from PyQt6.QtCore import QEasingCurve, QSize, Qt, QVariantAnimation
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
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
from . import tokens as tok
from .i18n import t
from .mixins.boards import BoardsMixin
from .mixins.console_palette import ConsolePaletteMixin
from .mixins.data_safety import DataSafetyMixin
from .mixins.detail_panel import DetailPanelMixin
from .mixins.review import ReviewWizardMixin
from .mixins.tags_projects import TagsProjectsMixin
from .mixins.task_lifecycle import TaskLifecycleMixin
from .mixins.theme import ThemeMixin
from .mixins.tray import TrayMixin
from .mixins.triage import TriageModeMixin
from .models.task_model import TaskTableModel
from .settings import Settings
from .theme import render_qss
from .widgets.annotations_view import AnnotationsView
from .widgets.command_console import CommandConsole
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
_MIN_SIZE = QSize(940, 620)


class MainWindow(
    QMainWindow,
    BoardsMixin,
    ConsolePaletteMixin,
    DataSafetyMixin,
    DetailPanelMixin,
    ReviewWizardMixin,
    TagsProjectsMixin,
    TaskLifecycleMixin,
    ThemeMixin,
    TrayMixin,
    TriageModeMixin,
):
    """The application shell. Owns construction/wiring and the central
    data-flow + write funnel; everything else is composed in from the
    ``mixins/`` package above — see ``docs/jtask-gui-design.md`` for the
    map of which mixin owns which feature area."""

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
        self._pending_reselect: set[str] = set()
        self._pending_ops = 0

        self._model = TaskTableModel(
            self.settings.theme,
            self.settings.persian_digits,
            self.settings.due_soon_days,
        )
        self._table = TaskTable(self._model)
        self._table.set_density(self.settings.density)
        # restore a persisted column layout (written on close) — the merged
        # "نمایش" toolbar control is the only editor of column visibility
        _col_order, _col_hidden, _ = self.settings.columns()
        if _col_order:
            self._model.set_columns([k for k in _col_order if k not in _col_hidden])
        self._detail = DetailPanel()
        self._history_view = TaskHistoryView()
        self._raw_view = RawDataView()
        self._annotations_view = AnnotationsView()
        self._reports = ReportsView(self.settings.theme)
        from .widgets.board_view import BoardView
        self._board = BoardView(self.settings.theme)
        self._board_mode = False
        self._group_key = "none"

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

        from .widgets.triage_view import TriageView

        self._triage = TriageView()
        self._content.addWidget(self._split)     # index 0: tasks (table)
        self._content.addWidget(self._reports)   # index 1: reports & charts
        self._content.addWidget(self._board)     # index 2: board engine
        self._content.addWidget(self._triage)    # index 3: triage mode

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

        # the active-context indicator leads row one — a global mode, visually
        # separate from row two's navigation clusters (sidebar IA redesign)
        from .widgets.context_pill import ContextPill

        self._context_pill = ContextPill()
        row1.addWidget(self._context_pill)
        row1.addSeparator()

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

        from PyQt6.QtWidgets import QMenu, QToolButton

        # one control folding "group by" + column show/hide (was two toolbar
        # widgets: the group combo + a Settings-only column reset)
        self._view_btn = QToolButton()
        self._view_btn.setIcon(icons.icon("view"))
        self._view_btn.setText(t("toolbar.view"))
        self._view_btn.setToolTip(t("toolbar.view.tip"))
        self._view_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._view_btn.setMenu(self._build_view_menu())
        row2.addWidget(self._view_btn)

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

        # -- view cluster: reports + saved filters + theme/console toggles
        self._reports_action = QAction(
            icons.icon("reports"), t("status.reports").replace("&", "&&"), self
        )
        self._reports_action.setToolTip(t("action.reports.tip"))
        self._reports_action.triggered.connect(
            lambda: self._on_view_selected({"kind": "reports", "title": t("status.reports")})
        )
        row2.addAction(self._reports_action)

        self._filters_btn = QToolButton()
        self._filters_btn.setIcon(icons.icon("star_outline"))
        self._filters_btn.setToolTip(t("action.filters.tip"))
        self._filters_btn.clicked.connect(self._open_saved_filter_menu)
        row2.addWidget(self._filters_btn)
        # pinned-filter chips are inserted just before this anchor
        self._pin_anchor = row2.addSeparator()
        self._pin_chips: list = []
        self._saved_filter_menu = None
        self._saved_counts: dict = {}

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

        # the weekly-review pass lives in the GTD board's own header (it only
        # applies there); the action stays window-level for Ctrl+R + the palette
        self._review_action = QAction(icons.icon("review"), t("action.review"), self)
        self._review_action.setToolTip(t("action.review.tip"))
        self._review_action.setShortcut(QKeySequence("Ctrl+R"))
        self._review_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self._review_action.triggered.connect(self._open_review)
        self.addAction(self._review_action)

        self._triage_action = QAction(icons.icon("triage"), t("action.triage"), self)
        self._triage_action.setToolTip(t("action.triage.tip"))
        self._triage_action.setShortcut(QKeySequence("Ctrl+Shift+I"))
        self._triage_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self._triage_action.triggered.connect(lambda: self._start_triage())
        row2.addAction(self._triage_action)

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

    # --- the merged "نمایش" control: grouping + column visibility ----

    def _build_view_menu(self):
        from PyQt6.QtGui import QActionGroup
        from PyQt6.QtWidgets import QMenu

        from .models.column_spec import COLUMNS

        menu = QMenu(self)

        head = menu.addAction(t("toolbar.group_by"))
        head.setEnabled(False)
        grp = QActionGroup(menu)
        grp.setExclusive(True)
        self._group_actions: dict[str, QAction] = {}
        for label, key in [
            (t("group.none"), "none"), (t("group.project"), "project"),
            (t("group.priority"), "priority"), (t("group.due_week"), "due"),
            (t("group.status"), "status"),
        ]:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == self._group_key)
            act.triggered.connect(lambda _c=False, k=key: self._set_group_key(k))
            grp.addAction(act)
            self._group_actions[key] = act

        menu.addSeparator()
        col_head = menu.addAction(t("view.menu.columns"))
        col_head.setEnabled(False)
        visible = set(self._model.visible_columns())
        self._col_actions: dict[str, QAction] = {}
        for col in COLUMNS:
            if not col.header:  # the marker columns (⭐ / indicators) always stay
                continue
            act = menu.addAction(col.header)
            act.setCheckable(True)
            act.setChecked(col.key in visible)
            if col.key == "description":
                act.setEnabled(False)  # the stretch column is not hideable
            act.toggled.connect(lambda _c=False, k=col.key: self._toggle_column(k))
            self._col_actions[col.key] = act

        menu.aboutToShow.connect(self._sync_view_menu)
        return menu

    def _set_group_key(self, key: str) -> None:
        self._group_key = key
        self._table.set_group_key(key)

    def _toggle_column(self, _key: str) -> None:
        from .models.column_spec import COLUMNS

        checked = {
            k for k, act in self._col_actions.items() if act.isChecked()
        }
        checked.add("description")
        keys = [c.key for c in COLUMNS if not c.header or c.key in checked]
        self._model.set_columns(keys)
        self.settings.save_columns(keys, [], {})

    def _sync_view_menu(self) -> None:
        for key, act in self._group_actions.items():
            act.setChecked(key == self._group_key)
        visible = set(self._model.visible_columns())
        for key, act in self._col_actions.items():
            act.blockSignals(True)
            act.setChecked(key in visible)
            act.blockSignals(False)

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
        self._context_pill.contextChangeRequested.connect(self._change_context)
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
        self._sidebar.boardActivated.connect(self._show_board)
        self._sidebar.boardManageRequested.connect(self._open_board_manager)
        self._filter_bar.saveRequested.connect(self._save_filter)
        self._detail.closed.connect(self._hide_detail)
        self._detail.closed.connect(self._after_triage_edit)
        self._detail.saveRequested.connect(self._save_task)
        self._detail.starToggled.connect(self._toggle_star)
        self._detail.startStopRequested.connect(self._start_stop)
        self._detail.doneRequested.connect(
            lambda u: self._bulk([u], "done", t("msg.tasks_done"))
        )
        self._detail.deleteRequested.connect(lambda u: self._delete([u]))
        self._model.cellEdited.connect(self._inline_edit)
        self._model.starToggled.connect(self._toggle_star)
        self._board.boardDrop.connect(self._board_drop)
        self._board.starToggled.connect(self._toggle_star)
        self._board.taskActivated.connect(self._open_card)
        self._board.triageRequested.connect(self._start_triage)
        self._board.columnSortChanged.connect(self._persist_column_sort)
        self._board.reviewRequested.connect(self._open_review)

        self._triage.decision.connect(self._triage_decision)
        self._triage.projectAssigned.connect(self._triage_project)
        self._triage.editRequested.connect(self._triage_edit)
        self._triage.deleteRequested.connect(self._triage_delete)
        self._triage.exited.connect(self._exit_triage)
        self._return_to_triage = False

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

    # --- data flow ------------------------------------------

    def refresh_all(self) -> None:
        # remember who was selected — a refresh rebuilds the table model
        # wholesale (Qt drops selection on a model reset), so row-index
        # continuity can't be relied on; reselect by uuid once reloaded.
        self._pending_reselect = set(self._table.selected_uuids())
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
            lambda r: self._context_pill.set_state(r[1], r[0]),
            self._error,
        )
        submit(
            taskwarrior.list_projects,
            lambda p: (self._detail.set_projects(p), self._table.set_projects(p)),
            self._error,
        )
        submit(taskwarrior.list_tags, self._detail.set_tag_completions, self._error)
        self._sidebar.populate_boards(self._board_names())
        self._rebuild_pin_chips()
        submit(self._view_counts, self._on_view_counts, lambda _e: None)
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

    def _populate_table(self, tasks: list[dict]) -> None:
        self._end_busy()
        self._model.set_tasks(tasks)
        self._detail.set_all_tasks(tasks)
        self._table.show_empty_state(self._view_spec.get("key", ""), len(tasks) == 0)
        title = self._view_spec.get("title") or t("view.tasks")
        self._status_count.setText(t("status.count", n=fmt.num(len(tasks)), title=title))

        if self._pending_reselect:
            self._table.select_uuids(self._pending_reselect)
            self._pending_reselect = set()
        self._refresh_open_detail(tasks)

    def _refresh_open_detail(self, tasks: list[dict]) -> None:
        """The detail panel must never silently show stale data for the task
        it has open — a write to that task (an annotation added from inside
        the panel, a bulk edit, an undo, anything) is its own trigger to
        reload, independent of whether the table's selection survived."""
        if not self._detail_host.isVisibleTo(self):
            return
        uuid = self._detail.current_uuid()
        if not uuid:
            return
        fresh = next((tk for tk in tasks if tk.get("uuid") == uuid), None)
        if fresh is not None:
            self._show_detail(fresh)
            return
        # the task fell out of the current view's filter (e.g. marked done
        # while viewing "pending") — fetch it directly so the panel still
        # reflects the write instead of going stale until manually reopened.
        submit(
            functools.partial(taskwarrior.export, [uuid]),
            lambda rows: self._show_detail(rows[0]) if rows else None,
            lambda _e: None,
        )

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

    # --- busy / helpers ----------------------------------

    def _begin_busy(self, message: str) -> None:
        self._pending_ops += 1
        self._op_status.running(message)

    def _end_busy(self) -> None:
        self._pending_ops = max(0, self._pending_ops - 1)
        if self._pending_ops == 0 and self._op_status.state == "running":
            self._op_status.idle()

    def _write(self, fn, success_msg: str, *, refresh: bool = True, then=None) -> None:
        self._begin_busy(t("op.applying"))

        def done(_result):
            self._end_busy()
            self._op_status.success(success_msg)
            self.statusBar().showMessage(success_msg, 2500)
            self._toast.show_message(success_msg)
            if refresh:
                self.refresh_all()
            if then is not None:
                then()

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
