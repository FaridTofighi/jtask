"""Diagnostics · Command reference · Calculator — read-only Taskwarrior tools.

Three self-contained panels; they live in the Settings dialog's "Taskwarrior"
section (they used to be the three tabs of a standalone ``ToolsDialog``).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from .. import tokens as tok
from ..calendar_system import active
from ..i18n import t
from ..workers import submit


class DiagnosticsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_6)
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


class HelpTab(QWidget):
    sendToConsole = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_6)
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

        row = QHBoxLayout()
        row.addStretch(1)
        self._to_console = QPushButton(t("tools.help.to_console"))
        self._to_console.setEnabled(False)
        self._to_console.clicked.connect(self._emit_to_console)
        row.addWidget(self._to_console)
        lay.addLayout(row)

        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.itemDoubleClicked.connect(lambda _i: self._emit_to_console())
        self._rows: list[tuple[str, str]] = []

    def load(self) -> None:
        submit(taskwarrior.command_reference, self._set, lambda _e: None)

    def _on_selection(self) -> None:
        self._to_console.setEnabled(bool(self._table.selectedItems()))

    def _emit_to_console(self) -> None:
        items = self._table.selectedItems()
        if not items:
            return
        invocation = self._table.item(items[0].row(), 0)
        if invocation and invocation.text().strip():
            self.sendToConsole.emit(invocation.text().strip())

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


class CalcTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_8)
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
                extra = "   ·   " + active().format_local(
                    result.replace("T", " ")[:19], "long"
                )
            except Exception:  # noqa: BLE001
                extra = ""
        self._out.setText(f"= {result}{extra}")

    def _err(self, err: object) -> None:
        self._out.setText(t("tools.calc.error", err=err))
