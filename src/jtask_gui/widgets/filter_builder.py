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

from .. import tokens as tok
from ..i18n import t
from .chips import TagChipEditor
from .jalali_date_picker import JalaliDatePicker

_STATUS = [
    ("fb.status.all", ""), ("status.pending", "pending"),
    ("status.waiting", "waiting"), ("status.completed", "completed"),
    ("status.deleted", "deleted"),
]
_PRIORITY = [
    ("fb.priority.all", ""), ("fb.priority.h", "H"), ("fb.priority.m", "M"),
    ("fb.priority.l", "L"), ("fb.priority.none", ""),
]
# common virtual tags worth a one-click toggle
_VTAGS = [
    ("fb.vtag.OVERDUE", "OVERDUE"), ("fb.vtag.DUE", "DUE"),
    ("fb.vtag.READY", "READY"), ("fb.vtag.ACTIVE", "ACTIVE"),
    ("fb.vtag.BLOCKED", "BLOCKED"), ("fb.vtag.BLOCKING", "BLOCKING"),
    ("fb.vtag.WAITING", "WAITING"), ("fb.vtag.TAGGED", "TAGGED"),
    ("fb.vtag.ANNOTATED", "ANNOTATED"),
]


class FilterBuilder(QDialog):
    applied = pyqtSignal(list, str)  # (rewritten tokens, raw display string)

    def __init__(self, initial_raw: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("fb.title"))
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
        form.addRow(t("word.project"), self._project)

        self._tags_inc = TagChipEditor()
        self._tags_exc = TagChipEditor()
        for chips in (self._tags_inc, self._tags_exc):
            try:
                chips.set_completions(taskwarrior.list_tags())
            except Exception:  # noqa: BLE001
                pass
            chips.tagsChanged.connect(self._update)
        form.addRow(t("fb.tags_include"), self._tags_inc)
        form.addRow(t("fb.tags_exclude"), self._tags_exc)

        self._status = QComboBox()
        for label_key, val in _STATUS:
            self._status.addItem(t(label_key), val)
        self._status.currentIndexChanged.connect(self._update)
        form.addRow(t("word.status"), self._status)

        self._priority = QComboBox()
        for label_key, val in _PRIORITY[:4]:
            self._priority.addItem(t(label_key), val)
        self._priority.currentIndexChanged.connect(self._update)
        form.addRow(t("word.priority"), self._priority)

        self._due_after = JalaliDatePicker()
        self._due_before = JalaliDatePicker()
        for p in (self._due_after, self._due_before):
            p.dateChanged.connect(self._update)
        form.addRow(t("fb.due_after"), self._due_after)
        form.addRow(t("fb.due_before"), self._due_before)

        self._ids = QLineEdit()
        self._ids.setPlaceholderText(t("fb.ids.placeholder"))
        self._ids.textChanged.connect(self._update)
        form.addRow(t("fb.ids"), self._ids)

        self._regex = QLineEdit()
        self._regex.setPlaceholderText(t("fb.regex.placeholder"))
        self._regex.textChanged.connect(self._update)
        form.addRow(t("fb.regex"), self._regex)

        self._uda_rows: list[tuple[str, str, QWidget, QComboBox | None]] = []
        try:
            udas = taskwarrior.uda_definitions()
        except Exception:  # noqa: BLE001
            udas = {}
        for name, spec in sorted(udas.items()):
            utype = spec.get("type", "string")
            values = taskwarrior.uda_values(name)
            op: QComboBox | None = None
            if utype == "date":
                editor: QWidget = JalaliDatePicker()
                editor.dateChanged.connect(self._update)
                op = self._op_combo(
                    [("fb.op.before", "before"), ("fb.op.after", "after")]
                )
            elif utype == "numeric":
                editor = QLineEdit()
                editor.textChanged.connect(self._update)
                op = self._op_combo(
                    [("fb.op.is", ""), ("fb.op.over", "over"), ("fb.op.under", "under")]
                )
            elif values:
                editor = QComboBox()
                editor.addItem("")
                editor.addItems(values)
                editor.currentIndexChanged.connect(self._update)
            else:
                editor = QLineEdit()
                editor.textChanged.connect(self._update)
            if op is not None:
                op.currentIndexChanged.connect(self._update)
                wrap = QWidget()
                h = QHBoxLayout(wrap)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(tok.SP_6)
                h.addWidget(op)
                h.addWidget(editor, 1)
                form.addRow(spec.get("label", name), wrap)
            else:
                form.addRow(spec.get("label", name), editor)
            self._uda_rows.append((name, utype, editor, op))

        from PyQt6.QtWidgets import QGridLayout, QToolButton

        vt_wrap = QWidget()
        grid = QGridLayout(vt_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(tok.SP_2)
        self._vtags: list[QToolButton] = []
        for i, (label_key, tag) in enumerate(_VTAGS):
            b = QToolButton()
            b.setText(t(label_key))
            b.setCheckable(True)
            b.setProperty("vtag", tag)
            b.toggled.connect(self._update)
            grid.addWidget(b, i // 3, i % 3)
            self._vtags.append(b)
        form.addRow(t("fb.vtags"), vt_wrap)

        self._extra = QLineEdit()
        self._extra.setPlaceholderText(t("fb.extra.placeholder"))
        self._extra.textChanged.connect(self._update)
        form.addRow(t("fb.extra"), self._extra)

        raw_row = QHBoxLayout()
        self._raw = QLabel("—")
        self._raw.setObjectName("Muted")
        self._raw.setWordWrap(True)
        raw_row.addWidget(QLabel(t("fb.raw_equiv")))
        raw_row.addWidget(self._raw, 1)
        copy = QPushButton(t("btn.copy"))
        copy.clicked.connect(self._copy)
        raw_row.addWidget(copy)
        root.addLayout(raw_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setText(t("btn.apply"))
        apply_btn.setObjectName("Primary")
        apply_btn.clicked.connect(self._emit)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("btn.cancel"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if initial_raw:
            self._extra.setText(initial_raw)
        self._update()

    def _op_combo(self, options: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        for label_key, val in options:
            combo.addItem(t(label_key), val)
        return combo

    def _uda_tokens(self) -> list[str]:
        tokens: list[str] = []
        for name, utype, editor, op in self._uda_rows:
            if utype == "date":
                if editor.value() is None:
                    continue
                modifier = op.currentData() if op is not None else "before"
                tokens.append(f"{name}.{modifier}:{editor.gregorian_string()}")
            elif isinstance(editor, QComboBox):
                val = editor.currentText().strip()
                if val:
                    tokens.append(f"{name}:{val}")
            else:
                val = editor.text().strip()
                if not val:
                    continue
                modifier = op.currentData() if op is not None else ""
                key = f"{name}.{modifier}" if modifier else name
                tokens.append(f"{key}:{val}")
        return tokens

    # --- composition -------------------------------------------

    def _raw_tokens(self) -> list[str]:
        tokens: list[str] = []
        proj = self._project.currentText().strip()
        if proj:
            tokens.append(f"project:{proj}")
        for tag in self._tags_inc.tags():
            tokens.append(f"+{tag}")
        for tag in self._tags_exc.tags():
            tokens.append(f"-{tag}")
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
        ids = self._ids.text().strip()
        if ids:
            tokens.append(ids)
        rx = self._regex.text().strip()
        if rx:
            tokens.append(f"/{rx.strip('/')}/")
        for b in self._vtags:
            if b.isChecked():
                tokens.append(f"+{b.property('vtag')}")
        tokens.extend(self._uda_tokens())
        if self._extra.text().strip():
            tokens.extend(self._extra.text().split())
        return tokens

    def _update(self) -> None:
        raw = " ".join(self._raw_tokens())
        self._raw.setText(raw or t("fb.no_filter"))

    def _copy(self) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(" ".join(self._raw_tokens()))

    def _emit(self) -> None:
        # date pickers already emit Gregorian, so the tokens are Taskwarrior-ready
        raw = self._raw_tokens()
        self.applied.emit(raw, " ".join(raw))
        self.accept()
