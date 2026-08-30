"""Configuration Manager — read every ``rc.*`` variable, write via ``task config``.

jtask never edits ``.taskrc`` text: edits and "reset to default" both go through
``taskwarrior.config_set`` / ``config_unset``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from ..workers import submit
from .confirm import confirm

_GROUPS = [
    ("همه", ""),
    ("عمومی", "general"),
    ("تاریخ و تقویم", "date"),
    ("گزارش‌ها", "report"),
    ("ویژگی‌های سفارشی", "uda"),
    ("زمینه‌ها", "context"),
    ("همگام‌سازی", "sync"),
    ("رنگ‌ها", "color"),
]
_DATE_PREFIXES = ("date", "weekstart", "due", "calendar")


def _group_of(name: str) -> str:
    head = name.split(".", 1)[0]
    if head in ("report", "uda", "context", "sync", "color"):
        return head
    if name.startswith(_DATE_PREFIXES):
        return "date"
    return "general"


class ConfigManager(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConfigManager")
        self._rows: list[tuple[str, str, str, bool]] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        from PyQt6.QtWidgets import QHBoxLayout

        bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("جست‌وجوی نام متغیر…")
        self._search.textChanged.connect(self._apply_filter)
        bar.addWidget(self._search, 1)
        self._group = QComboBox()
        for label, key in _GROUPS:
            self._group.addItem(label, key)
        self._group.currentIndexChanged.connect(self._apply_filter)
        bar.addWidget(self._group)
        lay.addLayout(bar)

        self._table = QTableWidget(0, 3)
        self._table.setObjectName("ConfigTable")
        self._table.setHorizontalHeaderLabels(["نام", "مقدار فعلی", "پیش‌فرض"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.doubleClicked.connect(self._edit_current)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self._table, 1)

        self._hint = QLabel("برای ویرایش روی یک ردیف دوبار کلیک کنید.")
        self._hint.setObjectName("Muted")
        lay.addWidget(self._hint)

    def reload(self) -> None:
        submit(self._collect, self._populate, lambda _e: None)

    @staticmethod
    def _collect() -> list[tuple[str, str, str, bool]]:
        current = taskwarrior._show_config()
        defaults = taskwarrior.config_defaults()
        names = set(taskwarrior.config_names()) | set(current)
        out = []
        for name in sorted(names):
            val = current.get(name, "")
            default = defaults.get(name, "")
            overridden = name in defaults
            out.append((name, val, default, overridden))
        return out

    def _populate(self, rows: list[tuple[str, str, str, bool]]) -> None:
        self._rows = rows
        self._apply_filter()

    def _apply_filter(self, *_a: object) -> None:
        needle = self._search.text().strip().lower()
        group = self._group.currentData()
        shown = [
            r for r in self._rows
            if (not needle or needle in r[0].lower())
            and (not group or _group_of(r[0]) == group)
        ]
        self._table.setRowCount(len(shown))
        for i, (name, val, default, overridden) in enumerate(shown):
            n = QTableWidgetItem(name)
            if overridden:
                n.setData(Qt.ItemDataRole.ToolTipRole, "بازنویسی‌شده در ‎~/.taskrc")
                f = n.font()
                f.setBold(True)
                n.setFont(f)
            self._table.setItem(i, 0, n)
            self._table.setItem(i, 1, QTableWidgetItem(val))
            self._table.setItem(i, 2, QTableWidgetItem(default or "—"))

    def _edit_current(self, *_a: object) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._table.item(row, 0).text()
        value = self._table.item(row, 1).text()
        default = self._table.item(row, 2).text()
        dlg = _EditDialog(name, value, default, self)
        if not dlg.exec():
            return
        action, new_value = dlg.result_action()
        if action == "reset":
            self._write(name, "", reset=True)
        elif action == "save" and new_value != value:
            self._write(name, new_value)

    def _write(self, name: str, value: str, *, reset: bool = False) -> None:
        if reset and not confirm(
            self,
            title="بازگردانی به پیش‌فرض",
            body=f"متغیر «{name}» از ‎~/.taskrc حذف و به مقدار پیش‌فرض بازگردانده می‌شود.",
        ):
            return
        submit(
            lambda: taskwarrior.config_set(name, value),
            lambda _r: (taskwarrior.refresh_lookups(), self.changed.emit(), self.reload()),
            lambda _e: None,
        )


class _EditDialog(QDialog):
    def __init__(self, name: str, value: str, default: str, parent=None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle("ویرایش متغیر پیکربندی")
        self.setMinimumWidth(440)
        self._action = "cancel"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(8)
        lay.addWidget(QLabel(f"<b>{name}</b>"))
        if default:
            d = QLabel(f"پیش‌فرض: {default}")
            d.setObjectName("Muted")
            lay.addWidget(d)
        self._edit = QLineEdit(value)
        lay.addWidget(self._edit)

        btns = QDialogButtonBox()
        btns.addButton("انصراف", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        if default:
            reset = btns.addButton(
                "بازگردانی به پیش‌فرض", QDialogButtonBox.ButtonRole.ResetRole
            )
            reset.clicked.connect(self._do_reset)
        save = btns.addButton("ذخیره", QDialogButtonBox.ButtonRole.AcceptRole)
        save.setObjectName("Primary")
        save.clicked.connect(self._do_save)
        lay.addWidget(btns)

    def _do_save(self) -> None:
        self._action = "save"
        self.accept()

    def _do_reset(self) -> None:
        self._action = "reset"
        self.accept()

    def result_action(self) -> tuple[str, str]:
        return self._action, self._edit.text().strip()
