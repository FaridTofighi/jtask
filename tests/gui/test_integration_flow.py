"""Full flow: quick-add -> list -> Jalali date -> mark done -> completed view."""

import datetime

import jdatetime
import pytest

from jtask import jalali


@pytest.fixture
def window(qapp, qtbot, tw_env):
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    win = MainWindow(Settings())
    qtbot.addWidget(win)
    _settle(qapp, qtbot)
    yield win
    wait_for_done(5000)
    qapp.processEvents()


def _settle(app, qtbot, rounds=8):
    from jtask_gui.workers import wait_for_done

    for _ in range(rounds):
        app.processEvents()
        wait_for_done(5000)
        app.processEvents()
        qtbot.wait(20)


def test_add_appears_with_jalali_date_then_completes(window, qapp, qtbot):
    app = qapp
    tomorrow = jdatetime.date.today() + datetime.timedelta(days=1)

    window._view_spec = {"kind": "report", "title": "بعدی", "fn": "report_next"}
    window._quick_add._edit.setText("خرید شیر فردا +خرید")
    window._quick_add._commit()
    _settle(app, qtbot)

    model = window._model
    descs = [model.task_at(r)["description"] for r in range(model.rowCount())]
    assert "خرید شیر" in descs

    row = descs.index("خرید شیر")
    task = model.task_at(row)
    assert task["due"] == jalali.to_persian_digits(tomorrow.strftime("%Y-%m-%d"))

    # mark done through the threaded worker path
    window._bulk([task["uuid"]], "done", "done")
    _settle(app, qtbot)

    descs_now = [model.task_at(r)["description"] for r in range(model.rowCount())]
    assert "خرید شیر" not in descs_now

    window._on_view_selected({"kind": "report", "title": "تکمیل‌شده", "fn": "report_completed"})
    _settle(app, qtbot)
    done_descs = [window._model.task_at(r)["description"] for r in range(window._model.rowCount())]
    assert "خرید شیر" in done_descs


def test_undo_action_is_present_and_wired(window):
    assert window._undo_action.text() == "واگرد آخرین عملیات"
    assert not window._undo_action.shortcut().isEmpty()


def test_reports_placeholder_shows_on_sidebar_selection(window, qapp, qtbot):
    window._on_view_selected({"kind": "placeholder"})
    _settle(qapp, qtbot, rounds=2)
    assert window._content.currentIndex() == 1
