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

from ..workers import submit
from .confirm import confirm


class ContextManager(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContextManager")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("ContextTable")
        self._table.setHorizontalHeaderLabels(
            ["نام", "فیلتر خواندن", "فیلتر نوشتن", "فعال"]
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
        add = QPushButton("افزودن زمینه…")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        row.addWidget(add)
        self._activate = QPushButton("فعال‌سازی انتخاب‌شده")
        self._activate.clicked.connect(self._activate_selected)
        row.addWidget(self._activate)
        self._deactivate = QPushButton("غیرفعال‌سازی زمینه")
        self._deactivate.clicked.connect(lambda: self._set_active(None))
        row.addWidget(self._deactivate)
        self._delete = QPushButton("حذف انتخاب‌شده")
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
            title="حذف زمینه",
            body=f"زمینهٔ «{name}» حذف می‌شود. کارها بی‌تغییر می‌مانند.",
            destructive=True,
            confirm_label="حذف",
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
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle("زمینه" if name else "زمینهٔ جدید")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        form = QFormLayout()
        self._name = QLineEdit(name)
        self._name.setReadOnly(bool(name))
        form.addRow("نام", self._name)
        self._read = QLineEdit(read)
        self._read.setPlaceholderText("مثال: project:کار or +فعال")
        form.addRow("فیلتر خواندن", self._read)
        self._write = QLineEdit(write)
        self._write.setPlaceholderText("خالی = مانند فیلتر خواندن")
        form.addRow("فیلتر نوشتن", self._write)
        lay.addLayout(form)

        note = QLabel(
            "فیلتر نوشتن جداگانه در همهٔ نسخه‌های Taskwarrior پشتیبانی نمی‌شود؛ "
            "در صورت نبود، همان فیلتر خواندن اعمال می‌شود."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)

        btns = QDialogButtonBox()
        btns.addButton("انصراف", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        ok = btns.addButton("ذخیره", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        lay.addWidget(btns)

    def values(self) -> tuple[str, str, str]:
        return (
            self._name.text().strip(),
            self._read.text().strip(),
            self._write.text().strip(),
        )
