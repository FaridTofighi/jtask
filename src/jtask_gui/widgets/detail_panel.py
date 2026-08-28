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
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali, taskwarrior
from jtask.rtl import bidi_isolate

from .. import fmt
from .chips import TagChipEditor
from .jalali_date_picker import JalaliDatePicker
from .recurrence_builder import RecurrenceBuilder

_PRIORITIES = [("بدون", ""), ("زیاد", "H"), ("متوسط", "M"), ("کم", "L")]
_STATUS_FA = {
    "pending": "در جریان", "completed": "انجام‌شده", "waiting": "در انتظار",
    "deleted": "حذف‌شده", "recurring": "تکرارشونده",
}
_DATE_FIELDS = [("due", "سررسید", True), ("scheduled", "زمان‌بندی", True),
                ("wait", "انتظار", False), ("until", "مهلت", False)]


class DetailPanel(QScrollArea):
    saveRequested = pyqtSignal(str, list)      # uuid, modification tokens
    annotateRequested = pyqtSignal(str, str)   # uuid, text
    denotateRequested = pyqtSignal(str, str)
    opened = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._task: dict | None = None
        self._dirty_dates: set[str] = set()

        body = QWidget()
        body.setObjectName("DetailPanel")
        self.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        top = QHBoxLayout()
        self._title = QLabel("جزئیات کار")
        self._title.setObjectName("H2")
        close = QPushButton("بستن")
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
        form.addRow("شرح", self._description)

        self._project = QComboBox()
        self._project.setEditable(True)
        form.addRow("پروژه", self._project)

        self._tags = TagChipEditor()
        form.addRow("برچسب‌ها", self._tags)

        self._priority = QComboBox()
        for label, _ in _PRIORITIES:
            self._priority.addItem(label)
        form.addRow("اولویت", self._priority)

        self._status = QLabel("—")
        form.addRow("وضعیت", self._status)

        self._dates: dict[str, JalaliDatePicker] = {}
        for key, label, with_time in _DATE_FIELDS:
            picker = JalaliDatePicker(with_time=with_time)
            picker.dateChanged.connect(lambda _v, k=key: self._dirty_dates.add(k))
            self._dates[key] = picker
            form.addRow(label, picker)

        self._recur = RecurrenceBuilder()
        form.addRow("تکرار", self._recur)

        self._depends = QLineEdit()
        self._depends.setPlaceholderText("شناسه‌ها با کاما، مثلاً 3,7")
        dep_row = QHBoxLayout()
        dep_row.addWidget(self._depends, 1)
        dep_btn = QPushButton("افزودن…")
        dep_btn.clicked.connect(self._pick_dependency)
        dep_row.addWidget(dep_btn)
        dep_wrap = QWidget()
        dep_wrap.setLayout(dep_row)
        form.addRow("وابستگی‌ها", dep_wrap)

        # annotations
        outer.addWidget(QLabel("یادداشت‌ها"))
        self._annotations = QListWidget()
        self._annotations.setMaximumHeight(140)
        outer.addWidget(self._annotations)
        ann_row = QHBoxLayout()
        self._ann_input = QLineEdit()
        self._ann_input.setPlaceholderText("یادداشت جدید…")
        ann_add = QPushButton("افزودن")
        ann_add.clicked.connect(self._add_annotation)
        ann_del = QPushButton("حذف انتخاب‌شده")
        ann_del.clicked.connect(self._del_annotation)
        ann_row.addWidget(self._ann_input, 1)
        ann_row.addWidget(ann_add)
        ann_row.addWidget(ann_del)
        outer.addLayout(ann_row)

        # UDAs
        self._uda_form = QFormLayout()
        self._uda_widgets: dict[str, QWidget] = {}
        outer.addWidget(QLabel("ویژگی‌های سفارشی (UDA)"))
        uda_wrap = QWidget()
        uda_wrap.setLayout(self._uda_form)
        outer.addWidget(uda_wrap)

        # urgency + audit
        self._urgency = QLabel("—")
        form_bottom = QFormLayout()
        form_bottom.addRow("فوریت", self._urgency)
        self._audit = QLabel("")
        self._audit.setObjectName("Muted")
        form_bottom.addRow("سوابق", self._audit)
        outer.addLayout(form_bottom)

        save = QPushButton("ذخیرهٔ تغییرات")
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

    def load_task(self, task: dict) -> None:
        self._task = task
        self._dirty_dates.clear()
        self._title.setText(f"کار #{task.get('id', '—')}")
        self._description.setText(task.get("description", ""))
        self._project.setCurrentText(task.get("project", ""))
        self._tags.set_tags([t for t in (task.get("tags") or []) if not t.isupper()])
        pri = task.get("priority", "")
        self._priority.setCurrentIndex(
            next((i for i, (_, v) in enumerate(_PRIORITIES) if v == pri), 0)
        )
        self._status.setText(_STATUS_FA.get(task.get("status", ""), task.get("status", "—")))
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
        self._audit.setText(self._audit_text(task))
        self.opened.emit()

    def _audit_text(self, task: dict) -> str:
        parts = []
        for key, label in (("entry", "ایجاد"), ("modified", "ویرایش"), ("end", "پایان")):
            raw = task.get(f"{key}_gregorian") or task.get(key)
            if raw:
                shown = bidi_isolate(jalali.from_taskwarrior(raw, fmt="short"))
                parts.append(f"{label}: {shown}")
        return "   ·   ".join(parts)

    def _load_annotations(self, task: dict) -> None:
        self._annotations.clear()
        for ann in task.get("annotations") or []:
            when = ann.get("entry", "")
            if when and not when.startswith("۱"):  # raw gregorian -> jalali
                when = jalali.from_taskwarrior(when, fmt="short")
            item = QListWidgetItem(f"{when} — {ann.get('description', '')}")
            item.setData(Qt.ItemDataRole.UserRole, ann.get("description", ""))
            self._annotations.addItem(item)

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
            labels = [f"{t.get('id')} — {t.get('description')}" for t in tasks]
            text, ok = QInputDialog.getItem(self, "افزودن وابستگی", "کار:", labels, 0, False)
            if ok and text:
                tid = text.split(" — ")[0]
                cur = [x for x in self._depends.text().split(",") if x]
                if tid not in cur:
                    cur.append(tid)
                self._depends.setText(",".join(cur))

        submit(fetch, choose)

    def _add_annotation(self) -> None:
        if self._task and self._ann_input.text().strip():
            self.annotateRequested.emit(self._task["uuid"], self._ann_input.text().strip())
            self._ann_input.clear()

    def _del_annotation(self) -> None:
        item = self._annotations.currentItem()
        if self._task and item:
            self.denotateRequested.emit(self._task["uuid"], item.data(Qt.ItemDataRole.UserRole))

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
