"""Visual filter builder — chips/dropdowns that compose a Taskwarrior filter.

Produces the exact same token list the raw filter box would, and shows the
equivalent raw string (copyable) so it doubles as a way to learn the syntax.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from .chips import TagChipEditor
from .jalali_date_picker import JalaliDatePicker

_STATUS = [("همه", ""), ("در جریان", "pending"), ("در انتظار", "waiting"),
           ("تکمیل‌شده", "completed"), ("حذف‌شده", "deleted")]
_PRIORITY = [("همه", ""), ("زیاد", "H"), ("متوسط", "M"), ("کم", "L"), ("بدون", "")]


class FilterBuilder(QDialog):
    applied = pyqtSignal(list, str)  # (rewritten tokens, raw display string)

    def __init__(self, initial_raw: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("سازندهٔ فیلتر")
        self.setMinimumWidth(440)
        root = QVBoxLayout(self)

        form = QFormLayout()
        root.addLayout(form)

        self._project = QComboBox()
        self._project.setEditable(True)
        self._project.addItem("")
        try:
            self._project.addItems(taskwarrior.list_projects())
        except Exception:  # noqa: BLE001
            pass
        self._project.currentTextChanged.connect(self._update)
        form.addRow("پروژه", self._project)

        self._tags_inc = TagChipEditor()
        self._tags_exc = TagChipEditor()
        for chips in (self._tags_inc, self._tags_exc):
            try:
                chips.set_completions(taskwarrior.list_tags())
            except Exception:  # noqa: BLE001
                pass
            chips.tagsChanged.connect(self._update)
        form.addRow("برچسب‌های شامل (+)", self._tags_inc)
        form.addRow("برچسب‌های مستثنا (-)", self._tags_exc)

        self._status = QComboBox()
        for label, val in _STATUS:
            self._status.addItem(label, val)
        self._status.currentIndexChanged.connect(self._update)
        form.addRow("وضعیت", self._status)

        self._priority = QComboBox()
        for label, val in _PRIORITY[:4]:
            self._priority.addItem(label, val)
        self._priority.currentIndexChanged.connect(self._update)
        form.addRow("اولویت", self._priority)

        self._due_after = JalaliDatePicker()
        self._due_before = JalaliDatePicker()
        for p in (self._due_after, self._due_before):
            p.dateChanged.connect(self._update)
        form.addRow("سررسید بعد از", self._due_after)
        form.addRow("سررسید پیش از", self._due_before)

        self._extra = QLineEdit()
        self._extra.setPlaceholderText("توکن‌های خام اضافی…")
        self._extra.textChanged.connect(self._update)
        form.addRow("افزودهٔ خام", self._extra)

        raw_row = QHBoxLayout()
        self._raw = QLabel("—")
        self._raw.setObjectName("Muted")
        self._raw.setWordWrap(True)
        raw_row.addWidget(QLabel("معادل خام:"))
        raw_row.addWidget(self._raw, 1)
        copy = QPushButton("رونوشت")
        copy.clicked.connect(self._copy)
        raw_row.addWidget(copy)
        root.addLayout(raw_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setText("اعمال")
        apply_btn.setObjectName("Primary")
        apply_btn.clicked.connect(self._emit)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("انصراف")
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if initial_raw:
            self._extra.setText(initial_raw)
        self._update()

    # --- composition -------------------------------------------

    def _raw_tokens(self) -> list[str]:
        tokens: list[str] = []
        proj = self._project.currentText().strip()
        if proj:
            tokens.append(f"project:{proj}")
        for t in self._tags_inc.tags():
            tokens.append(f"+{t}")
        for t in self._tags_exc.tags():
            tokens.append(f"-{t}")
        status = self._status.currentData()
        if status:
            tokens.append(f"status:{status}")
        pri = self._priority.currentData()
        if pri:
            tokens.append(f"priority:{pri}")
        if self._due_after.value() is not None:
            tokens.append(f"due.after:{self._due_after.gregorian_string()}")
        if self._due_before.value() is not None:
            tokens.append(f"due.before:{self._due_before.gregorian_string()}")
        if self._extra.text().strip():
            tokens.extend(self._extra.text().split())
        return tokens

    def _update(self) -> None:
        raw = " ".join(self._raw_tokens())
        self._raw.setText(raw or "(بدون فیلتر)")

    def _copy(self) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(" ".join(self._raw_tokens()))

    def _emit(self) -> None:
        # date pickers already emit Gregorian, so the tokens are Taskwarrior-ready
        raw = self._raw_tokens()
        self.applied.emit(raw, " ".join(raw))
        self.accept()
