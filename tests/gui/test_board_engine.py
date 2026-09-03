"""NB-1: the board engine — schema, drop vocabulary, BoardView, persistence."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings

from jtask_gui import boards

# --- schema + drop vocabulary -------------------------------------

def test_builtin_gtd_board_shape():
    b = boards.builtin_board("gtd")
    assert b.builtin and [c.title for c in b.columns]  # titles resolved via t()
    assert len(b.columns) == 5
    assert b.columns[0].drop["type"] == "none"          # Inbox is view-only


@pytest.mark.parametrize(("drop", "expected"), [
    ({"type": "none"}, None),
    ({"type": "tags", "add": ["a"], "remove": ["b"]}, ("modify", ["+a", "-b"])),
    ({"type": "tags", "add": [], "remove": []}, None),
    ({"type": "attr", "field": "project", "value": "Work"}, ("modify", ["project:Work"])),
    ({"type": "attr", "field": "priority", "value": ""}, ("modify", ["priority:"])),
    ({"type": "uda", "name": "effort", "value": "L"}, ("modify", ["effort:L"])),
    ({"type": "verb", "verb": "done"}, ("done", [])),
    ({"type": "verb", "verb": "reopen"}, ("modify", ["status:pending"])),
    ({"type": "verb", "verb": "bogus"}, None),
])
def test_compile_drop(drop, expected):
    assert boards.compile_drop(drop) == expected


def test_validate_rejects_bad_boards():
    for bad in (
        {},
        {"name": "x"},
        {"name": "x", "columns": []},
        {"name": "x", "columns": [{"filter": "a"}]},          # no title
        {"name": "x", "columns": [{"title": "c", "drop": {"type": "zap"}}]},
    ):
        with pytest.raises(boards.BoardValidationError):
            boards.validate(bad)
    boards.validate(boards.builtin_board("gtd").to_dict())     # a good one passes


def test_board_json_roundtrip():
    b = boards.builtin_board("gtd")
    b2 = boards.from_json(boards.to_json(b))
    assert b2.to_dict() == b.to_dict()


# --- bc-1: per-column accent colour ------------------------------

def test_column_colour_is_optional_and_omitted_when_unset():
    c = boards.Column("A", "status:pending")
    assert c.color is None
    assert "color" not in c.to_dict()                       # existing boards unchanged
    assert boards.Column.from_dict({"title": "A"}).color is None


def test_column_colour_roundtrips_through_dict_and_json():
    c = boards.Column("Done", "status:completed", color="success")
    assert c.to_dict()["color"] == "success"
    b = boards.Board("B", [c])
    assert boards.from_json(boards.to_json(b)).columns[0].color == "success"


def test_unknown_colour_is_dropped_on_load_but_rejected_by_validate():
    assert boards.Column.from_dict({"title": "A", "color": "chartreuse"}).color is None
    with pytest.raises(boards.BoardValidationError):
        boards.validate({"name": "x", "columns": [
            {"title": "c", "filter": "a", "color": "chartreuse"}]})


def test_builtin_presets_carry_default_colours():
    gtd = {c.title: c.color for c in boards.builtin_board("gtd").columns}
    assert set(gtd.values()) >= {"primary", "waiting", "accent", "success"}
    assert list(gtd.values())[0] is None                    # Inbox has no accent
    kanban = [c.color for c in boards.builtin_board("status").columns]
    assert kanban == [None, "primary", "success"]
    # every preset colour is a known role
    for board in boards.all_builtins():
        for col in board.columns:
            assert col.color is None or col.color in boards.COLUMN_ACCENT_ROLES


def test_column_colour_survives_the_settings_persistence_path(qapp):
    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings

    Settings().save_board("Mine", {"columns": [
        {"title": "Done", "filter": "status:completed",
         "drop": {"type": "none"}, "color": "success"}]})
    reloaded = Settings().boards()["Mine"]["columns"][0]
    assert reloaded["color"] == "success"
    assert boards.Board.from_dict({"name": "Mine", **Settings().boards()["Mine"]}) \
        .columns[0].color == "success"


def test_board_view_renders_the_accent_strip_only_when_a_colour_is_set(qtbot):
    from jtask_gui.widgets.board_view import BoardView

    v = BoardView("dark")
    qtbot.addWidget(v)
    v.set_board(boards.Board("B", [
        boards.Column("Plain", "status:pending"),
        boards.Column("Done", "status:completed", color="success"),
    ]))
    plain, done = v._columns
    assert plain._accent.isHidden() and not plain._accent.property("accent")
    assert not done._accent.isHidden()
    assert done._accent.property("accent") == "success"


# --- persistence -------------------------------------------------

def test_board_store_roundtrips_and_orders(qapp):
    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.settings import Settings

    s = Settings()
    assert s.boards() == {} and s.board_order() == []
    s.save_board("Mine", {"columns": [{"title": "A", "filter": "status:pending",
                                       "drop": {"type": "none"}}]})
    s.save_board("Yours", {"columns": [{"title": "B", "filter": "+urgent",
                                        "drop": {"type": "none"}}]})
    assert Settings().board_order() == ["Mine", "Yours"]
    s.set_board_order(["Yours", "Mine"])
    assert Settings().board_order() == ["Yours", "Mine"]
    s.delete_board("Mine")
    assert list(Settings().boards()) == ["Yours"]
    assert Settings().board_order() == ["Yours"]


# --- BoardView -------------------------------------------------

@pytest.fixture
def view(qtbot):
    from jtask_gui.widgets.board_view import BoardView

    v = BoardView("dark")
    qtbot.addWidget(v)
    return v


def test_board_view_builds_one_column_per_definition(view):
    view.set_board(boards.builtin_board("gtd"))
    assert [c._base_title for c in view._columns] == \
        [c.title for c in boards.builtin_board("gtd").columns]
    # only columns with a real drop action accept drops
    assert not view._columns[0].acceptDrops()          # Inbox = none
    assert view._columns[2].acceptDrops()              # Waiting For = tags


def test_board_view_drop_emits_the_columns_drop_config(view):
    view.set_board(boards.builtin_board("gtd"))
    view._col_tasks = [[] for _ in range(5)]
    view._col_tasks[0] = [{"uuid": "u1", "description": "x"}]

    got = []
    view.boardDrop.connect(lambda *a: got.append(a))
    view._on_dropped("u1", 2)          # drop into "Waiting For"
    assert got == [({"uuid": "u1", "description": "x"},
                    {"type": "tags", "add": ["waiting"], "remove": ["someday"]})]


def test_main_window_board_drop_compiles_to_one_write(qapp, qtbot, tw_env, monkeypatch):
    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    calls = []
    monkeypatch.setattr(w, "_write", lambda fn, msg: calls.append(fn))

    w._board_drop({"uuid": "u9"}, {"type": "tags", "add": ["waiting"], "remove": ["someday"]})
    w._board_drop({"uuid": "u9"}, {"type": "verb", "verb": "done"})
    w._board_drop({"uuid": "u9"}, {"type": "none"})        # no-op

    import functools
    assert len(calls) == 2
    assert calls[0].func is taskwarrior.command
    assert calls[0].args == (["u9"], "modify", ["+waiting", "-someday"])
    assert calls[1].args == (["u9"], "done", [])
    _ = functools
