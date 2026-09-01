"""TagChipEditor wraps its chips — many tags grow it taller, never wider.

A single-row layout used to force the whole edit panel wider than its pane and
clip the Close button.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def editor(qtbot):
    from jtask_gui.widgets.chips import TagChipEditor

    e = TagChipEditor()
    qtbot.addWidget(e)
    return e


def test_width_is_bounded_by_the_widest_chip_not_the_total(editor):
    editor.set_tags(["aa", "bb", "cc"])
    three = editor.minimumSizeHint().width()
    editor.set_tags([f"tg{i:02d}" for i in range(20)])   # 20 equal-width chips
    assert editor.tags() == [f"tg{i:02d}" for i in range(20)]
    twenty = editor.minimumSizeHint().width()
    # the wrapping flow layout keeps the floor to one chip wide — with equal
    # chip widths, 3 tags and 20 tags need the same minimum
    assert twenty == three
    assert twenty < 200                      # nowhere near Σ of 20 chips


def test_height_grows_as_chips_wrap(editor):
    editor.set_tags(["a"])
    one_line = editor.heightForWidth(300)
    editor.set_tags([f"longer-tag-name-{i}" for i in range(15)])
    many = editor.heightForWidth(300)
    assert many > one_line * 2  # wrapped onto several rows


def test_add_remove_keeps_input_last(editor):
    editor.set_tags(["x", "y"])
    editor._input.setText("z")
    editor._commit_input()
    assert editor.tags() == ["x", "y", "z"]
    # the input widget is always the trailing item in the flow
    last = editor._flow.itemAt(editor._flow.count() - 1).widget()
    assert last is editor._input
    editor._remove("y")
    assert editor.tags() == ["x", "z"]
    last = editor._flow.itemAt(editor._flow.count() - 1).widget()
    assert last is editor._input


def test_edit_panel_min_width_survives_a_heavily_tagged_task(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    base = w._detail_host.minimumSizeHint().width()

    w._show_detail({
        "uuid": "u1", "id": 1, "description": "x" * 200,
        "project": "Work.Admin.Q3.Planning.Longname",
        "tags": [f"context-tag-{i}" for i in range(18)],
        "status": "pending",
    })
    qapp.processEvents()
    assert w._detail_host.minimumSizeHint().width() <= base + 5
