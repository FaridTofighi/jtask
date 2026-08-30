"""Import dialog — preview a JSON task file, then hand it to ``task import`` (§ M7).

Detects the file shape (indented array vs. newline-delimited objects), shows how
many tasks it holds and a sample, warns that same-UUID tasks will be *updated*,
and only then runs the import.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import fmt


def inspect_import(path: str) -> dict:
    """``{ok, count, format, sample: list[str], error}`` for a candidate file."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        return {"ok": False, "count": 0, "format": "", "sample": [], "error": str(exc)}

    text = raw.strip()
    tasks: list[dict] = []
    fmt_name = ""
    if not text:
        return {"ok": False, "count": 0, "format": "", "sample": [], "error": "فایل خالی است."}
    try:
        if text.startswith("["):
            tasks = json.loads(text)
            fmt_name = "آرایهٔ JSON"
        else:
            for line in text.splitlines():
                line = line.strip().rstrip(",")
                if line and line not in "[]":
                    tasks.append(json.loads(line))
            fmt_name = "خطوط JSON"
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False, "count": 0, "format": "", "sample": [],
            "error": f"قالب JSON نامعتبر است: {exc}",
        }

    if not isinstance(tasks, list) or not tasks:
        return {
            "ok": False, "count": 0, "format": fmt_name, "sample": [],
            "error": "هیچ کاری در فایل پیدا نشد.",
        }
    sample = [str(t.get("description", "—")) for t in tasks[:8] if isinstance(t, dict)]
    return {"ok": True, "count": len(tasks), "format": fmt_name, "sample": sample, "error": ""}


class ImportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle("ورود کارها از فایل")
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        pick = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setPlaceholderText("مسیر فایل JSON")
        self._path.textChanged.connect(self._inspect)
        pick.addWidget(self._path, 1)
        browse = QPushButton("انتخاب…")
        browse.clicked.connect(self._browse)
        pick.addWidget(browse)
        root.addLayout(pick)

        self._info = QLabel("")
        self._info.setObjectName("Muted")
        self._info.setWordWrap(True)
        root.addWidget(self._info)

        self._sample = QListWidget()
        self._sample.setObjectName("ImportSample")
        self._sample.setMaximumHeight(150)
        root.addWidget(self._sample)

        self._warn = QLabel(
            "کارهایی که شناسهٔ یکسان (UUID) با کارهای موجود دارند، به‌روزرسانی می‌شوند."
        )
        self._warn.setObjectName("FormHint")
        self._warn.setWordWrap(True)
        root.addWidget(self._warn)

        btns = QDialogButtonBox()
        btns.addButton("انصراف", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        self._ok = btns.addButton("ورود", QDialogButtonBox.ButtonRole.AcceptRole)
        self._ok.setObjectName("Primary")
        self._ok.clicked.connect(self.accept)
        self._ok.setEnabled(False)
        root.addWidget(btns)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل", self._path.text(), "JSON (*.json);;همه (*)"
        )
        if path:
            self._path.setText(path)

    def _inspect(self, path: str) -> None:
        self._sample.clear()
        path = path.strip()
        if not path:
            self._info.setText("")
            self._ok.setEnabled(False)
            return
        rep = inspect_import(path)
        if not rep["ok"]:
            self._info.setText(rep["error"])
            self._ok.setEnabled(False)
            return
        self._info.setText(f"{fmt.num(rep['count'])} کار · قالب: {rep['format']}")
        for d in rep["sample"]:
            self._sample.addItem(d)
        if rep["count"] > len(rep["sample"]):
            self._sample.addItem("…")
        self._ok.setEnabled(True)

    def path(self) -> str:
        return self._path.text().strip()
