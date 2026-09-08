"""Manage-filters dialog — bulk reorganisation of saved filters.

Mirrors `board_manager.BoardManagerDialog`: takes `settings`, keeps a working
copy, full-reconciles on every edit and emits `changed`. Reorder with the
arrows, rename (type `Folder/Name` to move between folders), pin, and
multi-select delete.
"""

from __future__ import annotations

import copy

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import icons
from .. import tokens as tok
from ..i18n import t


class FilterManagerDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FilterManager")
        self.setWindowTitle(t("filter.manage.title"))
        self.setMinimumWidth(560)
        self._settings = settings
        self._filters: dict[str, str] = copy.deepcopy(settings.saved_filters())
        self._order: list[str] = list(settings.filter_order())
        self._pinned: list[str] = list(settings.pinned_filters())

        root = QHBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_12)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.currentRowChanged.connect(self._select)
        left.addWidget(self._list, 1)

        brow = QHBoxLayout()
        self._rename_btn = QPushButton(t("btn.rename"))
        self._rename_btn.clicked.connect(self._rename)
        self._pin_btn = QPushButton(t("filtermenu.pin"))
        self._pin_btn.clicked.connect(self._toggle_pin)
        self._del_btn = QPushButton(t("btn.delete"))
        self._del_btn.setObjectName("DangerButton")
        self._del_btn.clicked.connect(self._delete)
        self._up = self._arrow("mdi.chevron-up", lambda: self._move(-1))
        self._dn = self._arrow("mdi.chevron-down", lambda: self._move(1))
        for w in (self._rename_btn, self._pin_btn, self._del_btn, self._up, self._dn):
            brow.addWidget(w)
        left.addLayout(brow)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        self._raw = QLabel("")
        self._raw.setObjectName("Muted")
        self._raw.setWordWrap(True)
        self._raw.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right.addWidget(self._raw, 1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.button(QDialogButtonBox.StandardButton.Close).setText(t("btn.close"))
        box.rejected.connect(self.accept)
        right.addWidget(box)
        root.addLayout(right, 1)

        self._reload()

    @staticmethod
    def _arrow(glyph: str, slot):
        import qtawesome as qta

        b = QToolButton()
        b.setIcon(qta.icon(glyph))
        b.clicked.connect(slot)
        return b

    # --- list ----------------------------------------------------

    def _names(self) -> list[str]:
        known = set(self._filters)
        ordered = [n for n in self._order if n in known]
        return ordered + sorted(known - set(ordered))

    def _reload(self, keep: str | None = None) -> None:
        self._list.clear()
        for name in self._names():
            glyph = "pin" if name in self._pinned else "filter"
            role = "primary" if name in self._pinned else "text_muted"
            it = QListWidgetItem(icons.icon(glyph, role), name)
            it.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(it)
        if keep:
            for i in range(self._list.count()):
                if self._list.item(i).data(Qt.ItemDataRole.UserRole) == keep:
                    self._list.setCurrentRow(i)
                    break
        elif self._list.count():
            self._list.setCurrentRow(0)

    def _selected_names(self) -> list[str]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self._list.selectedItems()]

    def _select(self, _row: int) -> None:
        names = self._selected_names()
        self._raw.setText(self._filters.get(names[0], "") if names else "")
        pinned = bool(names) and names[0] in self._pinned
        self._pin_btn.setText(t("filtermenu.unpin") if pinned else t("filtermenu.pin"))

    # --- edits (write through, emit changed) -------------------

    def _persist(self) -> None:
        for name, raw in self._filters.items():
            self._settings.save_filter(name, raw)
        for name in list(self._settings.saved_filters()):
            if name not in self._filters:
                self._settings.delete_filter(name)
        self._settings.set_filter_order([n for n in self._order if n in self._filters])
        self._settings.set_pinned_filters([n for n in self._pinned if n in self._filters])
        self.changed.emit()

    def _rename(self) -> None:
        names = self._selected_names()
        if len(names) != 1:
            return
        old = names[0]
        new, ok = QInputDialog.getText(
            self, t("sidebar.rename.title"), t("sidebar.rename.label"), text=old
        )
        new = new.strip()
        if not ok or not new or new == old or new in self._filters:
            return
        self._filters[new] = self._filters.pop(old)
        self._order = [new if n == old else n for n in self._order]
        self._pinned = [new if n == old else n for n in self._pinned]
        self._persist()
        self._reload(new)

    def _toggle_pin(self) -> None:
        names = self._selected_names()
        if not names:
            return
        name = names[0]
        if name in self._pinned:
            self._pinned.remove(name)
        else:
            self._pinned.append(name)
        self._persist()
        self._reload(name)

    def _delete(self) -> None:
        names = self._selected_names()
        if not names:
            return
        if QMessageBox.question(
            self, t("sidebar.delete.title"),
            t("filter.manage.delete_body", n=len(names)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        for name in names:
            self._filters.pop(name, None)
        self._order = [n for n in self._order if n in self._filters]
        self._pinned = [n for n in self._pinned if n in self._filters]
        self._persist()
        self._reload()

    def _move(self, delta: int) -> None:
        names = self._selected_names()
        if len(names) != 1:
            return
        order = self._names()
        i = order.index(names[0])
        j = i + delta
        if 0 <= j < len(order):
            order[i], order[j] = order[j], order[i]
            self._order = order
            self._persist()
            self._reload(names[0])
