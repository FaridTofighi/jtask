"""Desktop notifications for tasks becoming due / overdue (via the tray icon)."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QSystemTrayIcon

from jtask import jalali, reports

from . import fmt
from .i18n import t
from .settings import Settings
from .workers import submit

_STATE_LABELS = {
    "overdue": t("notify.state.overdue"),
    "today": t("notify.state.today"),
    "soon": t("notify.state.soon"),
}


def _current_hour() -> int:
    return datetime.datetime.now().hour


def _due_dt(task: dict) -> datetime.datetime | None:
    raw = task.get("due_gregorian") or ""
    m = jalali._TW_TS_RE.match(raw)
    if not m:
        return None
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    return datetime.datetime(y, mo, d, hh, mm, ss, tzinfo=datetime.timezone.utc)


def _classify(task: dict, soon_days: int) -> str | None:
    if task.get("status") != "pending":
        return None
    due = _due_dt(task)
    if not due:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    if due < now:
        return "overdue"
    local_today = now.astimezone(jalali.LOCAL_TZ).date()
    if due.astimezone(jalali.LOCAL_TZ).date() == local_today:
        return "today"
    if due - now <= datetime.timedelta(days=soon_days):
        return "soon"
    return None


class NotificationManager(QObject):
    taskActivated = pyqtSignal()  # user clicked a notification / tray

    def __init__(self, settings: Settings, tray: QSystemTrayIcon, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._tray = tray
        self._seen: dict[str, str] = {}  # uuid -> last state notified
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll)
        self._stopped = False
        tray.messageClicked.connect(self.taskActivated)

    # --- lifecycle --------------------------------------------

    def start(self) -> None:
        interval = max(1, self._settings.notify_interval_min) * 60_000
        self._stopped = False
        self._timer.start(interval)
        QTimer.singleShot(4000, self.poll)  # a first check shortly after launch

    def stop(self) -> None:
        # Also blocks the pending ``QTimer.singleShot`` first-check and the
        # ``_evaluate`` callback, so nothing schedules a worker after teardown
        # has drained the pool (which would emit onto a freed signal → Aborted).
        self._stopped = True
        self._timer.stop()

    def reconfigure(self) -> None:
        self.stop()
        if self._settings.notifications_enabled:
            self.start()

    # --- polling ---------------------------------------------

    def poll(self) -> None:
        if (
            self._stopped
            or not self._settings.notifications_enabled
            or self._in_quiet_hours()
        ):
            return
        submit(lambda: reports.report_next(["+PENDING"]), self._evaluate)

    def _in_quiet_hours(self) -> bool:
        start, end = self._settings.quiet_hours
        if start == end:
            return False
        now_h = _current_hour()
        if start < end:
            return start <= now_h < end
        return now_h >= start or now_h < end  # wraps past midnight

    def _evaluate(self, tasks: list[dict]) -> None:
        enabled = set(self._settings.notify_states)
        soon = self._settings.due_soon_days
        fresh: list[tuple[str, dict]] = []
        current = set()
        for task in tasks:
            uuid = task.get("uuid")
            state = _classify(task, soon)
            if not uuid or state is None:
                continue
            current.add(uuid)
            if state in enabled and self._seen.get(uuid) != state:
                self._seen[uuid] = state
                fresh.append((state, task))
        # forget tasks that are no longer due, so they re-notify if they recur
        self._seen = {u: s for u, s in self._seen.items() if u in current}

        if not fresh:
            return
        if len(fresh) == 1:
            state, task = fresh[0]
            self._tray.showMessage(
                _STATE_LABELS[state],
                task.get("description", ""),
                QSystemTrayIcon.MessageIcon.Warning
                if state == "overdue" else QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
        else:
            titles = t("list.sep").join(x.get("description", "") for _, x in fresh[:3])
            more = t("notify.more", n=fmt.num(len(fresh) - 3)) if len(fresh) > 3 else ""
            self._tray.showMessage(
                t("notify.title", n=fmt.num(len(fresh))),
                titles + more,
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
