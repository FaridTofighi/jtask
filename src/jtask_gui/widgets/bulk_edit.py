"""Bulk field editor — one form that modifies many tasks at once (§ M5).

Only the fields the user actually touches are emitted; everything left on
"— بدون تغییر —" is omitted from the resulting ``task … modify`` mods.  Dates
come back Taskwarrior-ready (Gregorian) from the shared Jalali picker, so the
caller must *not* run them through ``rewrite_args`` again.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import fmt
from .jalali_date_picker import JalaliDatePicker
from .segmented import SegmentedControl

_NOCHANGE = "— بدون تغییر —"
_TAG_SPLIT = re.compile(r"[\s,، ]+")


def _tags(text: str) -> list[str]:
    return [t.lstrip("+-#") for t in _TAG_SPLIT.split(text.strip()) if t.lstrip("+-#")]


class BulkEditDialog(QDialog):
    def __init__(
        self,
        count: int,
        projects: list[str] | None = None,
        tags: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("BulkEditDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle("ویرایش گروهی")
        self.setMinimumWidth(460)
        self._count = count

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self._priority = SegmentedControl(
            [
                (_NOCHANGE, None),
                ("بحرانی", "H"),
                ("متوسط", "M"),
                ("پایین", "L"),
                ("حذف", "__clear__"),
            ]
        )
        form.addRow("اولویت", self._priority)

        self._project = QComboBox()
        self._project.setEditable(True)
        self._project.addItem(_NOCHANGE)
        for p in projects or []:
            self._project.addItem(p)
        self._project.setCurrentIndex(0)
        form.addRow("پروژه", self._project)

        self._add_tags = QLineEdit()
        self._add_tags.setPlaceholderText("برچسب‌های جداشده با فاصله برای افزودن")
        form.addRow("افزودن برچسب", self._add_tags)

        self._del_tags = QLineEdit()
        self._del_tags.setPlaceholderText("برچسب‌ها برای حذف")
        form.addRow("حذف برچسب", self._del_tags)

        self._due = _DateRow()
        form.addRow("سررسید", self._due)
        self._scheduled = _DateRow()
        form.addRow("زمان‌بندی", self._scheduled)
        self._wait = _DateRow()
        form.addRow("تاریخ انتظار", self._wait)

        root.addLayout(form)

        btns = QDialogButtonBox()
        btns.addButton("انصراف", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        ok = btns.addButton("اعمال", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        root.addWidget(btns)

    # -- result ---------------------------------------------------------

    def mods(self) -> list[str]:
        out: list[str] = []

        pri = self._priority.value()
        if pri == "__clear__":
            out.append("priority:")
        elif pri:
            out.append(f"priority:{pri}")

        proj = self._project.currentText().strip()
        if proj and proj != _NOCHANGE:
            out.append(f"project:{proj}")
        elif self._project.currentIndex() != 0 and not proj:
            out.append("project:")

        for t in _tags(self._add_tags.text()):
            out.append(f"+{t}")
        for t in _tags(self._del_tags.text()):
            out.append(f"-{t}")

        for attr, row in (
            ("due", self._due),
            ("scheduled", self._scheduled),
            ("wait", self._wait),
        ):
            token = row.token(attr)
            if token is not None:
                out.append(token)

        return out

    def summary(self) -> str:
        m = self.mods()
        head = f"روی {fmt.num(self._count)} کار:"
        return head + "\n" + (" ".join(m) if m else "(بدون تغییر)")


class _DateRow(QWidget):
    """A Jalali picker plus a 'clear this date' checkbox."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QHBoxLayout

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._picker = JalaliDatePicker()
        row.addWidget(self._picker, 1)
        self._clear = QCheckBox("پاک‌کردن")
        self._clear.toggled.connect(lambda on: self._picker.setDisabled(on))
        row.addWidget(self._clear)

    def token(self, attr: str) -> str | None:
        if self._clear.isChecked():
            return f"{attr}:"
        g = self._picker.gregorian_string()
        return f"{attr}:{g}" if g else None
