"""The toolbar saved-filters dropdown.

Replaces the sidebar's "Saved filters" section (sidebar IA redesign). A
`Qt.Popup` anchored under the toolbar button: a live search box, the same
`folder/name` nesting the sidebar used, a task count per filter (tinted in
the `overdue` tone when the filter tracks attention work — `+BLOCKED` /
`+OVERDUE` / `+WAITING`), click-to-apply, a right-click menu
(rename / delete / edit / pin), and a footer entry to the manage dialog.

Pure presentation — every data source (`settings.saved_filters()`, the
`_view_counts` job) is reused unchanged.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import fmt, icons
from .. import tokens as tok
from ..i18n import t
from ..theme import palette

_ATTENTION = re.compile(r"\+(BLOCKED|OVERDUE|WAITING)\b")
_NAME_ROLE = Qt.ItemDataRole.UserRole
_RAW_ROLE = Qt.ItemDataRole.UserRole + 1


class SavedFilterMenu(QWidget):
    filterActivated = pyqtSignal(str)          # raw
    renameRequested = pyqtSignal(str, str)     # old, new
    deleteRequested = pyqtSignal(str)          # name
    editRequested = pyqtSignal(str)            # raw
    pinToggled = pyqtSignal(str)               # name
    manageRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("SavedFilterMenu")
        self.setMinimumWidth(300)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_TIGHT)
        lay.setSpacing(tok.SP_6)

        self._search = QLineEdit()
        self._search.setObjectName("PaletteInput")
        self._search.setPlaceholderText(t("filtermenu.search"))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._refilter)
        lay.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setObjectName("SavedFilterTree")
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(12)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._row_menu)
        self._tree.itemClicked.connect(self._on_click)
        lay.addWidget(self._tree, 1)

        self._empty = QLineEdit()
        self._empty.setReadOnly(True)
        self._empty.setObjectName("Muted")
        self._empty.setFrame(False)
        self._empty.hide()
        lay.addWidget(self._empty)

        self._manage = QPushButton(t("filtermenu.manage"))
        self._manage.clicked.connect(lambda: (self.manageRequested.emit(), self.close()))
        lay.addWidget(self._manage)

    # --- API -------------------------------------------------------

    def set_data(
        self, filters: dict[str, str], counts: dict[str, int], pinned: list[str],
        order: list[str] | None = None, theme: str = "dark",
    ) -> None:
        self._tree.clear()
        names = order or sorted(filters)
        pinned_set = set(pinned)
        pal = palette(theme)
        attn = QColor(pal["overdue"])
        muted = QColor(pal["text_muted"])
        folders: dict[str, QTreeWidgetItem] = {}
        for name in names:
            if name not in filters:
                continue
            raw = filters[name]
            folder, _, leaf = name.rpartition("/")
            parent = self._tree.invisibleRootItem()
            if folder:
                if folder not in folders:
                    fi = QTreeWidgetItem([folder])
                    fi.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    fi.setIcon(0, icons.icon("folder", "text_muted"))
                    self._tree.addTopLevelItem(fi)
                    folders[folder] = fi
                parent = folders[folder]
            n = counts.get(name)
            label = leaf if n is None else f"{leaf}  ·  {fmt.num(n)}"
            item = QTreeWidgetItem([label])
            item.setData(0, _NAME_ROLE, name)
            item.setData(0, _RAW_ROLE, raw)
            item.setToolTip(0, raw)
            item.setForeground(0, attn if _ATTENTION.search(raw) else muted)
            if name in pinned_set:
                item.setIcon(0, icons.icon("pin", "primary"))
            parent.addChild(item) if folder else self._tree.addTopLevelItem(item)
        self._tree.expandAll()
        has_any = bool(filters)
        self._tree.setVisible(has_any)
        self._empty.setVisible(not has_any)
        if not has_any:
            self._empty.setText(t("sidebar.saved.hint"))

    def popup_at(self, global_bottom_left) -> None:
        self.move(global_bottom_left)
        self.resize(max(self.minimumWidth(), self.sizeHint().width()), 360)
        self._search.clear()
        self.show()
        self._search.setFocus()

    # --- internals ------------------------------------------------

    def _iter_leaves(self):
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            if top.data(0, _NAME_ROLE):
                yield top
            for j in range(top.childCount()):
                yield top.child(j)

    def _refilter(self, text: str) -> None:
        q = text.strip().lower()
        for leaf in self._iter_leaves():
            leaf.setHidden(q not in (leaf.data(0, _NAME_ROLE) or "").lower())
        # hide a folder whose children are all filtered out
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            if top.data(0, _NAME_ROLE):
                continue
            top.setHidden(all(top.child(j).isHidden() for j in range(top.childCount())))

    def _on_click(self, item: QTreeWidgetItem, _col: int) -> None:
        raw = item.data(0, _RAW_ROLE)
        if raw is not None:
            self.filterActivated.emit(raw)
            self.close()

    def _row_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        name = item.data(0, _NAME_ROLE) if item else None
        if not name:
            return
        raw = item.data(0, _RAW_ROLE)
        menu = QMenu(self)
        act_rename = menu.addAction(t("sidebar.menu.rename"))
        act_edit = menu.addAction(t("filtermenu.edit"))
        act_pin = menu.addAction(
            t("filtermenu.unpin") if not item.icon(0).isNull() else t("filtermenu.pin")
        )
        menu.addSeparator()
        act_delete = menu.addAction(t("sidebar.menu.delete"))
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen == act_rename:
            from PyQt6.QtWidgets import QInputDialog

            new, ok = QInputDialog.getText(
                self, t("sidebar.rename.title"), t("sidebar.rename.label"), text=name
            )
            if ok and new.strip() and new.strip() != name:
                self.renameRequested.emit(name, new.strip())
        elif chosen == act_edit:
            self.editRequested.emit(raw)
            self.close()
        elif chosen == act_pin:
            self.pinToggled.emit(name)
        elif chosen == act_delete:
            if QMessageBox.question(
                self, t("sidebar.delete.title"),
                t("sidebar.delete.body", name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                self.deleteRequested.emit(name)
