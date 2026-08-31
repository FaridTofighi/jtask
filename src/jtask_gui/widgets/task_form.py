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

from .. import tokens as tok
from ..bidi import bind_auto_direction
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
        row.setSpacing(tok.SP_6)
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
        self.setWindowTitle(t("form.title.add") if mode == "add" else t("form.title.log"))
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(tok.SP_10)

        self._submitted = False  # no validation hint until a submit is attempted
        self._description = QLineEdit()
        self._description.setPlaceholderText(t("form.description.placeholder"))
        self._description.textChanged.connect(self._revalidate)
        bind_auto_direction(self._description)
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
        self._description.editingFinished.connect(self._on_field_left)

        self._recur = RecurrenceBuilder()
        self._recur.recurrenceChanged.connect(self._revalidate)
        recur_row = QHBoxLayout()
        recur_row.setContentsMargins(0, 0, 0, 0)
        recur_row.setSpacing(tok.SP_6)
        recur_row.addWidget(self._recur, 1)
        self._recur_template_btn = QPushButton(t("form.recur.from_template"))
        self._recur_template_btn.clicked.connect(self._pick_recur_template)
        recur_row.addWidget(self._recur_template_btn)
        recur_wrap = QWidget()
        recur_wrap.setLayout(recur_row)
        self._recur_wrap = recur_wrap
        form.addRow(t("word.recurrence"), recur_wrap)

        self._depends = _DependsField()
        form.addRow(t("word.dependencies"), self._depends)

        if mode == "log":
            # a task logged as already-done cannot meaningfully recur
            form.setRowVisible(self._recur_wrap, False)

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
        self._ok.clicked.connect(self._try_accept)
        root.addWidget(btns)

        self._ok.setEnabled(not self._problems())  # button state only — no hint

    # -- validation ---------------------------------------------------
    # A disabled OK button is fine on a pristine form; a red error message is
    # not (§6.1). The hint appears only after a submit attempt or after the
    # description field has been touched and left empty.

    def _problems(self) -> list[str]:
        out: list[str] = []
        if not self._description.text().strip():
            out.append(t("form.err.description_required"))
        if self._recur.value() and not self._dates["due"].gregorian_string():
            out.append(t("form.err.recur_needs_due"))
        return out

    def _revalidate(self, *_a: object) -> None:
        problems = self._problems()
        self._ok.setEnabled(not problems)
        if self._submitted:
            self._show_problems(problems)

    def _show_problems(self, problems: list[str] | None = None) -> None:
        problems = self._problems() if problems is None else problems
        self._hint.setText(" ".join(problems))
        self._hint.setVisible(bool(problems))

    def _on_field_left(self) -> None:
        if not self._description.text().strip():
            self._submitted = True  # they engaged the required field and left it empty
            self._show_problems()

    def _try_accept(self) -> None:
        self._submitted = True
        problems = self._problems()
        self._show_problems(problems)
        if not problems:
            self.accept()

    # -- recurrence templates -------------------------------------------

    def _pick_recur_template(self) -> None:
        from ..workers import submit

        def fetch() -> list[dict]:
            from jtask import reports

            return reports.recurring_templates()

        def choose(templates: list[dict]) -> None:
            if not templates:
                QInputDialog.getItem(
                    self, t("form.recur.templates.title"),
                    t("form.recur.templates.none"), [""], 0, False,
                )
                return
            labels = [
                f"{tpl['description']}  ·  {tpl['recur']}" for tpl in templates
            ]
            text, ok = QInputDialog.getItem(
                self, t("form.recur.templates.title"),
                t("form.recur.templates.label"), labels, 0, False,
            )
            if not ok or not text:
                return
            tpl = templates[labels.index(text)]
            if not self._description.text().strip():
                self._description.setText(tpl["description"])
            if tpl.get("project"):
                self._project.setCurrentText(tpl["project"])
            if tpl.get("tags"):
                self._tags.set_tags(sorted(set(self._tags.tags()) | set(tpl["tags"])))
            self._recur.set_value(tpl["recur"])
            self._revalidate()

        submit(fetch, choose)

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
