"""Slide-in detail/edit panel exposing every attribute of a task."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior
from jtask.rtl import auto_isolate, bidi_isolate

from .. import fmt
from .. import tokens as tok
from ..bidi import bind_auto_direction
from ..calendar_system import active
from ..i18n import t
from .chips import TagChipEditor
from .jalali_date_picker import JalaliDatePicker
from .recurrence_builder import RecurrenceBuilder

_PRIORITIES = [
    ("detail.priority.none", ""), ("detail.priority.h", "H"),
    ("detail.priority.m", "M"), ("detail.priority.l", "L"),
]
_STATUS_KEY = {
    "pending": "status.pending", "completed": "status.completed", "waiting": "status.waiting",
    "deleted": "status.deleted", "recurring": "status.recurring",
}
_DATE_FIELDS = [("due", "word.due", True), ("scheduled", "word.scheduled", True),
                ("wait", "detail.date.wait", False), ("until", "word.until", False)]


class DetailPanel(QScrollArea):
    saveRequested = pyqtSignal(str, list)      # uuid, modification tokens
    opened = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._task: dict | None = None
        self._dirty_dates: set[str] = set()
        self._all_tasks: list[dict] = []

        body = QWidget()
        body.setObjectName("DetailPanel")
        self.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(*tok.INSET_PANEL)
        outer.setSpacing(tok.SP_10)

        top = QHBoxLayout()
        self._title = QLabel(t("detail.title"))
        self._title.setObjectName("H2")
        close = QPushButton(t("btn.close"))
        close.clicked.connect(self.hide_panel)
        top.addWidget(self._title, 1)
        top.addWidget(close)
        outer.addLayout(top)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        outer.addLayout(form)

        self._description = QLineEdit()
        bind_auto_direction(self._description)
        form.addRow(t("word.description"), self._description)

        self._project = QComboBox()
        self._project.setEditable(True)
        # don't let a long project path (or a long entry in the list) stretch
        # the form column and, through it, the whole edit panel
        self._project.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._project.setMinimumContentsLength(12)
        form.addRow(t("word.project"), self._project)

        self._tags = TagChipEditor()
        form.addRow(t("word.tags"), self._tags)

        self._priority = QComboBox()
        for label_key, _ in _PRIORITIES:
            self._priority.addItem(t(label_key))
        form.addRow(t("word.priority"), self._priority)

        self._status = QLabel("—")
        form.addRow(t("word.status"), self._status)

        self._dates: dict[str, JalaliDatePicker] = {}
        for key, label_key, with_time in _DATE_FIELDS:
            picker = JalaliDatePicker(with_time=with_time)
            picker.dateChanged.connect(lambda _v, k=key: self._dirty_dates.add(k))
            self._dates[key] = picker
            form.addRow(t(label_key), picker)

        self._recur = RecurrenceBuilder()
        form.addRow(t("detail.field.recurrence"), self._recur)

        self._depends = QLineEdit()
        self._depends.setPlaceholderText(t("detail.deps.placeholder"))
        dep_row = QHBoxLayout()
        dep_row.addWidget(self._depends, 1)
        dep_btn = QPushButton(t("btn.add_ellipsis"))
        dep_btn.clicked.connect(self._pick_dependency)
        dep_row.addWidget(dep_btn)
        dep_wrap = QWidget()
        dep_wrap.setLayout(dep_row)
        form.addRow(t("word.dependencies"), dep_wrap)

        # annotations — read-only summary here; full editing is the «یادداشت‌ها» tab
        outer.addWidget(QLabel(t("detail.annotations")))
        self._ann_summary = QLabel("—")
        self._ann_summary.setObjectName("Muted")
        self._ann_summary.setWordWrap(True)
        outer.addWidget(self._ann_summary)

        # UDAs
        self._uda_form = QFormLayout()
        self._uda_widgets: dict[str, QWidget] = {}
        outer.addWidget(QLabel(t("detail.udas")))
        uda_wrap = QWidget()
        uda_wrap.setLayout(self._uda_form)
        outer.addWidget(uda_wrap)

        # dependency graph
        from .dep_graph import DependencyGraph

        self._dep_label = QLabel(t("detail.dep_graph"))
        outer.addWidget(self._dep_label)
        self._dep_graph = DependencyGraph()
        outer.addWidget(self._dep_graph)

        # urgency + audit
        urg_row = QHBoxLayout()
        self._urgency = QLabel("—")
        urg_row.addWidget(self._urgency, 1)
        self._why_btn = QPushButton(t("detail.why"))
        self._why_btn.setCheckable(True)
        self._why_btn.toggled.connect(self._toggle_why)
        urg_row.addWidget(self._why_btn)
        urg_wrap = QWidget()
        urg_wrap.setLayout(urg_row)

        form_bottom = QFormLayout()
        form_bottom.addRow(t("detail.urgency"), urg_wrap)
        self._why = QLabel("")
        self._why.setObjectName("Muted")
        self._why.setWordWrap(True)
        self._why.setVisible(False)
        form_bottom.addRow("", self._why)
        self._audit = QLabel("")
        self._audit.setObjectName("Muted")
        form_bottom.addRow(t("detail.audit"), self._audit)
        outer.addLayout(form_bottom)

        save = QPushButton(t("detail.save"))
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        outer.addWidget(save)
        outer.addStretch(1)

    # --- show / hide -------------------------------------------
    # Visibility is owned by MainWindow (splitter panes reserve space even at
    # width 0, so the panel must actually be hidden when closed). The panel
    # only signals intent.

    def hide_panel(self) -> None:
        self.closed.emit()

    # --- population -------------------------------------------

    def set_projects(self, projects: list[str]) -> None:
        current = self._project.currentText()
        self._project.clear()
        self._project.addItems([""] + projects)
        self._project.setCurrentText(current)

    def set_tag_completions(self, tags: list[str]) -> None:
        self._tags.set_completions(tags)

    def set_all_tasks(self, tasks: list[dict]) -> None:
        self._all_tasks = tasks
        if self._task:
            self._dep_graph.show_task(self._task, tasks)

    def set_theme(self, name: str) -> None:
        self._dep_graph.set_theme(name)
        if self._task and getattr(self, "_all_tasks", None):
            self._dep_graph.show_task(self._task, self._all_tasks)

    def _toggle_why(self, on: bool) -> None:
        self._why.setVisible(on)
        if on and self._task:
            from ..workers import submit

            uuid = self._task["uuid"]
            submit(lambda: taskwarrior.urgency_terms(uuid), self._show_why)

    def _show_why(self, terms: list[dict]) -> None:
        if not terms:
            self._why.setText(t("detail.why.unavailable"))
            return
        lines = [
            f"{t['label']}:  {fmt.num(round(float(t['value']), 1), isolate=True)}"
            for t in sorted(terms, key=lambda x: -abs(float(x["value"])))
        ]
        self._why.setText("   ·   ".join(lines))

    def load_task(self, task: dict) -> None:
        self._task = task
        self._dirty_dates.clear()
        self.verticalScrollBar().setValue(0)  # open at the top — title + Close visible
        self._title.setText(t("detail.task_number", id=task.get("id", "—")))
        self._description.setText(task.get("description", ""))
        self._project.setCurrentText(task.get("project", ""))
        self._tags.set_tags([t for t in (task.get("tags") or []) if not t.isupper()])
        pri = task.get("priority", "")
        self._priority.setCurrentIndex(
            next((i for i, (_, v) in enumerate(_PRIORITIES) if v == pri), 0)
        )
        st = task.get("status", "")
        self._status.setText(t(_STATUS_KEY[st]) if st in _STATUS_KEY else (st or "—"))
        for key, picker in self._dates.items():
            picker.set_from_taskwarrior(task.get(f"{key}_gregorian") or task.get(key) or "")
        self._dirty_dates.clear()
        self._recur.set_value(task.get("recur", ""))
        deps = task.get("depends") or []
        if isinstance(deps, str):
            deps = deps.split(",")
        self._depends.setText(",".join(str(d) for d in deps))
        self._load_annotations(task)
        self._load_udas(task)
        self._urgency.setText(fmt.num(round(float(task.get("urgency", 0)), 1), isolate=True))
        self._why_btn.setChecked(False)
        self._why.clear()
        self._audit.setText(self._audit_text(task))
        self._dep_graph.show_task(task, self._all_tasks)
        self.opened.emit()

    def _audit_text(self, task: dict) -> str:
        parts = []
        anchors = (
            ("entry", t("detail.anchor.entry")),
            ("modified", t("detail.anchor.modified")),
            ("end", t("detail.anchor.end")),
        )
        for key, label in anchors:
            raw = task.get(f"{key}_gregorian") or task.get(key)
            if raw:
                shown = bidi_isolate(active().format_utc(raw, "short"))
                parts.append(f"{label}: {shown}")
        return "   ·   ".join(parts)

    def _load_annotations(self, task: dict) -> None:
        anns = task.get("annotations") or []
        if not anns:
            self._ann_summary.setText(t("detail.annotations.empty"))
            return
        first = auto_isolate(anns[0].get("description", ""))
        if len(anns) > 1:
            self._ann_summary.setText(
                t("detail.annotations.summary", first=first, more=fmt.num(len(anns) - 1))
            )
        else:
            self._ann_summary.setText(first)

    def _load_udas(self, task: dict) -> None:
        while self._uda_form.rowCount():
            self._uda_form.removeRow(0)
        self._uda_widgets.clear()
        for name, spec in taskwarrior.uda_definitions().items():
            utype = spec.get("type", "string")
            if utype == "date":
                w: QWidget = JalaliDatePicker()
                w.set_from_taskwarrior(task.get(f"{name}_gregorian") or task.get(name) or "")
            elif utype == "numeric":
                from PyQt6.QtWidgets import QDoubleSpinBox

                w = QDoubleSpinBox()
                w.setRange(-1e9, 1e9)
                if task.get(name) not in (None, ""):
                    w.setValue(float(task[name]))
            else:
                w = QLineEdit(str(task.get(name, "")))
            self._uda_widgets[name] = w
            self._uda_form.addRow(spec.get("label", name), w)

    # --- editing actions -------------------------------------

    def _pick_dependency(self) -> None:
        from ..workers import submit

        def fetch():
            from jtask import reports
            return reports.report_next()

        def choose(tasks):
            labels = [f"{x.get('id')} — {x.get('description')}" for x in tasks]
            text, ok = QInputDialog.getItem(
                self, t("form.deps.pick.title"), t("form.deps.pick.label"),
                labels, 0, False,
            )
            if ok and text:
                tid = text.split(" — ")[0]
                cur = [x for x in self._depends.text().split(",") if x]
                if tid not in cur:
                    cur.append(tid)
                self._depends.setText(",".join(cur))

        submit(fetch, choose)

    def _save(self) -> None:
        if not self._task:
            return
        mods: list[str] = []
        orig = self._task

        if self._description.text() != orig.get("description", ""):
            mods.append(self._description.text())

        proj = self._project.currentText().strip()
        if proj != (orig.get("project") or ""):
            mods.append(f"project:{proj}")

        new_tags = set(self._tags.tags())
        old_tags = {t for t in (orig.get("tags") or []) if not t.isupper()}
        mods += [f"+{t}" for t in new_tags - old_tags]
        mods += [f"-{t}" for t in old_tags - new_tags]

        pri = _PRIORITIES[self._priority.currentIndex()][1]
        if pri != (orig.get("priority") or ""):
            mods.append(f"priority:{pri}")

        for key in self._dates:
            if key in self._dirty_dates:
                mods.append(f"{key}:{self._dates[key].gregorian_string()}")

        recur = self._recur.value()
        if recur != (orig.get("recur") or ""):
            mods.append(f"recur:{recur}")

        deps = self._depends.text().strip()
        old_deps = orig.get("depends") or []
        if isinstance(old_deps, list):
            old_deps = ",".join(str(d) for d in old_deps)
        if deps != old_deps:
            mods.append(f"depends:{deps}")

        for name, w in self._uda_widgets.items():
            val = self._uda_value(w)
            if str(val) != str(orig.get(name, "")):
                mods.append(f"{name}:{val}")

        if mods:
            self.saveRequested.emit(orig["uuid"], mods)

    @staticmethod
    def _uda_value(w: QWidget) -> str:
        if isinstance(w, JalaliDatePicker):
            return w.gregorian_string()
        if isinstance(w, QLineEdit):
            return w.text()
        from PyQt6.QtWidgets import QDoubleSpinBox

        if isinstance(w, QDoubleSpinBox):
            return str(w.value())
        return ""
