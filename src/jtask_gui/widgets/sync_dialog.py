"""Sync Manager — run ``task sync`` with visible state and no concurrent runs (§ M7).

Detects whether Taskwarrior sync is configured; if not, explains and points at
the Configuration Manager rather than firing a command that would error.

The manual Sync button and the optional automatic interval both run through one
:class:`~jtask_gui.auto_sync.AutoSyncManager` — a single concurrency guard, no
duplicate sync path.
"""

from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from jtask import jalali, taskwarrior
from jtask.rtl import bidi_isolate

from .. import fmt
from .. import tokens as tok
from ..auto_sync import AutoSyncManager
from ..i18n import t
from ..settings import Settings
from ..workers import submit
from .fa_spinbox import FaSpinBox

_KIND_KEY = {"remote": "sync.kind.remote", "local": "sync.kind.local"}


class SyncManagerDialog(QDialog):
    synced = pyqtSignal()  # a sync finished successfully

    def __init__(
        self,
        settings,
        parent: QWidget | None = None,
        *,
        manager: AutoSyncManager | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        # a passed-in manager is the app-wide one (its timer drives auto-sync);
        # a standalone dialog gets a throwaway so the manual button still has
        # one shared execution path + guard.
        self._sync = manager or AutoSyncManager(settings, self)
        self._sync.syncSucceeded.connect(self._on_sync_ok)
        self._sync.syncFailed.connect(self._on_sync_failed)
        self.setObjectName("SyncDialog")
        self.setWindowTitle(t("sync.title"))
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_10)

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

        # --- auto-sync ---------------------------------------
        self._auto = QCheckBox(t("sync.auto.enabled"))
        self._auto.setChecked(settings.autosync_enabled)
        self._auto.toggled.connect(self._on_auto_toggled)
        root.addWidget(self._auto)

        row = QHBoxLayout()
        row.setSpacing(tok.SP_8)
        self._interval_label = QLabel(t("sync.auto.interval"))
        row.addWidget(self._interval_label)
        self._interval = FaSpinBox()
        self._interval.setRange(Settings.AUTOSYNC_FLOOR_SEC, 86_400)
        self._interval.setValue(settings.autosync_interval_sec)
        self._interval.setSuffix(t("sync.auto.seconds"))
        self._interval.valueChanged.connect(self._on_interval_changed)
        row.addWidget(self._interval)
        row.addStretch(1)
        iwrap = QWidget()
        iwrap.setLayout(row)
        root.addWidget(iwrap)

        self._auto_hint = QLabel(
            t("sync.auto.hint", n=fmt.num(Settings.AUTOSYNC_FLOOR_SEC))
        )
        self._auto_hint.setObjectName("Muted")
        self._auto_hint.setWordWrap(True)
        root.addWidget(self._auto_hint)
        self._sync_auto_enabled(self._auto.isChecked())

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

        self._configured = False
        self._refresh_last()
        self._reflect_running()
        submit(taskwarrior.sync_status, self._show_status, lambda _e: self._show_status(
            {"configured": False, "kind": None, "target": ""}
        ))

    # --- auto-sync controls --------------------------------

    def _sync_auto_enabled(self, on: bool) -> None:
        self._interval_label.setEnabled(on)
        self._interval.setEnabled(on)

    def _on_auto_toggled(self, on: bool) -> None:
        self._settings.autosync_enabled = on
        self._sync_auto_enabled(on)
        self._sync.reconfigure()

    def _on_interval_changed(self, value: int) -> None:
        self._settings.autosync_interval_sec = value
        if self._settings.autosync_enabled:
            self._sync.reconfigure()  # restart on the new interval at once

    # --- status -------------------------------------------

    def _refresh_last(self) -> None:
        raw = self._settings.last_sync
        if raw:
            try:
                d = dt.datetime.fromisoformat(raw)
                shown = jalali.from_local(d.strftime("%Y-%m-%d %H:%M:%S"), "long")
                self._last.setText(t("sync.last_success", shown=bidi_isolate(shown)))
                return
            except ValueError:
                pass
        self._last.setText(t("sync.never"))

    def _show_status(self, st: dict) -> None:
        self._configured = bool(st.get("configured"))
        if not self._configured:
            self._status.setText(t("sync.not_configured"))
            self._detail.setText(t("sync.not_configured.detail"))
            self._go.setEnabled(False)
            return
        self._status.setText(t("sync.ready"))
        # the target is a URL or a filesystem path — an LTR-structured token
        # that must stay atomic inside the RTL line
        self._detail.setText(
            f"{t(_KIND_KEY.get(st['kind'], st['kind']))}: "
            f"{bidi_isolate(st['target'])}"
        )
        self._reflect_running()

    def _reflect_running(self) -> None:
        busy = self._sync.is_running()
        self._go.setEnabled(self._configured and not busy)
        self._go.setText(t("sync.running") if busy else t("sync.run"))

    # --- run ---------------------------------------------

    def _run(self) -> None:
        if not self._sync.run("manual"):
            return  # already in flight (manual or automatic)
        self._out.setText("")
        self._reflect_running()

    def _on_sync_ok(self, _source: str, _iso: str) -> None:
        self._out.setText(t("sync.done"))
        self._refresh_last()
        self._reflect_running()
        self.synced.emit()

    def _on_sync_failed(self, _source: str, err: object) -> None:
        self._out.setText(t("sync.failed", err=err))
        self._reflect_running()
