"""Reports Manager — inspect every report; edit definitions of *custom* ones.

Built-in reports are shown read-only.  Editing one offers to create a same-named
override only after an explicit confirmation, so a user's own report is never
silently clobbered.
"""

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

from ..i18n import t
from ..workers import submit
from .confirm import confirm

_FIELDS = [
    ("description", "rep.field.description"),
    ("columns", "rep.field.columns"),
    ("labels", "rep.field.labels"),
    ("sort", "rep.field.sort"),
    ("filter", "rep.field.filter"),
    ("dateformat", "rep.field.dateformat"),
]


class ReportManager(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReportManager")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("ReportTable")
        self._table.setHorizontalHeaderLabels(
            [t("rep.col.name"), t("rep.col.type"), t("rep.col.columns"), t("rep.col.filter")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        self._table.doubleClicked.connect(self._edit)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self._table, 1)

        row = QHBoxLayout()
        add = QPushButton(t("rep.add"))
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        row.addWidget(add)
        row.addStretch(1)
        self._hint = QLabel(t("rep.hint"))
        self._hint.setObjectName("Muted")
        row.addWidget(self._hint)
        lay.addLayout(row)

        self._specs: dict[str, dict] = {}

    def reload(self) -> None:
        submit(taskwarrior.report_specs, self._populate, lambda _e: None)

    def _populate(self, specs: dict[str, dict]) -> None:
        self._specs = specs
        names = sorted(specs)
        self._table.setRowCount(len(names))
        for i, name in enumerate(names):
            spec = specs[name]
            builtin = name in taskwarrior.BUILTIN_REPORTS
            self._table.setItem(i, 0, QTableWidgetItem(name))
            self._table.setItem(
                i, 1, QTableWidgetItem(t("rep.type.builtin") if builtin else t("rep.type.custom"))
            )
            self._table.setItem(i, 2, QTableWidgetItem(spec.get("columns", "")))
            self._table.setItem(i, 3, QTableWidgetItem(spec.get("filter", "")))

    def _selected(self) -> str | None:
        r = self._table.currentRow()
        return self._table.item(r, 0).text() if r >= 0 else None

    def _add(self) -> None:
        dlg = _ReportDialog(self)
        if dlg.exec():
            self._save(dlg.name(), dlg.fields(), is_new=True)

    def _edit(self, *_a: object) -> None:
        name = self._selected()
        if not name:
            return
        spec = self._specs.get(name, {})
        builtin = name in taskwarrior.BUILTIN_REPORTS
        dlg = _ReportDialog(self, name=name, spec=spec, builtin=builtin)
        if not dlg.exec():
            return
        if builtin and not confirm(
            self,
            title=t("rep.override.title"),
            body=t("rep.override.body", name=name),
        ):
            return
        self._save(name, dlg.fields(), is_new=False)

    def _save(self, name: str, fields: dict, *, is_new: bool) -> None:
        if not name:
            return
        if is_new and name in self._specs and not confirm(
            self,
            title=t("rep.exists.title"),
            body=t("rep.exists.body", name=name),
        ):
            return

        def work() -> None:
            for key, val in fields.items():
                if val:
                    taskwarrior.report_set(name, key, val)
                else:
                    taskwarrior.config_unset(f"report.{name}.{key}")

        submit(
            work,
            lambda _r: (taskwarrior.refresh_lookups(), self.changed.emit(), self.reload()),
            lambda _e: None,
        )


class _ReportDialog(QDialog):
    def __init__(self, parent=None, *, name="", spec: dict | None = None, builtin=False) -> None:
        super().__init__(parent)
        spec = spec or {}
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle(t("rep.dialog.title") if name else t("rep.dialog.title_new"))
        self.setMinimumWidth(480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        form = QFormLayout()
        self._name = QLineEdit(name)
        self._name.setReadOnly(bool(name))
        self._name.setPlaceholderText(t("rep.name.placeholder"))
        form.addRow(t("word.name"), self._name)
        self._fields: dict[str, QLineEdit] = {}
        for key, label_key in _FIELDS:
            e = QLineEdit(spec.get(key, ""))
            self._fields[key] = e
            form.addRow(t(label_key), e)
        lay.addLayout(form)

        if builtin:
            w = QLabel(t("rep.builtin.note"))
            w.setObjectName("FormHint")
            w.setWordWrap(True)
            lay.addWidget(w)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        ok = btns.addButton(t("btn.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        lay.addWidget(btns)

    def name(self) -> str:
        return self._name.text().strip()

    def fields(self) -> dict:
        return {k: e.text().strip() for k, e in self._fields.items()}
