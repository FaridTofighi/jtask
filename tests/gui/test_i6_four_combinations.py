"""i6 — every Language × Calendar combination renders a coherent window.

Language drives interface text + layout direction; Calendar drives how dates
are shown. The four combinations are independent and all must work. Taskwarrior
storage stays Gregorian/UTC throughout (asserted separately in the CLI suite).
"""

from __future__ import annotations

import re

import pytest
from PyQt6.QtCore import Qt

_PERSIAN = re.compile(r"[؀-ۿ]")
_COMBOS = [
    ("fa", "jalali"),
    ("fa", "gregorian"),
    ("en", "jalali"),
    ("en", "gregorian"),
]


@pytest.fixture
def combo(qapp, request):
    """Switch the whole process to (language, calendar) for the test body."""
    from PyQt6.QtCore import QSettings

    from jtask.rtl import digit_mode, set_digit_mode
    from jtask_gui import calendar_system, i18n
    from jtask_gui.settings import Settings

    lang, cal = request.param
    prev = (i18n.lang(), qapp.layoutDirection(), calendar_system._active, digit_mode())

    QSettings("jtask", "jtask-gui").clear()
    s = Settings()
    s.language = lang
    s.calendar = cal
    s.sync()

    i18n.set_language(lang)
    qapp.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if lang == "fa" else Qt.LayoutDirection.LeftToRight
    )
    calendar_system.set_calendar(cal)
    set_digit_mode(s.persian_digits)

    yield lang, cal

    i18n.set_language(prev[0])
    qapp.setLayoutDirection(prev[1])
    calendar_system._active = prev[2]
    set_digit_mode(prev[3])
    QSettings("jtask", "jtask-gui").clear()


def _window(qapp, qtbot):
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    return w


def _all_text(w) -> list[str]:
    from PyQt6.QtWidgets import QLabel

    return [lbl.text() for lbl in w.findChildren(QLabel) if lbl.text().strip()]


@pytest.mark.parametrize("combo", _COMBOS, indirect=True)
def test_layout_direction_follows_language_only(combo, qapp, qtbot, tw_env):
    lang, _cal = combo
    w = _window(qapp, qtbot)
    want = (
        Qt.DockWidgetArea.RightDockWidgetArea
        if lang == "fa"
        else Qt.DockWidgetArea.LeftDockWidgetArea
    )
    assert w.dockWidgetArea(w._sidebar_dock) == want


@pytest.mark.parametrize("combo", _COMBOS, indirect=True)
def test_interface_language_matches(combo, qapp, qtbot, tw_env):
    lang, _cal = combo
    w = _window(qapp, qtbot)
    texts = _all_text(w)
    persian_labels = [t for t in texts if _PERSIAN.search(t)]
    if lang == "fa":
        assert persian_labels, "fa UI should have Persian chrome"
    else:
        # project / tag names in the sample data can be anything; the window
        # chrome (sidebar sections, status bar, dock titles) must be English.
        assert w._sidebar.topLevelItem(0).text(0) == "Quick views"
        assert not any(
            _PERSIAN.search(w._sidebar.topLevelItem(i).text(0))
            for i in range(w._sidebar.topLevelItemCount())
        )


@pytest.mark.parametrize("combo", _COMBOS, indirect=True)
def test_due_column_renders_in_the_active_calendar(combo, qapp, qtbot, tw_env):
    from jtask import taskwarrior
    from jtask.jalali import normalize_digits

    _lang, cal = combo
    taskwarrior.run(["add", "Alpha", "due:2025-06-15"])
    taskwarrior.run(["add", "Beta", "due:2025-11-03"])
    taskwarrior.refresh_lookups()
    w = _window(qapp, qtbot)
    m = w._table.model()
    due_col = next(
        c for c in range(m.columnCount())
        if m.headerData(c, Qt.Orientation.Horizontal) in ("Due", "سررسید")
    )
    seen = []
    for r in range(m.rowCount()):
        raw = m.data(m.index(r, due_col))
        if raw:
            seen.append(normalize_digits(re.sub(r"[⁦-⁩]", "", raw)))
    assert seen, "sample data has due dates"
    for iso in seen:
        y = int(iso[:4])
        if cal == "gregorian":
            assert 2000 <= y <= 2100, iso
        else:
            assert 1380 <= y <= 1500, iso


@pytest.mark.parametrize("combo", _COMBOS, indirect=True)
def test_calendar_popup_month_names(combo, qapp, qtbot, tw_env):
    from jtask_gui.calendar_system import active
    from jtask_gui.widgets.jalali_calendar import JalaliMonthGrid

    lang, cal = combo
    grid = JalaliMonthGrid(calendar=active())
    qtbot.addWidget(grid)
    names = active().month_names()
    if cal == "gregorian":
        assert names[0] == "January"
    elif lang == "en":
        assert names[0] == "Farvardin"      # transliteration, not translation
    else:
        assert names[0] == "فروردین"
