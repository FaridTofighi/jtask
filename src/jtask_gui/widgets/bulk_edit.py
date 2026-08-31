"""Bulk field editor — one form that modifies many tasks at once (§ M5).

Only the fields the user actually touches are emitted; everything left on the
"no change" sentinel is omitted from the resulting ``task … modify`` mods.
Dates come back Taskwarrior-ready (Gregorian) from the shared Jalali picker, so
the caller must *not* run them through ``rewrite_args`` again.
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
from .. import tokens as tok
from ..i18n import t
from .jalali_date_picker import JalaliDatePicker
from .segmented import SegmentedControl

_TAG_SPLIT = re.compile(r"[\s,، ]+")


def _tags(text: str) -> list[str]:
    return [x.lstrip("+-#") for x in _TAG_SPLIT.split(text.strip()) if x.lstrip("+-#")]


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
        self.setWindowTitle(t("bulk.title"))
        self.setMinimumWidth(460)
        self._count = count

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(tok.SP_10)

        self._priority = SegmentedControl(
            [
                (t("bulk.no_change"), None),
                (t("priority.h"), "H"),
                (t("priority.m"), "M"),
                (t("priority.l"), "L"),
                (t("bulk.priority.clear"), "__clear__"),
            ]
        )
        form.addRow(t("word.priority"), self._priority)

        self._project = QComboBox()
        self._project.setEditable(True)
        self._project.addItem(t("bulk.no_change"))
        for p in projects or []:
            self._project.addItem(p)
        self._project.setCurrentIndex(0)
        form.addRow(t("word.project"), self._project)

        self._add_tags = QLineEdit()
        self._add_tags.setPlaceholderText(t("bulk.add_tags.placeholder"))
        form.addRow(t("bulk.add_tags"), self._add_tags)

        self._del_tags = QLineEdit()
        self._del_tags.setPlaceholderText(t("bulk.del_tags.placeholder"))
        form.addRow(t("bulk.del_tags"), self._del_tags)

        self._due = _DateRow()
        form.addRow(t("word.due"), self._due)
        self._scheduled = _DateRow()
        form.addRow(t("word.scheduled"), self._scheduled)
        self._wait = _DateRow()
        form.addRow(t("word.wait"), self._wait)
        self._until = _DateRow()
        form.addRow(t("word.until"), self._until)

        root.addLayout(form)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        ok = btns.addButton(t("btn.apply"), QDialogButtonBox.ButtonRole.AcceptRole)
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
        if proj and proj != t("bulk.no_change"):
            out.append(f"project:{proj}")
        elif self._project.currentIndex() != 0 and not proj:
            out.append("project:")

        for tag in _tags(self._add_tags.text()):
            out.append(f"+{tag}")
        for tag in _tags(self._del_tags.text()):
            out.append(f"-{tag}")

        for attr, row in (
            ("due", self._due),
            ("scheduled", self._scheduled),
            ("wait", self._wait),
            ("until", self._until),
        ):
            token = row.token(attr)
            if token is not None:
                out.append(token)

        return out

    def summary(self) -> str:
        m = self.mods()
        head = t("bulk.summary.head", count=fmt.num(self._count))
        return head + "\n" + (" ".join(m) if m else t("bulk.summary.none"))


class _DateRow(QWidget):
    """A Jalali picker plus a 'clear this date' checkbox."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QHBoxLayout

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(tok.SP_6)
        self._picker = JalaliDatePicker()
        row.addWidget(self._picker, 1)
        self._clear = QCheckBox(t("bulk.date.clear"))
        self._clear.toggled.connect(lambda on: self._picker.setDisabled(on))
        row.addWidget(self._clear)

    def token(self, attr: str) -> str | None:
        if self._clear.isChecked():
            return f"{attr}:"
        g = self._picker.gregorian_string()
        return f"{attr}:{g}" if g else None
