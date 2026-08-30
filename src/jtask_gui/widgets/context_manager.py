"""Context Manager — create / edit / delete / activate Taskwarrior contexts."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from .confirm import confirm


class ContextManager(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContextManager")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_8)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("ContextTable")
        self._table.setHorizontalHeaderLabels(
            [t("ctx.col.name"), t("ctx.col.read"), t("ctx.col.write"), t("ctx.col.active")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        self._table.doubleClicked.connect(self._edit)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self._table, 1)

        row = QHBoxLayout()
        add = QPushButton(t("ctx.add"))
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        row.addWidget(add)
        self._activate = QPushButton(t("ctx.activate_selected"))
        self._activate.clicked.connect(self._activate_selected)
        row.addWidget(self._activate)
        self._deactivate = QPushButton(t("ctx.deactivate"))
        self._deactivate.clicked.connect(lambda: self._set_active(None))
        row.addWidget(self._deactivate)
        self._delete = QPushButton(t("ctx.delete_selected"))
        self._delete.clicked.connect(self._delete_selected)
        row.addWidget(self._delete)
        row.addStretch(1)
        lay.addLayout(row)

    def reload(self) -> None:
        submit(taskwarrior.context_list, self._populate, lambda _e: None)

    def _populate(self, rows: list[dict]) -> None:
        self._table.setRowCount(len(rows))
        for i, c in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(c["name"]))
            self._table.setItem(i, 1, QTableWidgetItem(c.get("read", "")))
            self._table.setItem(i, 2, QTableWidgetItem(c.get("write", "")))
            act = QTableWidgetItem("✓" if c.get("active") else "")
            act.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 3, act)

    def _selected_name(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).text()

    def _add(self) -> None:
        dlg = _ContextDialog(self)
        if dlg.exec():
            name, read, write = dlg.values()
            if name and read:
                self._apply(lambda: taskwarrior.context_define(name, read, write))

    def _edit(self, *_a: object) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._table.item(row, 0).text()
        read = self._table.item(row, 1).text()
        write = self._table.item(row, 2).text()
        dlg = _ContextDialog(self, name=name, read=read, write=write)
        if dlg.exec():
            _n, r, w = dlg.values()
            self._apply(lambda: taskwarrior.context_define(name, r, w))

    def _activate_selected(self) -> None:
        name = self._selected_name()
        if name:
            self._set_active(name)

    def _set_active(self, name: str | None) -> None:
        self._apply(lambda: taskwarrior.context_activate(name))

    def _delete_selected(self) -> None:
        name = self._selected_name()
        if not name:
            return
        if not confirm(
            self,
            title=t("ctx.delete.title"),
            body=t("ctx.delete.body", name=name),
            destructive=True,
            confirm_label=t("btn.delete"),
        ):
            return
        self._apply(lambda: taskwarrior.context_delete(name))

    def _apply(self, fn) -> None:
        submit(
            fn,
            lambda _r: (taskwarrior.refresh_lookups(), self.changed.emit(), self.reload()),
            lambda _e: None,
        )


class _ContextDialog(QDialog):
    def __init__(self, parent=None, *, name="", read="", write="") -> None:
        super().__init__(parent)
        self.setWindowTitle(t("ctx.dialog.title") if name else t("ctx.dialog.title_new"))
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_DIALOG)
        form = QFormLayout()
        self._name = QLineEdit(name)
        self._name.setReadOnly(bool(name))
        form.addRow(t("word.name"), self._name)
        self._read = QLineEdit(read)
        self._read.setPlaceholderText(t("ctx.read.placeholder"))
        form.addRow(t("ctx.col.read"), self._read)
        self._write = QLineEdit(write)
        self._write.setPlaceholderText(t("ctx.write.placeholder"))
        form.addRow(t("ctx.col.write"), self._write)
        lay.addLayout(form)

        note = QLabel(t("ctx.write.note"))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        ok = btns.addButton(t("btn.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        lay.addWidget(btns)

    def values(self) -> tuple[str, str, str]:
        return (
            self._name.text().strip(),
            self._read.text().strip(),
            self._write.text().strip(),
        )
