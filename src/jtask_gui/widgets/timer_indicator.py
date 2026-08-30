"""Status-bar active-timer indicator — live elapsed time for started tasks.

Taskwarrior keeps the current ``start`` timestamp on each active task; this
widget shows the running task (or count, when several are active) and ticks the
elapsed time every second.  Click to stop.
"""

from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QWidget

from .. import fmt
from ..i18n import t


def _elapsed(since: dt.datetime, now: dt.datetime) -> str:
    total = max(0, int((now - since).total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return fmt.digits(f"{h}:{m:02d}:{s:02d}")


class TimerIndicator(QLabel):
    stopRequested = pyqtSignal(str)  # uuid

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimerIndicator")
        self._active: list[dict] = []
        self._start: dt.datetime | None = None
        self._uuid: str | None = None
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._refresh_text)
        self.setVisible(False)
        self.setToolTip(t("timer.stop_tip"))

    def set_active_tasks(self, tasks: list[dict]) -> None:
        self._active = [x for x in tasks if x.get("start")]
        if not self._active:
            self._uuid = None
            self._start = None
            self._tick.stop()
            self.setVisible(False)
            return
        primary = self._active[0]
        self._uuid = primary.get("uuid")
        raw = primary.get("start_gregorian") or primary.get("start") or ""
        self._start = _parse(raw)
        self.setVisible(True)
        self._refresh_text()
        self._tick.start()

    def _refresh_text(self) -> None:
        if not self._active:
            return
        now = dt.datetime.now(dt.timezone.utc)
        if len(self._active) == 1:
            desc = self._active[0].get("description", "")
            el = _elapsed(self._start, now) if self._start else "—"
            self.setText(f"▶ {desc}  {el}")
        else:
            n = fmt.digits(str(len(self._active)))
            el = _elapsed(self._start, now) if self._start else "—"
            self.setText(t("timer.n_active", n=n, el=el))

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if self._uuid:
            self.stopRequested.emit(self._uuid)
        super().mousePressEvent(ev)


def _parse(raw: str) -> dt.datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt_ in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return dt.datetime.strptime(raw, fmt_).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    try:  # local "YYYY-MM-DD HH:MM:SS"
        return dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").astimezone(dt.timezone.utc)
    except ValueError:
        return None
