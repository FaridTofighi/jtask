"""Sync Manager — run ``task sync`` with visible state and no concurrent runs (§ M7).

Detects whether Taskwarrior sync is configured; if not, explains and points at
the (M8) Configuration Manager rather than firing a command that would error.
"""

from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali, taskwarrior

from ..i18n import t
from ..workers import submit

_KIND_KEY = {"remote": "sync.kind.remote", "local": "sync.kind.local"}


class SyncManagerDialog(QDialog):
    synced = pyqtSignal()  # a sync finished successfully

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setObjectName("SyncDialog")
        self.setWindowTitle(t("sync.title"))
        self.setMinimumWidth(440)
        self._running = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        self._status = QLabel(t("sync.checking"))
        self._status.setObjectName("H2")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        self._detail = QLabel("")
        self._detail.setObjectName("Muted")
        self._detail.setWordWrap(True)
        root.addWidget(self._detail)

        self._last = QLabel("")
        self._last.setObjectName("Muted")
        root.addWidget(self._last)

        self._out = QLabel("")
        self._out.setObjectName("Muted")
        self._out.setWordWrap(True)
        root.addWidget(self._out)

        self._btns = QDialogButtonBox()
        self._close = self._btns.addButton(
            t("btn.close"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._close.clicked.connect(self.reject)
        self._go = self._btns.addButton(
            t("sync.run"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self._go.setObjectName("Primary")
        self._go.clicked.connect(self._run)
        self._go.setEnabled(False)
        root.addWidget(self._btns)

        self._refresh_last()
        submit(taskwarrior.sync_status, self._show_status, lambda _e: self._show_status(
            {"configured": False, "kind": None, "target": ""}
        ))

    def _refresh_last(self) -> None:
        raw = self._settings.last_sync
        if raw:
            try:
                d = dt.datetime.fromisoformat(raw)
                shown = jalali.from_local(d.strftime("%Y-%m-%d %H:%M:%S"), "long")
                self._last.setText(t("sync.last_success", shown=shown))
                return
            except ValueError:
                pass
        self._last.setText(t("sync.never"))

    def _show_status(self, st: dict) -> None:
        if not st.get("configured"):
            self._status.setText(t("sync.not_configured"))
            self._detail.setText(t("sync.not_configured.detail"))
            self._go.setEnabled(False)
            return
        self._status.setText(t("sync.ready"))
        self._detail.setText(
            f"{t(_KIND_KEY.get(st['kind'], st['kind']))}: {st['target']}"
        )
        self._go.setEnabled(True)

    def _run(self) -> None:
        if self._running:
            return
        self._running = True
        self._go.setEnabled(False)
        self._go.setText(t("sync.running"))
        self._out.setText("")

        def done(text: str) -> None:
            self._running = False
            self._go.setText(t("sync.run"))
            self._go.setEnabled(True)
            self._out.setText(text or t("sync.done"))
            self._settings.last_sync = dt.datetime.now().isoformat(timespec="seconds")
            self._refresh_last()
            self.synced.emit()

        def failed(err: object) -> None:
            self._running = False
            self._go.setText(t("sync.run"))
            self._go.setEnabled(True)
            self._out.setText(t("sync.failed", err=err))

        submit(taskwarrior.synchronize, done, failed)
