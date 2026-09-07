"""Bug: after a write (adding an annotation, editing a field, an undo …) the
table lost its selection and the open detail panel kept showing stale data
until the user manually reselected the row.

Fix: `MainWindow.refresh_all()` remembers the selected uuid(s) and
`TaskTable.select_uuids()` reselects by identity (not row index) once the
table reloads; `_populate_table` independently reloads the open detail panel
for whatever task it is currently showing, whether or not that task is still
selected/visible in the table.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _en():
    from jtask_gui import i18n

    prev = i18n.lang()
    i18n.set_language("en")
    yield
    i18n.set_language(prev)


@pytest.fixture
def win(qapp, qtbot, tw_env):
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    tw.add(["Task A", "priority:L"])
    tw.add(["Task B", "priority:L"])
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

    for _ in range(8):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()


def _uuid(desc: str) -> str:
    from jtask import taskwarrior as tw

    return tw.export([f"description:{desc}"])[0]["uuid"]


def _select(win, qapp, uuid: str) -> None:
    win._table.select_uuids([uuid])
    _drain(qapp)


# --- 1. adding an annotation from the open panel -----------------

def test_annotation_preserves_selection_and_shows_immediately(win, qapp):
    uuid = _uuid("Task A")
    _select(win, qapp, uuid)
    assert win._detail_host.isVisibleTo(win)          # selecting opens the panel

    win._annotations_view.annotateRequested.emit(uuid, "checked the logs")
    _drain(qapp)

    assert win._table.selected_uuids() == [uuid]       # 1. selection preserved
    assert win._detail_host.isVisibleTo(win)            # panel still open
    assert win._annotations_view._list.count() == 1     # 2. no manual reselect needed
    card = win._annotations_view._list.itemWidget(win._annotations_view._list.item(0))
    assert card.desc == "checked the logs"
    assert "checked the logs" in win._detail._ann_summary.text()


# --- 2. a plain field edit from within the panel ------------------

def test_field_edit_from_panel_preserves_selection_and_updates_panel(win, qapp):
    uuid = _uuid("Task A")
    _select(win, qapp, uuid)
    assert win._detail._priority.currentText() != "High"

    win._save_task(uuid, ["priority:H"])
    _drain(qapp)

    assert win._table.selected_uuids() == [uuid]
    assert win._detail.current_uuid() == uuid
    assert win._detail._priority.currentText() == "High"


# --- 3. a write to the shown task from elsewhere in the app -------

def test_write_from_elsewhere_refreshes_the_open_panel(win, qapp):
    from jtask import taskwarrior as tw

    uuid = _uuid("Task A")
    _select(win, qapp, uuid)
    assert win._detail.current_uuid() == uuid

    win._table._done_shortcut()                        # Ctrl+D path
    _drain(qapp)

    after = tw.export([uuid])[0]
    assert after["status"] == "completed"
    # the default view no longer contains a completed task -> it can't stay
    # selected, but the still-open panel must not be left showing the old data
    assert win._detail.current_uuid() == uuid
    assert win._detail._status.state == "completed"


def test_undo_affecting_the_shown_task_refreshes_the_panel(win, qapp):
    from jtask import taskwarrior as tw

    uuid = _uuid("Task A")
    _select(win, qapp, uuid)
    win._save_task(uuid, ["priority:H"])
    _drain(qapp)
    assert win._detail._priority.currentText() == "High"

    win._write(lambda: tw.run(["undo"]), "undone")
    _drain(qapp)

    assert win._detail.current_uuid() == uuid
    assert win._detail._priority.currentText() != "High"


# --- 4. no regression: switching to a different task still works --

def test_switching_selection_to_another_task_loads_its_own_data(win, qapp):
    uuid_a, uuid_b = _uuid("Task A"), _uuid("Task B")
    _select(win, qapp, uuid_a)
    assert win._detail.current_uuid() == uuid_a
    assert win._detail._description.text() == "Task A"

    _select(win, qapp, uuid_b)
    assert win._detail.current_uuid() == uuid_b
    assert win._detail._description.text() == "Task B"     # not stale/mixed with A

    # and A stays untouched by whatever refresh happened while switching
    from jtask import taskwarrior as tw
    assert tw.export([uuid_a])[0]["description"] == "Task A"
