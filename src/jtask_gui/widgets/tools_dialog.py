"""Diagnostics · Command reference · Calculator — read-only Taskwarrior tools (§ M9)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali, taskwarrior

from ..i18n import t
from ..workers import submit


class _DiagnosticsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._text = QPlainTextEdit()
        self._text.setObjectName("DiagText")
        self._text.setReadOnly(True)
        self._text.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self._text, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        copy = QPushButton(t("btn.copy"))
        copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self._text.toPlainText())
        )
        row.addWidget(copy)
        save = QPushButton(t("tools.save_to_file"))
        save.clicked.connect(self._save)
        row.addWidget(save)
        lay.addLayout(row)

    def load(self) -> None:
        self._text.setPlainText(t("tools.fetching"))
        submit(
            taskwarrior.diagnostics,
            self._text.setPlainText,
            lambda e: self._text.setPlainText(str(e)),
        )

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("tools.save_diag"), "task-diagnostics.txt", t("tools.txt_filter")
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._text.toPlainText() + "\n")


class _HelpTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("tools.help.search"))
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search)
        self._table = QTableWidget(0, 2)
        self._table.setObjectName("HelpTable")
        self._table.setHorizontalHeaderLabels(
            [t("tools.help.col.command"), t("tools.help.col.description")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        lay.addWidget(self._table, 1)
        self._rows: list[tuple[str, str]] = []

    def load(self) -> None:
        submit(taskwarrior.command_reference, self._set, lambda _e: None)

    def _set(self, rows: list[tuple[str, str]]) -> None:
        self._rows = rows
        self._filter()

    def _filter(self, *_a: object) -> None:
        needle = self._search.text().strip().lower()
        shown = [r for r in self._rows if not needle or needle in (r[0] + r[1]).lower()]
        self._table.setRowCount(len(shown))
        for i, (inv, desc) in enumerate(shown):
            self._table.setItem(i, 0, QTableWidgetItem(inv))
            self._table.setItem(i, 1, QTableWidgetItem(desc))
        self._table.resizeColumnToContents(0)


class _CalcTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(QLabel(t("tools.calc.hint")))
        row = QHBoxLayout()
        self._in = QLineEdit()
        self._in.setPlaceholderText(t("tools.calc.placeholder"))
        self._in.returnPressed.connect(self._go)
        row.addWidget(self._in, 1)
        btn = QPushButton(t("tools.calc.run"))
        btn.setObjectName("Primary")
        btn.clicked.connect(self._go)
        row.addWidget(btn)
        lay.addLayout(row)
        self._out = QLabel("")
        self._out.setObjectName("CalcResult")
        self._out.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._out.setWordWrap(True)
        lay.addWidget(self._out)
        lay.addStretch(1)

    def _go(self) -> None:
        expr = self._in.text().strip()
        if not expr:
            return
        self._out.setText("…")
        submit(lambda: taskwarrior.calc(expr), self._show, self._err)

    def _show(self, result: str) -> None:
        extra = ""
        if len(result) >= 19 and result[4] == "-" and "T" in result:
            try:
                extra = "   ·   " + jalali.from_local(
                    result.replace("T", " ")[:19], "long"
                )
            except Exception:  # noqa: BLE001
                extra = ""
        self._out.setText(f"= {result}{extra}")

    def _err(self, err: object) -> None:
        self._out.setText(t("tools.calc.error", err=err))


class ToolsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolsDialog")
        self.setWindowTitle(t("tools.title"))
        self.resize(720, 540)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        tabs = QTabWidget()
        self.diagnostics = _DiagnosticsTab()
        self.help = _HelpTab()
        self.calc = _CalcTab()
        tabs.addTab(self.diagnostics, t("tools.tab.diagnostics"))
        tabs.addTab(self.help, t("tools.tab.help"))
        tabs.addTab(self.calc, t("tools.tab.calc"))
        lay.addWidget(tabs, 1)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.close"), QDialogButtonBox.ButtonRole.AcceptRole).clicked.connect(
            self.accept
        )
        lay.addWidget(btns)

        self.diagnostics.load()
        self.help.load()
