"""Hook Manager — list Taskwarrior hook scripts, enable / disable, reveal.

Editing a hook's body stays a console / ``$EDITOR`` task; this surface lists
what is installed and lets the user flip the executable bit that Taskwarrior
uses to decide whether to run a hook.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from .. import tokens as tok
from ..i18n import t
from ..workers import submit


class HookManager(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HookManager")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_8)

        self._location = QLabel("")
        self._location.setObjectName("Muted")
        self._location.setWordWrap(True)
        lay.addWidget(self._location)

        self._table = QTableWidget(0, 3)
        self._table.setObjectName("HookTable")
        self._table.setHorizontalHeaderLabels(
            [t("hook.col.name"), t("hook.col.event"), t("hook.col.status")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        lay.addWidget(self._table, 1)

        self._empty = QLabel(t("hook.empty"))
        self._empty.setObjectName("EmptyState")
        self._empty.setWordWrap(True)
        self._empty.setVisible(False)
        lay.addWidget(self._empty)

        row = QHBoxLayout()
        self._toggle = QPushButton(t("hook.toggle"))
        self._toggle.clicked.connect(self._toggle_selected)
        row.addWidget(self._toggle)
        reveal = QPushButton(t("hook.reveal"))
        reveal.clicked.connect(self._reveal)
        row.addWidget(reveal)
        row.addStretch(1)
        note = QLabel(t("hook.edit_note"))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addLayout(row)
        lay.addWidget(note)

        self._hooks: list[dict] = []

    def reload(self) -> None:
        submit(self._fetch, self._populate, lambda _e: None)

    @staticmethod
    def _fetch() -> tuple[str, list[dict]]:
        return taskwarrior.hooks_location(), taskwarrior.hooks()

    def _populate(self, result: tuple[str, list[dict]]) -> None:
        location, hooks = result
        self._hooks = hooks
        self._location.setText(t("hook.location", path=location))
        self._table.setRowCount(len(hooks))
        for i, hook in enumerate(hooks):
            self._table.setItem(i, 0, QTableWidgetItem(hook["name"]))
            self._table.setItem(i, 1, QTableWidgetItem(hook["event"] or "—"))
            status = t("hook.status.enabled") if hook["enabled"] else t("hook.status.disabled")
            self._table.setItem(i, 2, QTableWidgetItem(status))
        self._table.setVisible(bool(hooks))
        self._empty.setVisible(not hooks)

    def _selected(self) -> dict | None:
        r = self._table.currentRow()
        return self._hooks[r] if 0 <= r < len(self._hooks) else None

    def _toggle_selected(self) -> None:
        hook = self._selected()
        if not hook:
            return

        def work() -> None:
            taskwarrior.hook_set_enabled(hook["path"], not hook["enabled"])

        def done(_r: object) -> None:
            self.changed.emit()
            self.reload()

        submit(work, done, lambda _e: None)

    def _reveal(self) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        hook = self._selected()
        target = hook["path"] if hook else taskwarrior.hooks_location()
        QDesktopServices.openUrl(QUrl.fromLocalFile(target))
