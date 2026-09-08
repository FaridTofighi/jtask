"""Navigation sidebar: quick views, boards, projects, tags.

Reports & Charts, saved filters and contexts live in the toolbar (sidebar IA
redesign). Projects and Tags stay here but compress — a search field + a
capped list for projects, a wrapped chip flow for tags — so the sidebar
stays short however many accumulate.
"""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QLineEdit,
    QScrollArea,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from .. import fmt, icons
from ..calendar_system import active
from ..i18n import t
from ..theme import palette
from ..tw_color import to_hex
from .flow_layout import FlowWidget

_SPEC_ROLE = Qt.ItemDataRole.UserRole
_ICON_ROLE = Qt.ItemDataRole.UserRole + 5
_SECTION_ROLE = Qt.ItemDataRole.UserRole + 6
_COLOUR_ROLE = Qt.ItemDataRole.UserRole + 7
_STUCK_ROLE = Qt.ItemDataRole.UserRole + 8
UUID_MIME = "application/x-jtask-uuids"

_PROJ_CAP = 5      # projects shown before "show all"
_TAG_CAP_ROWS = 3  # chip rows shown before "show all"


class _TagChip(QToolButton):
    """A tag pill in the compressed Tags section — clickable to filter,
    right-click for rename/remove, and a drop target for tasks (add the
    tag), keeping the vertical-list behaviour it replaced."""

    activateRequested = pyqtSignal()
    menuRequested = pyqtSignal(object)   # global QPoint
    tasksDropped = pyqtSignal(list)      # uuids

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TagChip")
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.menuRequested.emit(self.mapToGlobal(pos))
        )
        self.clicked.connect(self.activateRequested)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(UUID_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(UUID_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        uuids = bytes(event.mimeData().data(UUID_MIME)).decode().split()
        if uuids:
            self.tasksDropped.emit(uuids)
            event.acceptProposedAction()


def _colour_dot(hex_colour: str, size: int = 10) -> QIcon:
    """A filled round swatch as a row icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(hex_colour))
    p.drawEllipse(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


def _badged_icon(base: QIcon, badge_hex: str, size: int = 16) -> QIcon:
    """*base* with a small filled dot in the bottom-right — the stuck-project
    marker, in the ``blocked`` state colour."""
    pm = base.pixmap(size, size)
    if pm.isNull():
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(badge_hex))
    d = max(6, size // 2)
    p.drawEllipse(size - d, size - d, d - 1, d - 1)
    p.end()
    return QIcon(pm)


def _this_week_filter() -> list[str]:
    start, end = active().week_bounds()
    g_start = start - datetime.timedelta(days=1)
    g_end = end + datetime.timedelta(days=1)
    return [
        f"due.after:{g_start:%Y-%m-%d}",
        f"due.before:{g_end:%Y-%m-%d}",
        "status:pending",
    ]


# (label_key, icon/stable key, spec). The spec's ``key`` is the stable identity
# used by the empty-state lookup; ``title`` is the localized display label.
QUICK_VIEWS = [
    ("view.starred", "star",
     {"kind": "filter", "key": "starred",
      "filter": ["+starred", "status:pending"]}),
    ("view.today", "today",
     {"kind": "filter", "key": "today",
      "filter": ["due:today", "status:pending"]}),
    ("view.week", "week",
     {"kind": "filter", "key": "week", "filter": _this_week_filter}),
    ("view.overdue", "overdue",
     {"kind": "filter", "key": "overdue", "filter": ["+OVERDUE"]}),
    ("view.next", "next",
     {"kind": "report", "key": "next", "fn": "report_ready"}),
    ("view.waiting", "waiting",
     {"kind": "report", "key": "waiting", "fn": "report_waiting"}),
    ("view.blocked", "blocked",
     {"kind": "report", "key": "blocked", "fn": "report_blocked"}),
    ("view.completed", "completed",
     {"kind": "report", "key": "completed", "fn": "report_completed"}),
]


class Sidebar(QTreeWidget):
    """Emits ``activated(dict)`` describing the view the user picked."""

    activated = pyqtSignal(dict)
    tasksDroppedOnProject = pyqtSignal(list, str)  # (uuids, project)
    tasksDroppedOnTag = pyqtSignal(list, str)  # (uuids, tag) — add the tag
    tagRenameRequested = pyqtSignal(str, str)  # (old, new) — across all tasks
    tagRemoveRequested = pyqtSignal(str)  # tag — strip from all tasks
    projectRenameRequested = pyqtSignal(str, str)  # (old, new) — incl. sub-projects
    projectDeleteRequested = pyqtSignal(str)  # project — delete it and its sub-tasks
    projectColorRequested = pyqtSignal(str, str)  # (project, taskwarrior colour string)
    projectColorClearRequested = pyqtSignal(str)  # project — unset its colour
    boardActivated = pyqtSignal(str)        # board name
    boardManageRequested = pyqtSignal()
    addNextActionRequested = pyqtSignal(str)  # project — open Add Task pre-filled

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setHeaderHidden(True)
        self.setIndentation(10)
        self.setColumnCount(1)
        self.setUniformRowHeights(False)  # the tag chip-flow row is taller
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(False)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemClicked.connect(self._on_click)

        self._quick = self._section(t("sidebar.section.quick"))
        for label_key, glyph, spec in QUICK_VIEWS:
            spec = dict(spec, title=t(label_key))
            self._leaf(self._quick, t(label_key), spec, glyph)

        gap = QTreeWidgetItem([""])
        gap.setFlags(Qt.ItemFlag.NoItemFlags)
        gap.setSizeHint(0, QSize(1, 10))
        self.addTopLevelItem(gap)

        # Reports & Charts, saved filters and contexts moved to the toolbar
        # (sidebar IA redesign) — the sidebar keeps only navigation that grows
        # with the data: quick views, boards, projects, tags.
        self._boards = self._section(t("sidebar.section.boards"))

        self._projects = self._section(t("sidebar.section.projects"))
        self._project_items: list[QTreeWidgetItem] = []
        self._projects_expanded = False
        self._build_project_scaffold()

        self._tags = self._section(t("sidebar.section.tags"))
        self._tag_specs: list[tuple[str, dict]] = []
        self._tags_expanded = False
        self._build_tag_scaffold()

        self.expandAll()
        self.retint()

    # --- projects / tags scaffolding (persist across populate) -----

    def _build_project_scaffold(self) -> None:
        row = QTreeWidgetItem([""])
        row.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._projects.addChild(row)
        self._proj_search = QLineEdit()
        self._proj_search.setObjectName("SidebarSearch")
        self._proj_search.setPlaceholderText(t("sidebar.search.projects"))
        self._proj_search.setClearButtonEnabled(True)
        self._proj_search.textChanged.connect(self._apply_project_filter)
        self.setItemWidget(row, 0, self._proj_search)

        self._proj_more = QTreeWidgetItem([""])
        self._proj_more.setData(0, _SPEC_ROLE, {"kind": "expander", "target": "projects"})
        self._projects.addChild(self._proj_more)
        self._proj_more.setHidden(True)

    def _build_tag_scaffold(self) -> None:
        row = QTreeWidgetItem([""])
        row.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._tags.addChild(row)
        self._tag_flow = FlowWidget(hspacing=4, vspacing=4)
        self._tag_scroll = QScrollArea()
        self._tag_scroll.setObjectName("SidebarChips")
        self._tag_scroll.setWidgetResizable(True)
        self._tag_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tag_scroll.setWidget(self._tag_flow)
        self._tag_row = row
        self.setItemWidget(row, 0, self._tag_scroll)

        self._tag_more = QTreeWidgetItem([""])
        self._tag_more.setData(0, _SPEC_ROLE, {"kind": "expander", "target": "tags"})
        self._tags.addChild(self._tag_more)
        self._tag_more.setHidden(True)

    # --- build helpers ------------------------------------------

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([title])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setData(0, _SECTION_ROLE, True)
        font = item.font(0)
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() - 1)
        font.setLetterSpacing(font.SpacingType.PercentageSpacing, 105)
        item.setFont(0, font)
        self.addTopLevelItem(item)
        return item

    def _leaf(self, parent, label: str, spec: dict, glyph: str | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, _SPEC_ROLE, spec)
        if glyph:
            item.setData(0, _ICON_ROLE, glyph)
        if parent is not None:
            parent.addChild(item)
        return item

    def retint(self) -> None:
        """Re-tint row icons and section captions for the active theme."""
        pal = palette(icons._theme)
        muted = QColor(pal["text_muted"])
        for item in self._iter_items(self.invisibleRootItem()):
            tw = item.data(0, _COLOUR_ROLE)
            glyph = item.data(0, _ICON_ROLE)
            hx = to_hex(tw) if tw else None
            if hx:
                base = _colour_dot(hx)
            elif glyph:
                base = icons.icon(glyph, "text_muted")
            else:
                base = None
            if base is not None:
                if item.data(0, _STUCK_ROLE):
                    base = _badged_icon(base, pal["blocked"])
                item.setIcon(0, base)
            if item.data(0, _SECTION_ROLE):
                item.setForeground(0, muted)
        self._hint_colour = muted

    def _iter_items(self, root):
        for i in range(root.childCount()):
            child = root.child(i)
            yield child
            yield from self._iter_items(child)

    def navigation_targets(self) -> list[tuple[str, str, dict]]:
        """``(label, section, spec)`` for every activatable row — feeds the
        command palette."""
        out: list[tuple[str, str, dict]] = []
        for item in self._iter_items(self.invisibleRootItem()):
            spec = item.data(0, _SPEC_ROLE)
            if not isinstance(spec, dict) or item.data(0, _SECTION_ROLE):
                continue
            if spec.get("kind") == "expander":
                continue
            parent = item.parent()
            section = parent.text(0) if parent is not None else ""
            out.append((item.text(0).split("  ·")[0].strip(), section, spec))
        # tag chips are not tree items — surface them for the palette too
        for label, spec in getattr(self, "_tag_specs", []):
            out.append((label, self._tags.text(0), dict(spec)))
        return out

    # --- dynamic population ------------------------------------

    def populate_projects(
        self, rows: list[dict], colors: dict[str, str] | None = None
    ) -> None:
        colors = colors or {}
        for it in self._project_items:  # drop only the leaves, keep search + "more"
            self._projects.removeChild(it)
        self._project_items = []
        insert_at = 1  # child(0) is the search row
        for row in rows:
            name = row["project"]
            label = f"{name}  ·  {fmt.num(row['open'])}"
            spec = {
                "kind": "filter",
                "drop": "project",
                "title": name,
                "filter": [f"project:{name}", "status:pending"],
            }
            item = QTreeWidgetItem([label])
            item.setData(0, _SPEC_ROLE, spec)
            item.setData(0, _ICON_ROLE, "project")
            tw = colors.get(name, "")
            if tw:
                item.setData(0, _COLOUR_ROLE, tw)
                item.setToolTip(0, t("project_color.tooltip", color=tw))
            if row.get("stuck"):
                item.setData(0, _STUCK_ROLE, True)
                item.setToolTip(0, t("sidebar.project_stuck.tip"))
            self._projects.insertChild(insert_at, item)
            insert_at += 1
            self._project_items.append(item)
        # keep the "show all / less" row last
        self._projects.removeChild(self._proj_more)
        self._projects.addChild(self._proj_more)
        self._apply_project_filter(self._proj_search.text())
        self.retint()

    def _apply_project_filter(self, text: str) -> None:
        q = text.strip().lower()
        matches = [it for it in self._project_items if q in it.text(0).lower()]
        over_cap = len(self._project_items) > _PROJ_CAP and not q
        for it in self._project_items:
            if it not in matches:
                it.setHidden(True)
            elif over_cap and not self._projects_expanded:
                it.setHidden(matches.index(it) >= _PROJ_CAP)
            else:
                it.setHidden(False)
        if over_cap:
            self._proj_more.setHidden(False)
            hidden = max(0, len(matches) - _PROJ_CAP)
            self._proj_more.setText(
                0,
                t("sidebar.show_less") if self._projects_expanded
                else t("sidebar.show_all", n=fmt.num(hidden)),
            )
        else:
            self._proj_more.setHidden(True)

    def populate_tags(self, rows: list[dict]) -> None:
        while self._tag_flow.flow.count():
            w = self._tag_flow.flow.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._tag_specs = []
        for row in rows:
            tag = row["tag"]
            spec = {
                "kind": "filter",
                "drop": "tag",
                "tag": tag,
                "title": f"#{tag}",
                "filter": [f"+{tag}", "status:pending"],
            }
            chip = _TagChip(f"#{tag}  ·  {fmt.num(row['count'])}")
            chip.setToolTip(f"#{tag}")
            chip.activateRequested.connect(lambda s=dict(spec): self.activate_spec(s))
            chip.menuRequested.connect(lambda gp, tg=tag: self._show_tag_menu(tg, gp))
            chip.tasksDropped.connect(
                lambda uuids, tg=tag: self.tasksDroppedOnTag.emit(uuids, tg)
            )
            self._tag_flow.flow.addWidget(chip)
            self._tag_specs.append((f"#{tag}", spec))
        self._apply_tag_cap()
        self.retint()

    def _apply_tag_cap(self) -> None:
        import math

        n = len(self._tag_specs)
        row_h = 26  # ~ one chip row including spacing
        cap_px = _TAG_CAP_ROWS * row_h
        vw = max(self._tag_scroll.viewport().width(), 160)
        # deterministic row estimate — the exact flow height isn't known until
        # the chips are polished, but the *decision* to cap only needs a guess
        per_row = max(1, vw // 92)
        rows = math.ceil(n / per_row) if n else 0
        over = rows > _TAG_CAP_ROWS
        if self._tags_expanded or not over:
            self._tag_scroll.setMinimumHeight(0)
            self._tag_scroll.setMaximumHeight(16_777_215)
            height = max(row_h, self._tag_flow.flow.heightForWidth(vw), rows * row_h)
        else:
            height = cap_px
        self._tag_scroll.setFixedHeight(int(height))
        self._tag_row.setSizeHint(0, QSize(1, int(height) + 6))
        self._tag_more.setHidden(not over)
        if over:
            self._tag_more.setText(
                0,
                t("sidebar.show_less") if self._tags_expanded
                else t("sidebar.show_all", n=fmt.num(n)),
            )

    def resizeEvent(self, event):  # noqa: N802 - re-measure the wrapping chips
        super().resizeEvent(event)
        if getattr(self, "_tag_specs", None) is not None:
            self._apply_tag_cap()

    def populate_boards(self, names: list[str]) -> None:
        self._boards.takeChildren()
        for name in names:
            self._leaf(self._boards, name,
                       {"kind": "board", "name": name}, "board")
        manage = self._leaf(
            self._boards, t("sidebar.boards.manage"),
            {"kind": "board_manage"}, "settings",
        )
        f = manage.font(0)
        f.setItalic(True)
        manage.setFont(0, f)
        self.retint()

    def set_view_counts(self, counts: dict[str, int]) -> None:
        """Append ``· N`` to the quick-view rows (keyed by spec key)."""
        for item in self._iter_items(self._quick):
            spec = item.data(0, _SPEC_ROLE)
            if isinstance(spec, dict) and spec.get("key") in counts:
                n = counts[spec["key"]]
                item.setText(0, f"{spec['title']}  ·  {fmt.num(n)}")

    # --- drag & drop -----------------------------------------

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(UUID_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        spec = item.data(0, _SPEC_ROLE) if item else None
        if (
            event.mimeData().hasFormat(UUID_MIME)
            and spec
            and spec.get("drop") in ("project", "tag")
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        spec = item.data(0, _SPEC_ROLE) if item else None
        if not spec:
            return
        uuids = bytes(event.mimeData().data(UUID_MIME)).decode().split()
        if not uuids:
            return
        if spec.get("drop") == "project" and spec.get("title"):
            self.tasksDroppedOnProject.emit(uuids, spec["title"])
            event.acceptProposedAction()
        elif spec.get("drop") == "tag" and spec.get("tag"):
            self.tasksDroppedOnTag.emit(uuids, spec["tag"])
            event.acceptProposedAction()

    # --- context menu (saved filters + tags + projects) ------

    def _context_menu(self, pos) -> None:
        from PyQt6.QtWidgets import QInputDialog, QMenu

        item = self.itemAt(pos)
        spec = item.data(0, _SPEC_ROLE) if item else None
        if not spec:
            return

        if spec.get("drop") == "project":
            name = spec["title"]
            current = item.data(0, _COLOUR_ROLE) or ""
            menu = QMenu(self)
            act_rename = menu.addAction(t("sidebar.menu.project_rename"))
            act_color = menu.addAction(t("sidebar.menu.project_color"))
            act_color_clear = menu.addAction(t("sidebar.menu.project_color_clear"))
            act_color_clear.setEnabled(bool(current))
            menu.addSeparator()
            act_next = menu.addAction(t("sidebar.menu.project_add_next"))
            menu.addSeparator()
            act_delete = menu.addAction(t("sidebar.menu.project_delete"))
            chosen = menu.exec(self.viewport().mapToGlobal(pos))
            if chosen == act_next:
                self.addNextActionRequested.emit(name)
            elif chosen == act_rename:
                new, ok = QInputDialog.getText(
                    self, t("sidebar.project_rename.title"),
                    t("sidebar.project_rename.label", project=name), text=name,
                )
                new = new.strip().rstrip(".")
                if ok and new and new != name:
                    self.projectRenameRequested.emit(name, new)
            elif chosen == act_color:
                from .project_color_dialog import ProjectColorDialog

                dlg = ProjectColorDialog(name, current, self)
                if dlg.exec() and (res := dlg.result_color()) is not None:
                    if res:
                        self.projectColorRequested.emit(name, res)
                    else:
                        self.projectColorClearRequested.emit(name)
            elif chosen == act_color_clear:
                self.projectColorClearRequested.emit(name)
            elif chosen == act_delete:
                self.projectDeleteRequested.emit(name)
            return

    def _show_tag_menu(self, tag: str, global_pos) -> None:
        from PyQt6.QtWidgets import QInputDialog, QMenu

        menu = QMenu(self)
        act_rename = menu.addAction(t("sidebar.menu.tag_rename"))
        act_remove = menu.addAction(t("sidebar.menu.tag_remove"))
        chosen = menu.exec(global_pos)
        if chosen == act_rename:
            new, ok = QInputDialog.getText(
                self, t("sidebar.tag_rename.title"),
                t("sidebar.tag_rename.label", tag=tag), text=tag,
            )
            new = new.strip().lstrip("#+")
            if ok and new and new != tag:
                self.tagRenameRequested.emit(tag, new)
        elif chosen == act_remove:
            self.tagRemoveRequested.emit(tag)

    # --- events -----------------------------------------------

    def _on_click(self, item: QTreeWidgetItem, _column: int) -> None:
        spec = item.data(0, _SPEC_ROLE)
        if not spec:
            return
        if spec.get("kind") == "expander":
            self._toggle_expander(spec["target"])
            return
        self.activate_spec(spec)

    def _toggle_expander(self, target: str) -> None:
        if target == "projects":
            self._projects_expanded = not self._projects_expanded
            self._apply_project_filter(self._proj_search.text())
        elif target == "tags":
            self._tags_expanded = not self._tags_expanded
            self._apply_tag_cap()

    def activate_spec(self, spec: dict) -> None:
        """Route a sidebar spec to the right signal — shared by clicks and the
        command palette."""
        if spec.get("kind") == "board":
            self.boardActivated.emit(spec["name"])
            return
        if spec.get("kind") == "board_manage":
            self.boardManageRequested.emit()
            return
        resolved = dict(spec)
        flt = resolved.get("filter")
        if callable(flt):
            resolved["filter"] = flt()
        self.activated.emit(resolved)
