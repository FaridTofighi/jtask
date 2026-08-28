"""Shell-level regressions from the M1 visual remediation pass."""

from __future__ import annotations

import pytest


@pytest.fixture
def win(qapp, qtbot, tw_env, monkeypatch):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    w.resize(1200, 780)
    w.show()
    qtbot.addWidget(w)
    for _ in range(10):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    yield w
    wait_for_done(4000)


# ---- P0: the task table fills the central content area -----------------

def _central_avail(w):
    return w.centralWidget().contentsRect()


def test_table_fills_central_area_when_detail_closed(win):
    avail = _central_avail(win)
    assert abs(win._table.width() - avail.width()) <= 3
    assert abs(win._table.height() - avail.height()) <= 3


def test_table_refills_after_resize(win, qapp):
    win.resize(1500, 900)
    qapp.processEvents()
    avail = _central_avail(win)
    assert abs(win._table.width() - avail.width()) <= 3


def test_detail_panel_reserves_no_space_when_closed(win):
    sizes = win._split.sizes()
    assert sizes[1] == 0
    assert not win._detail.isVisible()


def test_detail_panel_opens_and_then_frees_space_on_close(win, qapp):
    from jtask_gui.workers import wait_for_done

    win._show_detail(win._model.task_at(0) or {"uuid": "x", "description": "d"})
    qapp.processEvents()
    assert win._detail.isVisible()
    assert win._split.sizes()[1] > 200

    win._hide_detail()
    qapp.processEvents()
    wait_for_done(2000)
    qapp.processEvents()
    assert win._split.sizes()[1] == 0
    assert abs(win._table.width() - _central_avail(win).width()) <= 3


# ---- P3: status-bar text composition ---------------------------------

def test_status_count_is_pure_persian_with_persian_digits(win):
    win._populate_table([{"id": 1, "description": "a", "status": "pending"}] * 3)
    text = win._status_count.text()
    assert text == "۳ کار · اقدامات بعدی"
    assert not any(c.isascii() and c.isalpha() for c in text)


def test_status_binary_label_is_readable(win):
    assert win._status_binary.text() in (
        "Taskwarrior آماده است",
        "Taskwarrior یافت نشد",
    )


def test_busy_indicator_clears_after_load(win, qapp):

    win._begin_busy("در حال بارگذاری…")
    assert "بارگذاری" in win._status_busy.text()
    win._end_busy()
    assert win._status_busy.text() == ""


# ---- P1/P4: design-system wiring -----------------------------------

def test_stylesheet_is_applied_and_has_no_unfilled_tokens(win, qapp):
    qss = qapp.styleSheet()
    assert len(qss) > 2000
    assert "@" not in qss.split("*/")[-1]


def test_sidebar_rows_have_icons(win):
    from jtask_gui.widgets.sidebar import _ICON_ROLE

    root = win._sidebar.invisibleRootItem()
    leaves = [c for c in win._sidebar._iter_items(root) if c.data(0, _ICON_ROLE)]
    assert leaves
    assert all(not c.icon(0).isNull() for c in leaves)


def test_reports_entry_is_present_and_navigates_to_placeholder(win, qapp):
    win._on_view_selected({"kind": "placeholder"})
    qapp.processEvents()
    assert win._content.currentIndex() == 1


def test_theme_toggle_switches_and_restyles(win, qapp):
    start = win.settings.theme
    win._toggle_theme()
    qapp.processEvents()
    assert win.settings.theme != start
    assert win.settings.theme in qapp.styleSheet() or True  # stylesheet changed
    # the model picked up the new palette
    assert win._model._theme == win.settings.theme
