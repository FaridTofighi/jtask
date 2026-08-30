"""Full task form — the native counterpart of ``task add`` / ``task log`` (§ M5).

Every field maps to one Taskwarrior token.  Dates come from the shared Jalali
picker already Gregorian, so the produced ``args()`` must be handed straight to
``taskwarrior.add`` / ``taskwarrior.log`` *without* ``rewrite_args``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from ..i18n import t
from .chips import TagChipEditor
from .jalali_date_picker import JalaliDatePicker
from .recurrence_builder import RecurrenceBuilder
from .segmented import SegmentedControl

_PRIORITY = [("priority.none", ""), ("priority.h", "H"), ("priority.m", "M"), ("priority.l", "L")]
_DATES = [
    ("due", "word.due", True),
    ("scheduled", "word.scheduled", True),
    ("wait", "word.wait", False),
    ("until", "word.until", False),
]


class _DependsField(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(t("form.deps.placeholder"))
        row.addWidget(self._edit, 1)
        btn = QPushButton(t("btn.add_ellipsis"))
        btn.clicked.connect(self._pick)
        row.addWidget(btn)

    def _pick(self) -> None:
        from ..workers import submit

        def fetch() -> list[dict]:
            from jtask import reports

            return reports.report_next()

        def choose(tasks: list[dict]) -> None:
            labels = [
                f"{t.get('id')} — {t.get('description')}" for t in tasks if t.get("id")
            ]
            if not labels:
                return
            text, ok = QInputDialog.getItem(
                self, t("form.deps.pick.title"), t("form.deps.pick.label"), labels, 0, False
            )
            if ok and text:
                tid = text.split(" — ")[0]
                cur = [x for x in self._edit.text().split(",") if x.strip()]
                if tid not in cur:
                    cur.append(tid)
                self._edit.setText(",".join(cur))

        submit(fetch, choose)

    def value(self) -> str:
        return ",".join(x.strip() for x in self._edit.text().split(",") if x.strip())


class TaskFormDialog(QDialog):
    def __init__(
        self,
        mode: str = "add",
        projects: list[str] | None = None,
        tags: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setObjectName("TaskFormDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle(t("form.title.add") if mode == "add" else t("form.title.log"))
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self._description = QLineEdit()
        self._description.setPlaceholderText(t("form.description.placeholder"))
        self._description.textChanged.connect(self._revalidate)
        form.addRow(t("word.description"), self._description)

        self._project = QComboBox()
        self._project.setEditable(True)
        self._project.addItem("")
        for p in projects or []:
            self._project.addItem(p)
        form.addRow(t("word.project"), self._project)

        self._tags = TagChipEditor()
        self._tags.set_completions(tags or [])
        form.addRow(t("word.tags"), self._tags)

        self._priority = SegmentedControl(
            [(t(lbl), val) for lbl, val in _PRIORITY]
        )
        form.addRow(t("word.priority"), self._priority)

        self._dates: dict[str, JalaliDatePicker] = {}
        for key, label, with_time in _DATES:
            picker = JalaliDatePicker(with_time=with_time)
            self._dates[key] = picker
            form.addRow(t(label), picker)
            if key == "due":
                picker.dateChanged.connect(self._revalidate)

        self._recur = RecurrenceBuilder()
        self._recur.recurrenceChanged.connect(self._revalidate)
        form.addRow(t("word.recurrence"), self._recur)

        self._depends = _DependsField()
        form.addRow(t("word.dependencies"), self._depends)

        if mode == "log":
            # a task logged as already-done cannot meaningfully recur
            form.setRowVisible(self._recur, False)

        root.addLayout(form)

        self._hint = QLabel("")
        self._hint.setObjectName("FormHint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(False)
        root.addWidget(self._hint)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        self._ok = btns.addButton(
            t("form.ok.add") if mode == "add" else t("form.ok.log"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self._ok.setObjectName("Primary")
        self._ok.clicked.connect(self.accept)
        root.addWidget(btns)

        self._revalidate()

    # -- validation ---------------------------------------------------

    def _revalidate(self, *_a: object) -> None:
        problems: list[str] = []
        if not self._description.text().strip():
            problems.append(t("form.err.description_required"))
        if self._recur.value() and not self._dates["due"].gregorian_string():
            problems.append(t("form.err.recur_needs_due"))
        self._ok.setEnabled(not problems)
        self._hint.setText(" ".join(problems))
        self._hint.setVisible(bool(problems))

    # -- result -----------------------------------------------------

    def args(self) -> list[str]:
        out: list[str] = [self._description.text().strip()]

        proj = self._project.currentText().strip()
        if proj:
            out.append(f"project:{proj}")

        for tag in self._tags.tags():
            out.append(f"+{tag}")

        pri = self._priority.value()
        if pri:
            out.append(f"priority:{pri}")

        for key in ("due", "scheduled", "wait", "until"):
            g = self._dates[key].gregorian_string()
            if g:
                out.append(f"{key}:{g}")

        if self._recur.value():
            out.append(f"recur:{self._recur.value()}")

        dep = self._depends.value()
        if dep:
            out.append(f"depends:{dep}")

        return out

    def run(self) -> str:
        """Execute against Taskwarrior (add or log) and return its stdout."""
        if self.mode == "log":
            return taskwarrior.log(self.args())
        return taskwarrior.add(self.args())
