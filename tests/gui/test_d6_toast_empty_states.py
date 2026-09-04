"""d6 — non-blocking toast + consistent empty states."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGETS = Path(__file__).parents[2] / "src" / "jtask_gui" / "widgets"


# --- toast ---------------------------------------------------------

def test_toast_shows_then_auto_dismisses(qapp, qtbot):
    from PyQt6.QtWidgets import QWidget

    from jtask_gui.widgets.toast import Toast

    host = QWidget()
    host.resize(600, 400)
    qtbot.addWidget(host)
    toast = Toast(host)

    toast.show_message("فیلتر ذخیره شد")
    assert not toast.isHidden()
    assert toast._text.text() == "فیلتر ذخیره شد"
    # it does not steal focus or block input
    assert toast.focusPolicy().name == "NoFocus"
    assert toast.testAttribute(
        __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute
        .WA_TransparentForMouseEvents
    )

    from jtask_gui.widgets import toast as toast_mod

    qtbot.wait(toast_mod._VISIBLE_MS + toast_mod._FADE_MS + 200)
    assert toast.isHidden()


def test_write_path_raises_a_toast(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    QSettings("jtask", "jtask-gui").clear()
    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    w._save_filter("کارهای مهم", "priority:H")
    qapp.processEvents()
    assert not w._toast.isHidden()
    assert "کارهای مهم" in w._toast._text.text()


def test_destructive_actions_still_use_a_blocking_confirm():
    """The toast must not have replaced any confirmation dialog.

    ``_delete``/``_purge`` live in ``mixins/task_lifecycle.py`` (MainWindow
    decomposition, 2026-09-05) — search every module MainWindow is composed
    from, not just main_window.py itself, so this gate survives future moves
    too."""
    root = Path(__file__).parents[2] / "src" / "jtask_gui"
    src = "\n".join(
        p.read_text()
        for p in [root / "main_window.py", *sorted((root / "mixins").glob("*.py"))]
    )
    for verb in ("_delete", "_purge"):
        m = re.search(rf"def {verb}\(.*?(?=\n    def )", src, re.S)
        assert m and "confirm(" in m.group(0), f"{verb} lost its confirm()"


# --- empty states -------------------------------------------------

def test_empty_states_use_the_designed_class():
    """Every 'no data' fallback label uses #EmptyState / #DepEmpty, not a bare
    #Muted label."""
    offenders = []
    empty_key = re.compile(r't\("(?:[\w.]*\.empty|chart\.no_data|[\w.]*no_tasks[\w.]*)"')
    for p in list(_WIDGETS.glob("*.py")) + list(_WIDGETS.glob("charts/*.py")):
        src = p.read_text()
        for m in empty_key.finditer(src):
            window = src[max(0, m.start() - 400): m.end() + 200]
            if "QLabel" in window and 'setObjectName("Muted")' in window and \
               "EmptyState" not in window and "DepEmpty" not in window:
                offenders.append(f"{p.name}: {m.group(0)}")
    assert not offenders, f"bare empty-state labels: {offenders}"


@pytest.mark.parametrize(
    "factory,attr",
    [
        ("summary", "_grid"),
        ("timesheet", "_empty"),
    ],
)
def test_view_empty_state_is_styled(qapp, qtbot, tw_env, factory, attr):
    if factory == "summary":
        from jtask_gui.widgets.charts.summary_view import SummaryView

        v = SummaryView()
        v.set_data([])
        qtbot.addWidget(v)
        from PyQt6.QtWidgets import QLabel

        lbls = v.findChildren(QLabel)
        assert any(x.objectName() == "EmptyState" for x in lbls)
    else:
        from jtask_gui.widgets.timesheet_view import TimesheetView

        v = TimesheetView()
        qtbot.addWidget(v)
        assert v._empty.objectName() == "EmptyState"
