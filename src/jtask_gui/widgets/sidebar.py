"""Navigation sidebar: quick views, projects, tags, contexts, reports."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from .. import icons
from ..calendar_system import active
from ..i18n import t
from ..theme import palette
from ..tw_color import to_hex

_SPEC_ROLE = Qt.ItemDataRole.UserRole
_ICON_ROLE = Qt.ItemDataRole.UserRole + 5
_SECTION_ROLE = Qt.ItemDataRole.UserRole + 6
_COLOUR_ROLE = Qt.ItemDataRole.UserRole + 7
_STUCK_ROLE = Qt.ItemDataRole.UserRole + 8
UUID_MIME = "application/x-jtask-uuids"


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
    contextChangeRequested = pyqtSignal(str)  # "" clears the context
    tasksDroppedOnProject = pyqtSignal(list, str)  # (uuids, project)
    tasksDroppedOnTag = pyqtSignal(list, str)  # (uuids, tag) — add the tag
    tagRenameRequested = pyqtSignal(str, str)  # (old, new) — across all tasks
    tagRemoveRequested = pyqtSignal(str)  # tag — strip from all tasks
    projectRenameRequested = pyqtSignal(str, str)  # (old, new) — incl. sub-projects
    projectDeleteRequested = pyqtSignal(str)  # project — delete it and its sub-tasks
    projectColorRequested = pyqtSignal(str, str)  # (project, taskwarrior colour string)
    projectColorClearRequested = pyqtSignal(str)  # project — unset its colour
    savedFilterActivated = pyqtSignal(str)  # raw filter string
    boardActivated = pyqtSignal(str)        # board name
    boardManageRequested = pyqtSignal()
    savedFilterDeleteRequested = pyqtSignal(str)  # name
    savedFilterRenameRequested = pyqtSignal(str, str)  # (old, new)
    addNextActionRequested = pyqtSignal(str)  # project — open Add Task pre-filled

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setHeaderHidden(True)
        self.setIndentation(10)
        self.setColumnCount(1)
        self.setUniformRowHeights(True)
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
        self._saved = self._section(t("sidebar.section.saved"))
        self._projects = self._section(t("sidebar.section.projects"))
        self._tags = self._section(t("sidebar.section.tags"))
        self._contexts = self._section(t("sidebar.section.contexts"))

        self.expandAll()
        self.retint()

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
            parent = item.parent()
            section = parent.text(0) if parent is not None else ""
            out.append((item.text(0).split("  ·")[0].strip(), section, spec))
        return out

    # --- dynamic population ------------------------------------

    def populate_projects(
        self, rows: list[dict], colors: dict[str, str] | None = None
    ) -> None:
        colors = colors or {}
        self._projects.takeChildren()
        for row in rows:
            name = row["project"]
            label = f"{name}  ·  {row['open']}"
            spec = {
                "kind": "filter",
                "drop": "project",
                "title": name,
                "filter": [f"project:{name}", "status:pending"],
            }
            item = self._leaf(self._projects, label, spec, "project")
            tw = colors.get(name, "")
            if tw:
                item.setData(0, _COLOUR_ROLE, tw)
                item.setToolTip(0, t("project_color.tooltip", color=tw))
            if row.get("stuck"):
                item.setData(0, _STUCK_ROLE, True)
                item.setToolTip(0, t("sidebar.project_stuck.tip"))
        self.retint()

    def populate_tags(self, rows: list[dict]) -> None:
        self._tags.takeChildren()
        for row in rows:
            self._leaf(
                self._tags,
                f"#{row['tag']}  ·  {row['count']}",
                {
                    "kind": "filter",
                    "drop": "tag",
                    "tag": row["tag"],
                    "title": f"#{row['tag']}",
                    "filter": [f"+{row['tag']}", "status:pending"],
                },
                "tag",
            )
        self.retint()

    def populate_contexts(self, names: list[str], active: str | None) -> None:
        self._contexts.takeChildren()
        none_item = QTreeWidgetItem([t("sidebar.no_context") + ("  ●" if not active else "")])
        none_item.setData(0, _SPEC_ROLE, {"kind": "context", "name": ""})
        none_item.setData(0, _ICON_ROLE, "context")
        self._contexts.addChild(none_item)
        for name in names:
            mark = "  ●" if name == active else ""
            item = QTreeWidgetItem([name + mark])
            item.setData(0, _SPEC_ROLE, {"kind": "context", "name": name})
            item.setData(0, _ICON_ROLE, "context")
            self._contexts.addChild(item)
        self.retint()

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

    def populate_saved_filters(self, filters: dict[str, str]) -> None:
        self._saved.takeChildren()
        self._saved_items: dict[str, QTreeWidgetItem] = {}
        if not filters:
            hint = QTreeWidgetItem([t("sidebar.saved.hint")])
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            hint.setForeground(0, getattr(self, "_hint_colour", QColor("#888")))
            self._saved.addChild(hint)
            return
        folders: dict[str, QTreeWidgetItem] = {}
        for name, raw in sorted(filters.items()):
            # a "/" in the saved-filter name nests it under a folder
            folder, _, leaf = name.rpartition("/")
            parent = self._saved
            if folder:
                if folder not in folders:
                    fi = QTreeWidgetItem([folder])
                    fi.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    fi.setData(0, _ICON_ROLE, "folder")
                    self._saved.addChild(fi)
                    folders[folder] = fi
                parent = folders[folder]
            item = self._leaf(
                parent, leaf,
                {"kind": "saved", "name": name, "raw": raw}, "filter",
            )
            item.setToolTip(0, raw)
            self._saved_items[name] = item
        self.expandItem(self._saved)
        for fi in folders.values():
            self.expandItem(fi)
        self.retint()

    def set_view_counts(self, counts: dict[str, int]) -> None:
        """Append ``· N`` to quick-view / saved-filter rows (keyed by spec key
        or saved-filter name)."""
        def label_with_count(base: str, n: int | None) -> str:
            return f"{base}  ·  {n}" if n is not None else base

        for item in self._iter_items(self._quick):
            spec = item.data(0, _SPEC_ROLE)
            if isinstance(spec, dict) and spec.get("key") in counts:
                item.setText(0, label_with_count(spec["title"], counts[spec["key"]]))
        for name, item in getattr(self, "_saved_items", {}).items():
            if name in counts:
                leaf = name.rpartition("/")[2]
                item.setText(0, label_with_count(leaf, counts[name]))

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
        from PyQt6.QtWidgets import QInputDialog, QMenu, QMessageBox

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

        if spec.get("drop") == "tag":
            tag = spec["tag"]
            menu = QMenu(self)
            act_rename = menu.addAction(t("sidebar.menu.tag_rename"))
            act_remove = menu.addAction(t("sidebar.menu.tag_remove"))
            chosen = menu.exec(self.viewport().mapToGlobal(pos))
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
            return

        if spec.get("kind") != "saved":
            return
        name = spec["name"]
        menu = QMenu(self)
        act_rename = menu.addAction(t("sidebar.menu.rename"))
        act_delete = menu.addAction(t("sidebar.menu.delete"))
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_rename:
            new, ok = QInputDialog.getText(
                self, t("sidebar.rename.title"), t("sidebar.rename.label"), text=name
            )
            if ok and new.strip() and new.strip() != name:
                self.savedFilterRenameRequested.emit(name, new.strip())
        elif chosen == act_delete:
            confirm = QMessageBox.question(
                self, t("sidebar.delete.title"),
                t("sidebar.delete.body", name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.savedFilterDeleteRequested.emit(name)

    # --- events -----------------------------------------------

    def _on_click(self, item: QTreeWidgetItem, _column: int) -> None:
        spec = item.data(0, _SPEC_ROLE)
        if spec:
            self.activate_spec(spec)

    def activate_spec(self, spec: dict) -> None:
        """Route a sidebar spec to the right signal — shared by clicks and the
        command palette."""
        if spec.get("kind") == "context":
            self.contextChangeRequested.emit(spec["name"])
            return
        if spec.get("kind") == "saved":
            self.savedFilterActivated.emit(spec["raw"])
            return
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
