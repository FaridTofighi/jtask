"""NB-3: the Boards sidebar section + the board-management dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings


@pytest.fixture(autouse=True)
def _clean():
    from jtask_gui import i18n

    prev = i18n.lang()
    i18n.set_language("en")            # assert against English board/column names
    QSettings("jtask", "jtask-gui").clear()
    yield
    QSettings("jtask", "jtask-gui").clear()
    i18n.set_language(prev)


# --- sidebar --------------------------------------------------------

def test_sidebar_boards_section(qtbot):
    from jtask_gui.widgets.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.populate_boards(["GTD", "Kanban", "My board"])
    rows = [sb._boards.child(i).text(0) for i in range(sb._boards.childCount())]
    assert rows[:3] == ["GTD", "Kanban", "My board"]
    assert rows[-1] == sb._boards.child(sb._boards.childCount() - 1).text(0)  # manage row

    activated, managed = [], []
    sb.boardActivated.connect(activated.append)
    sb.boardManageRequested.connect(lambda: managed.append(True))
    sb.activate_spec({"kind": "board", "name": "My board"})
    sb.activate_spec({"kind": "board_manage"})
    assert activated == ["My board"] and managed == [True]


# --- MainWindow board wiring --------------------------------------

@pytest.fixture
def win(qapp, qtbot, tw_env):
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    return w


def test_board_names_lists_builtins_then_user_boards(win):
    win.settings.save_board("Mine", {"columns": [
        {"title": "c", "filter": "status:pending", "drop": {"type": "none"}}]})
    assert win._board_names() == ["GTD", "Kanban", "Mine"]


def test_show_board_switches_content_and_loads(win, qapp):
    win._show_board("GTD")
    qapp.processEvents()
    assert win._content.currentIndex() == 2
    assert win._board.current_board().name == "GTD"
    assert [c._base_title for c in win._board._columns][:2] == ["Inbox", "Next Actions"]


def test_show_user_board_by_name(win, qapp):
    win.settings.save_board("Focus", {"columns": [
        {"title": "Now", "filter": "+ACTIVE", "drop": {"type": "verb", "verb": "start"}},
        {"title": "Later", "filter": "status:pending -ACTIVE",
         "drop": {"type": "verb", "verb": "stop"}}]})
    win._show_board("Focus")
    qapp.processEvents()
    assert [c._base_title for c in win._board._columns] == ["Now", "Later"]


def test_boards_changed_repopulates_the_sidebar(win):
    win.settings.save_board("New1", {"columns": [
        {"title": "c", "filter": "status:pending", "drop": {"type": "none"}}]})
    win._on_boards_changed()
    rows = [win._sidebar._boards.child(i).text(0)
            for i in range(win._sidebar._boards.childCount())]
    assert "New1" in rows


# --- BoardManagerDialog -----------------------------------------

@pytest.fixture
def mgr(qapp):
    from jtask_gui.settings import Settings
    from jtask_gui.widgets.board_manager import BoardManagerDialog

    return BoardManagerDialog(Settings())


def test_manager_lists_builtins_and_from_preset_makes_a_copy(mgr):
    from jtask_gui.settings import Settings

    assert [mgr._boards.item(i).text() for i in range(mgr._boards.count())][:2] == \
        ["GTD", "Kanban"]
    mgr._from_preset("GTD")
    assert "GTD 2" in Settings().boards()
    assert len(Settings().boards()["GTD 2"]["columns"]) == 5


def test_manager_edits_persist_and_builtins_stay_readonly(mgr):
    from jtask_gui.settings import Settings

    mgr._from_preset("Kanban")
    names = mgr._all_board_names()
    mgr._boards.setCurrentRow(names.index("Kanban 2"))
    mgr._cols.setCurrentRow(0)
    assert mgr._col_title.isEnabled()
    mgr._col_title.setText("Backlog")
    assert Settings().boards()["Kanban 2"]["columns"][0]["title"] == "Backlog"

    # a built-in is not editable
    mgr._boards.setCurrentRow(names.index("Kanban"))
    mgr._cols.setCurrentRow(0)
    assert not mgr._col_title.isEnabled()


def test_manager_column_and_board_reorder_and_delete(mgr):
    from jtask_gui.settings import Settings

    mgr._from_preset("GTD")
    mgr._boards.setCurrentRow(mgr._all_board_names().index("GTD 2"))
    mgr._cols.setCurrentRow(0)
    mgr._move_col(1)
    assert [c["title"] for c in Settings().boards()["GTD 2"]["columns"]][:2] == \
        ["Next Actions", "Inbox"]
    mgr._add_col()
    assert len(Settings().boards()["GTD 2"]["columns"]) == 6
    mgr._delete()
    assert list(Settings().boards()) == []


def test_manager_drop_editor_roundtrips_every_type(mgr):
    from jtask_gui.widgets.board_manager import _DropEditor

    ed = _DropEditor()
    for drop in (
        {"type": "none"},
        {"type": "tags", "add": ["x"], "remove": ["y"]},
        {"type": "attr", "field": "priority", "value": "H"},
        {"type": "verb", "verb": "done"},
    ):
        ed.load(drop)
        assert ed.value() == drop


# --- NB-4: export / import --------------------------------------

def test_export_then_import_roundtrips(mgr, tmp_path):
    from jtask_gui import boards as B
    from jtask_gui.settings import Settings

    mgr._from_preset("GTD")
    mgr._boards.setCurrentRow(mgr._all_board_names().index("GTD 2"))
    path = tmp_path / "gtd.json"
    path.write_text(B.to_json(B.Board.from_dict(mgr._current_board_dict())),
                    encoding="utf-8")

    QSettings("jtask", "jtask-gui").clear()
    mgr2_settings = Settings()
    from jtask_gui.widgets.board_manager import BoardManagerDialog
    mgr2 = BoardManagerDialog(mgr2_settings)
    board = B.from_json(path.read_text(encoding="utf-8"))
    mgr2._user[board.name] = {"columns": [c.to_dict() for c in board.columns]}
    mgr2._order.append(board.name)
    mgr2._persist()
    assert len(Settings().boards()[board.name]["columns"]) == 5


def test_import_rejects_bad_files():
    from jtask_gui import boards as B

    for text in ("{ not json", '{"name": "x"}', '{"name": "y", "columns": []}'):
        with pytest.raises(ValueError):        # noqa: PT011 - JSONDecodeError / BoardValidationError
            B.from_json(text)


def test_manager_has_export_import_buttons(mgr):
    from PyQt6.QtWidgets import QPushButton

    labels = {b.text() for b in mgr.findChildren(QPushButton)}
    from jtask_gui.i18n import t
    assert t("board.manage.export") in labels
    assert t("board.manage.import") in labels
