"""UDA Manager — CRUD Taskwarrior user-defined attribute *definitions*."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from ..i18n import t
from ..workers import submit
from .confirm import confirm

_TYPES = [
    ("uda.type.string", "string"),
    ("uda.type.numeric", "numeric"),
    ("uda.type.date", "date"),
    ("uda.type.duration", "duration"),
]
_TYPE_FA = {v: t(k) for k, v in _TYPES}


class UdaManager(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UdaManager")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("UdaTable")
        self._table.setHorizontalHeaderLabels(
            [t("uda.col.name"), t("uda.col.label"), t("uda.col.type"), t("uda.col.values")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        self._table.doubleClicked.connect(self._edit)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        lay.addWidget(self._table, 1)

        row = QHBoxLayout()
        add = QPushButton(t("uda.add"))
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        row.addWidget(add)
        rm = QPushButton(t("uda.delete_selected"))
        rm.clicked.connect(self._delete)
        row.addWidget(rm)
        row.addStretch(1)
        lay.addLayout(row)

    def reload(self) -> None:
        submit(taskwarrior.uda_definitions, self._populate, lambda _e: None)

    def _populate(self, udas: dict[str, dict]) -> None:
        items = sorted(udas.items())
        self._table.setRowCount(len(items))
        for i, (name, spec) in enumerate(items):
            utype = spec.get("type", "string")
            self._table.setItem(i, 0, QTableWidgetItem(name))
            self._table.setItem(i, 1, QTableWidgetItem(spec.get("label", name)))
            self._table.setItem(i, 2, QTableWidgetItem(_TYPE_FA.get(utype, utype)))
            self._table.setItem(i, 3, QTableWidgetItem(spec.get("values", "")))

    def _selected(self) -> str | None:
        r = self._table.currentRow()
        return self._table.item(r, 0).text() if r >= 0 else None

    def _add(self) -> None:
        dlg = _UdaDialog(self)
        if dlg.exec():
            self._save(dlg.values())

    def _edit(self, *_a: object) -> None:
        r = self._table.currentRow()
        if r < 0:
            return
        name = self._table.item(r, 0).text()
        spec = taskwarrior.uda_definitions().get(name, {})
        dlg = _UdaDialog(self, name=name, spec=spec)
        if dlg.exec():
            self._save(dlg.values())

    def _save(self, vals: dict) -> None:
        name = vals["name"]
        if not name:
            return

        def work() -> None:
            taskwarrior.uda_set(name, "type", vals["type"])
            taskwarrior.uda_set(name, "label", vals["label"] or name)
            if vals["values"]:
                taskwarrior.uda_set(name, "values", vals["values"])
            else:
                taskwarrior.config_unset(f"uda.{name}.values")
            if vals["default"]:
                taskwarrior.uda_set(name, "default", vals["default"])

        self._apply(work)

    def _delete(self) -> None:
        name = self._selected()
        if not name:
            return
        if not confirm(
            self,
            title=t("uda.delete.title"),
            body=t("uda.delete.body", name=name),
            destructive=True,
            confirm_label=t("btn.delete"),
        ):
            return
        self._apply(lambda: taskwarrior.uda_delete(name))

    def _apply(self, fn) -> None:
        submit(
            fn,
            lambda _r: (taskwarrior.refresh_lookups(), self.changed.emit(), self.reload()),
            lambda _e: None,
        )


class _UdaDialog(QDialog):
    def __init__(self, parent=None, *, name="", spec: dict | None = None) -> None:
        super().__init__(parent)
        spec = spec or {}
        self.setWindowTitle(t("uda.dialog.title") if name else t("uda.dialog.title_new"))
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        form = QFormLayout()
        self._name = QLineEdit(name)
        self._name.setReadOnly(bool(name))
        self._name.setPlaceholderText(t("uda.name.placeholder"))
        form.addRow(t("word.name"), self._name)
        self._label = QLineEdit(spec.get("label", ""))
        form.addRow(t("uda.col.label"), self._label)
        self._type = QComboBox()
        for lbl, val in _TYPES:
            self._type.addItem(t(lbl), val)
        cur = spec.get("type", "string")
        self._type.setCurrentIndex(
            next((i for i, (_, v) in enumerate(_TYPES) if v == cur), 0)
        )
        form.addRow(t("uda.col.type"), self._type)
        self._values = QLineEdit(spec.get("values", ""))
        self._values.setPlaceholderText(t("uda.values.placeholder"))
        form.addRow(t("uda.col.values"), self._values)
        self._default = QLineEdit(spec.get("default", ""))
        form.addRow(t("uda.field.default"), self._default)
        lay.addLayout(form)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        ok = btns.addButton(t("btn.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        lay.addWidget(btns)

    def values(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "label": self._label.text().strip(),
            "type": self._type.currentData(),
            "values": self._values.text().strip(),
            "default": self._default.text().strip(),
        }
