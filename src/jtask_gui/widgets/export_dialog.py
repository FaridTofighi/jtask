"""Export dialog — write matching tasks to a JSON file (§ M7).

Scope (all / current filter / custom) × format (indented array / JSON lines) →
a file the user picks.  Export + Import together are jtask's backup/restore
path (see docs/taskwarrior-feature-matrix.md → intentional non-features).
"""

from __future__ import annotations

import datetime as dt
import os

import jdatetime
from PyQt6.QtCore import Qt
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

from ..workers import submit
from .segmented import SegmentedControl


class ExportDialog(QDialog):
    def __init__(
        self, current_filter: list[str] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ExportDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle("خروجی گرفتن از کارها")
        self.setMinimumWidth(500)
        self._current_filter = list(current_filter or [])
        self._count_gen = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self._scope = SegmentedControl(
            [("همه", "all"), ("فیلتر فعلی", "current"), ("سفارشی", "custom")]
        )
        self._scope.changed.connect(self._on_scope)
        form.addRow("محدوده", self._scope)

        self._filter_edit = QLineEdit(" ".join(self._current_filter))
        self._filter_edit.setPlaceholderText("مثال: project:خانه +مهم status:pending")
        self._filter_edit.textChanged.connect(self._recount)
        self._filter_edit.setEnabled(False)
        form.addRow("فیلتر", self._filter_edit)

        self._format = SegmentedControl(
            [("آرایهٔ JSON", "array"), ("خطوط JSON", "lines")]
        )
        form.addRow("قالب", self._format)

        dest_row = QHBoxLayout()
        self._path = QLineEdit(self._default_path())
        dest_row.addWidget(self._path, 1)
        browse = QPushButton("انتخاب…")
        browse.clicked.connect(self._browse)
        dest_row.addWidget(browse)
        dw = QWidget()
        dw.setLayout(dest_row)
        form.addRow("مقصد", dw)

        root.addLayout(form)

        self._count = QLabel("")
        self._count.setObjectName("Muted")
        root.addWidget(self._count)

        btns = QDialogButtonBox()
        btns.addButton("انصراف", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        self._ok = btns.addButton(
            "خروجی گرفتن", QDialogButtonBox.ButtonRole.AcceptRole
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
            self, "ذخیرهٔ خروجی", self._path.text(), "JSON (*.json);;همه (*)"
        )
        if path:
            self._path.setText(path)

    def _recount(self, *_a: object) -> None:
        flt = self.filter_tokens()
        self._count.setText("در حال شمارش…")
        self._count_gen += 1
        gen = self._count_gen

        def ok(n: int) -> None:
            if gen == self._count_gen:
                self._count.setText(f"{_fa(n)} کار برای خروجی")

        def err(_e: object) -> None:
            if gen == self._count_gen:
                self._count.setText("شمارش ناموفق بود")

        submit(lambda: len(taskwarrior.export(flt or None)), ok, err)

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
    text = taskwarrior.export_text(flt, array=spec["array"])
    path = spec["path"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return {
        "path": path,
        "bytes": os.path.getsize(path),
        "count": len(taskwarrior.export(flt)),
        "when": dt.datetime.now(),
    }
