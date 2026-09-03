"""gtd-W2: the Weekly Review Wizard — step sequence, the live view per step,
resumability, and that it never blocks the app."""

from __future__ import annotations

import datetime

import pytest
from PyQt6.QtCore import QSettings


@pytest.fixture(autouse=True)
def _en():
    from jtask_gui import i18n

    prev = i18n.lang()
    i18n.set_language("en")
    QSettings("jtask", "jtask-gui").clear()
    yield
    QSettings("jtask", "jtask-gui").clear()
    i18n.set_language(prev)


# --- the widget in isolation -----------------------------------

def test_step_keys_are_the_shared_steps_plus_a_reports_glance():
    from jtask import gtd
    from jtask_gui.widgets.review_wizard import STEP_KEYS

    assert STEP_KEYS == [s.key for s in gtd.REVIEW_STEPS] + ["reports"]


def test_wizard_navigation_and_signals(qtbot):
    from jtask_gui.widgets.review_wizard import STEP_KEYS, ReviewWizard

    w = ReviewWizard()
    qtbot.addWidget(w)
    entered: list[int] = []
    w.stepEntered.connect(entered.append)

    w.start(0)
    assert w.current() == 0 and not w._back.isEnabled()
    assert w._heading.text() and w._hint.text()

    w.go(1)
    assert w.current() == 1 and w._back.isEnabled()
    assert entered == [0, 1]

    from jtask_gui.i18n import t

    w.jump(len(STEP_KEYS) - 1)
    assert w._next.text() == t("review.finish")

    exited = []
    w.exited.connect(lambda: exited.append(True))
    w.go(1)                                   # past the end = finish
    assert exited == [True]


def test_stuck_step_list_offers_add_next_action(qtbot):
    from jtask_gui.widgets.review_wizard import ReviewWizard

    w = ReviewWizard()
    qtbot.addWidget(w)
    w.show_stuck(["Alpha", "Beta"])
    got: list[str] = []
    w.addNextActionRequested.connect(got.append)
    w._stuck.itemActivated.emit(w._stuck.item(0))
    assert got == ["Alpha"]

    w.show_stuck([])
    assert w._stuck.count() == 1               # the "no stuck projects ✔" row
    assert w._stuck.item(0).data(0x0100) is None  # UserRole empty → not clickable


# --- wired into MainWindow ------------------------------------

@pytest.fixture
def win(qapp, qtbot, tw_env):
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["inbox item"])
    tw.add(["waiting item", "project:Delegated", "+waiting"])
    tw.refresh_lookups()

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    return w


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()


def test_open_review_drives_the_main_view_per_step(win, qapp):
    from jtask.gtd import review_step

    win._open_review()
    assert win._review_active
    assert win._review_dock.isVisibleTo(win)

    # step 0 = inbox → the main view uses the shared filter
    assert win._review.current() == 0
    assert win._view_spec["filter"] == review_step("inbox").filter()

    win._review.go(1)                                     # overdue
    assert win._view_spec["filter"] == review_step("overdue").filter()

    # the task table is never disabled while the wizard is open
    assert win._table.isEnabled()


def test_stuck_step_populates_the_dock_list(win, qapp):
    from jtask_gui.widgets.review_wizard import STEP_KEYS

    win._open_review()
    win._review.jump(STEP_KEYS.index("stuck_projects"))
    _drain(qapp)
    rows = [win._review._stuck.item(i).text() for i in range(win._review._stuck.count())]
    assert any("Delegated" in r for r in rows)


def test_exit_restores_the_previous_view_and_clears_resume_state(win, qapp):
    before = dict(win._view_spec)
    win._open_review()
    win._review.go(2)
    assert win.settings.review_step == 2

    win._exit_review()
    assert not win._review_active
    assert win.settings.review_step == 0 and win.settings.review_started == ""
    assert win._view_spec.get("title") == before.get("title")


def test_review_is_resumable_within_48h(win, qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    win.settings.review_step = 3
    win.settings.review_started = datetime.datetime.now().isoformat(timespec="seconds")

    # user clicks "Resume"
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[0])
    win._open_review()
    assert win._review.current() == 3


def test_a_stale_review_starts_over(win, qapp):
    win.settings.review_step = 5
    win.settings.review_started = (
        datetime.datetime.now() - datetime.timedelta(days=3)
    ).isoformat(timespec="seconds")
    win._open_review()
    assert win._review.current() == 0
