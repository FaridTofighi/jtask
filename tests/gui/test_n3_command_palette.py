"""Mission n3 — the Ctrl/Cmd-K command palette."""

from __future__ import annotations

import pytest

from jtask_gui.widgets.command_palette import Command, CommandPalette, _score


def test_score_prefers_contiguous_then_subsequence():
    assert _score("", "anything") == 0
    assert _score("add", "Add task") == 0          # substring at start
    assert _score("task", "Add task") == 4         # substring later
    contiguous = _score("undo", "Undo last change")
    fuzzy = _score("ulc", "Undo last change")
    assert contiguous is not None and fuzzy is not None
    assert contiguous < fuzzy                      # contiguous always wins
    assert _score("zzz", "Add task") is None


@pytest.fixture
def palette(qtbot):
    calls = []
    cmds = [
        Command("Add task", "Action", lambda: calls.append("add"), hint="Ctrl+Shift+N"),
        Command("Undo", "Action", lambda: calls.append("undo")),
        Command("Today", "Quick views", lambda: calls.append("today")),
        Command("Overdue", "Quick views", lambda: calls.append("overdue")),
    ]
    p = CommandPalette(cmds, None)
    qtbot.addWidget(p)
    p._calls = calls
    return p


def test_palette_filters_and_ranks(palette):
    palette._input.setText("tod")
    assert [palette._list.item(i).text() for i in range(palette._list.count())][0] == "Today"

    palette._input.setText("")
    assert palette._list.count() == 4  # everything when empty


def test_palette_runs_the_selected_command(palette, qtbot):
    palette._input.setText("undo")
    palette._activate_current()
    assert palette._calls == ["undo"]


def test_main_window_collects_actions_views_and_filters(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    w.settings.save_filter("My urgent", "+urgent")
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    from jtask_gui.i18n import t

    cmds = w._collect_commands()
    labels = {c.label for c in cmds}
    cats = {c.category for c in cmds}
    assert "My urgent" in labels                        # saved filter
    assert t("palette.cat.action") in cats              # a toolbar/menu action
    assert t("palette.cat.filter") in cats
    assert any(c.hint for c in cmds)                    # actions carry shortcuts
    assert len(cmds) >= 12
