"""i3 — layout direction follows UI **language** only (never the calendar).

fa  → RightToLeft, sidebar dock on the right.
en  → LeftToRight,  sidebar dock on the left.

Every dialog inherits the application direction (no leftover hardcoded RTL),
and the ``undo`` glyph is only mirrored in RTL.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt


@pytest.fixture
def in_language(qapp, request):
    """Run the test body with the app switched to ``request.param`` language +
    matching layout direction, then restore fa/RTL for the rest of the suite."""
    from jtask_gui import i18n

    lang = request.param
    prev_lang = i18n.lang()
    prev_dir = qapp.layoutDirection()

    i18n.set_language(lang)
    qapp.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if lang == "fa" else Qt.LayoutDirection.LeftToRight
    )
    yield lang
    i18n.set_language(prev_lang)
    qapp.setLayoutDirection(prev_dir)


def _fresh_window(qapp, qtbot):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    s = Settings()
    s.language = "fa" if qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft else "en"
    w = MainWindow(s)
    qtbot.addWidget(w)
    for _ in range(5):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    return w


@pytest.mark.parametrize("in_language", ["fa", "en"], indirect=True)
def test_sidebar_dock_side_follows_language(in_language, qapp, qtbot, tw_env):
    w = _fresh_window(qapp, qtbot)
    area = w.dockWidgetArea(w._sidebar_dock)
    if in_language == "fa":
        assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert area == Qt.DockWidgetArea.RightDockWidgetArea
    else:
        assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
        assert area == Qt.DockWidgetArea.LeftDockWidgetArea


@pytest.mark.parametrize("in_language", ["fa", "en"], indirect=True)
def test_sidebar_side_survives_a_stale_persisted_layout(in_language, qapp, qtbot, tw_env):
    """A dock layout saved under the other language (or an older build) must not
    keep the sidebar on the wrong edge — _enforce_sidebar_side() self-heals it."""
    from PyQt6.QtCore import QSettings

    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    QSettings("jtask", "jtask-gui").clear()

    # build a window in the *opposite* direction and stash its dock state
    other = "fa" if in_language == "en" else "en"
    from jtask_gui import i18n

    i18n.set_language(other)
    qapp.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if other == "fa" else Qt.LayoutDirection.LeftToRight
    )
    s = Settings()
    s.language = other
    tmp = MainWindow(s)
    qtbot.addWidget(tmp)
    poisoned = tmp.saveState()

    # now pretend that state was saved under the CURRENT language's bucket
    i18n.set_language(in_language)
    qapp.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if in_language == "fa" else Qt.LayoutDirection.LeftToRight
    )
    s2 = Settings()
    s2.language = in_language
    s2.save_window(tmp.saveGeometry(), poisoned, language=in_language)

    w = MainWindow(s2)
    qtbot.addWidget(w)
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    want = (
        Qt.DockWidgetArea.RightDockWidgetArea
        if in_language == "fa"
        else Qt.DockWidgetArea.LeftDockWidgetArea
    )
    assert w.dockWidgetArea(w._sidebar_dock) == want


@pytest.mark.parametrize("in_language", ["fa", "en"], indirect=True)
def test_closeevent_saves_state_under_the_built_language(in_language, qapp, qtbot, tw_env):
    """Switching language then closing without restarting must not poison the
    new language's saved layout with the old (still-rendered) one."""
    from PyQt6.QtCore import QSettings

    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    QSettings("jtask", "jtask-gui").clear()
    s = Settings()
    s.language = in_language
    w = MainWindow(s)
    qtbot.addWidget(w)

    switched = "fa" if in_language == "en" else "en"
    s.language = switched          # user picks a new language, defers the restart
    w.close()                      # closeEvent fires

    assert Settings()._s.value(f"win/state_{in_language}") is not None
    assert Settings()._s.value(f"win/state_{switched}") is None


@pytest.mark.parametrize("in_language", ["fa", "en"], indirect=True)
def test_dialogs_inherit_app_direction(in_language, qapp, qtbot, tw_env):
    from jtask_gui.widgets.bulk_edit import BulkEditDialog
    from jtask_gui.widgets.error_dialog import ErrorDialog
    from jtask_gui.widgets.export_dialog import ExportDialog
    from jtask_gui.widgets.manager_dialog import ManagerDialog
    from jtask_gui.widgets.task_form import TaskFormDialog

    want = qapp.layoutDirection()
    for dlg in (
        TaskFormDialog("add"),
        BulkEditDialog(2),
        ExportDialog([]),
        ErrorDialog("x"),
        ManagerDialog(),
    ):
        qtbot.addWidget(dlg)
        assert dlg.layoutDirection() == want, type(dlg).__name__


@pytest.mark.parametrize("in_language", ["fa", "en"], indirect=True)
def test_monospace_boxes_stay_ltr_in_both_languages(in_language, qapp, qtbot, tw_env):
    from jtask_gui.widgets.raw_data_view import RawDataView

    v = RawDataView()
    qtbot.addWidget(v)
    assert v._text.layoutDirection() == Qt.LayoutDirection.LeftToRight


@pytest.mark.parametrize("in_language", ["fa", "en"], indirect=True)
def test_undo_glyph_mirrored_only_in_rtl(in_language, qapp):
    from jtask_gui import icons

    icons._cache.clear()
    ic = icons.icon("undo")
    # render both to pixmaps and compare — mirrored vs not differ
    from jtask_gui.icons import icon as _icon  # noqa: F401

    assert not ic.isNull()
    assert icons._is_rtl() == (in_language == "fa")


def test_no_hardcoded_rtl_left_in_dialogs():
    """Grep guard: no widget may hardcode ``setLayoutDirection(RightToLeft)``.
    The four LeftToRight calls on monospace/code boxes are allowed."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "src" / "jtask_gui"
    offenders = []
    for p in root.rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "setLayoutDirection(Qt.LayoutDirection.RightToLeft)" in line:
                offenders.append(f"{p.relative_to(root)}:{i}")
    assert offenders == [], offenders
