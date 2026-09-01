"""Export dialog — write matching tasks to a JSON file (§ M7).

Scope (all / current filter / custom) × format (indented array / JSON lines) →
a file the user picks.  Export + Import together are jtask's backup/restore
path (see docs/taskwarrior-feature-matrix.md → intentional non-features).
"""

from __future__ import annotations

import datetime as dt
import os

import jdatetime
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from .. import tokens as tok
from ..i18n import t
from ..workers import submit
from .segmented import SegmentedControl


class ExportDialog(QDialog):
    def __init__(
        self, current_filter: list[str] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ExportDialog")
        self.setWindowTitle(t("export.title"))
        self.setMinimumWidth(500)
        self._current_filter = list(current_filter or [])
        self._count_gen = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_12)
        form = QFormLayout()
        form.setSpacing(tok.SP_10)

        self._scope = SegmentedControl(
            [
                (t("export.scope.all"), "all"),
                (t("export.scope.current"), "current"),
                (t("export.scope.custom"), "custom"),
            ]
        )
        self._scope.changed.connect(self._on_scope)
        form.addRow(t("export.scope"), self._scope)

        self._filter_edit = QLineEdit(" ".join(self._current_filter))
        self._filter_edit.setPlaceholderText(t("export.filter.placeholder"))
        self._filter_edit.textChanged.connect(self._recount)
        self._filter_edit.setEnabled(False)
        form.addRow(t("export.filter"), self._filter_edit)

        self._format = SegmentedControl(
            [(t("export.format.array"), "array"), (t("export.format.lines"), "lines")]
        )
        form.addRow(t("export.format"), self._format)

        dest_row = QHBoxLayout()
        self._path = QLineEdit(self._default_path())
        dest_row.addWidget(self._path, 1)
        browse = QPushButton(t("btn.choose"))
        browse.clicked.connect(self._browse)
        dest_row.addWidget(browse)
        dw = QWidget()
        dw.setLayout(dest_row)
        form.addRow(t("export.destination"), dw)

        root.addLayout(form)

        self._count = QLabel("")
        self._count.setObjectName("Muted")
        root.addWidget(self._count)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        self._ok = btns.addButton(
            t("export.ok"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._ok.setObjectName("Primary")
        self._ok.clicked.connect(self.accept)
        root.addWidget(btns)

        self._recount()

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _default_path() -> str:
        today = jdatetime.date.today().strftime("%Y-%m-%d")
        return os.path.join(
            os.path.expanduser("~"), f"jtask-export-{today}.json"
        )

    def _on_scope(self, _v: object) -> None:
        self._filter_edit.setEnabled(self.scope() == "custom")
        if self.scope() == "current":
            self._filter_edit.setText(" ".join(self._current_filter))
        self._recount()

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("export.save_dialog"), self._path.text(), t("export.file_filter")
        )
        if path:
            self._path.setText(path)

    def _recount(self, *_a: object) -> None:
        flt = self.filter_tokens()
        self._count.setText(t("export.counting"))
        self._count_gen += 1
        gen = self._count_gen

        def ok(n: int) -> None:
            if gen == self._count_gen:
                self._count.setText(t("export.count", n=_fa(n)))

        def err(_e: object) -> None:
            if gen == self._count_gen:
                self._count.setText(t("export.count_failed"))

        # a backup is always complete — never scoped to the active context
        submit(lambda: len(taskwarrior.export(flt or None, apply_context=False)), ok, err)

    # -- result --------------------------------------------------------

    def scope(self) -> str:
        return str(self._scope.value())

    def filter_tokens(self) -> list[str]:
        if self.scope() == "all":
            return []
        return [t for t in self._filter_edit.text().split() if t]

    def spec(self) -> dict:
        return {
            "filter": self.filter_tokens(),
            "array": self._format.value() == "array",
            "path": self._path.text().strip(),
        }


def _fa(n: int) -> str:
    from .. import fmt

    return fmt.num(n)


def write_export(spec: dict) -> dict:
    """Run the export described by *spec* and write the file. Returns stats."""
    flt = spec["filter"] or None
    # a backup file must stay complete regardless of the active context
    text = taskwarrior.export_text(flt, array=spec["array"], apply_context=False)
    path = spec["path"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return {
        "path": path,
        "bytes": os.path.getsize(path),
        "count": len(taskwarrior.export(flt, apply_context=False)),
        "when": dt.datetime.now(),
    }
