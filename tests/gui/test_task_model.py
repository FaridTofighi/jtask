"""TaskTableModel formatting and colour roles."""

import datetime

from PyQt6.QtCore import Qt

from jtask_gui.models.task_model import TASK_ROLE, TaskTableModel
from jtask_gui.theme import palette


def _row(model, col_key):
    keys = model.visible_columns()
    return keys.index(col_key)


def test_dates_render_with_persian_digits_by_default():
    m = TaskTableModel(persian_digits=True)
    m.set_tasks([{"id": 1, "description": "x", "due": "۱۴۰۳-۰۷-۱۰", "status": "pending"}])
    idx = m.index(0, _row(m, "due"))
    assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "۱۴۰۳-۰۷-۱۰"


def test_persian_digits_can_be_disabled():
    m = TaskTableModel(persian_digits=False)
    m.set_tasks([{"id": 1, "description": "x", "due": "۱۴۰۳-۰۷-۱۰", "status": "pending"}])
    idx = m.index(0, _row(m, "due"))
    assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "1403-07-10"


def test_id_column_is_always_ascii():
    m = TaskTableModel(persian_digits=True)
    m.set_tasks([{"id": 42, "description": "x", "status": "pending"}])
    idx = m.index(0, _row(m, "id"))
    assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "42"


def _dt(days):
    d = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return d.strftime("%Y%m%dT%H%M%SZ")


def test_overdue_due_cell_uses_overdue_colour():
    m = TaskTableModel(theme_name="شب")
    m.set_tasks([{"id": 1, "description": "x", "status": "pending",
                  "due_gregorian": _dt(-2), "due": "گذشته"}])
    idx = m.index(0, _row(m, "due"))
    colour = m.data(idx, Qt.ItemDataRole.ForegroundRole)
    assert colour.name().lower() == palette("شب")["overdue"].lower()


def test_due_soon_cell_uses_due_soon_colour():
    m = TaskTableModel(theme_name="شب", due_soon_days=3)
    m.set_tasks([{"id": 1, "description": "x", "status": "pending",
                  "due_gregorian": _dt(1), "due": "به‌زودی"}])
    idx = m.index(0, _row(m, "due"))
    colour = m.data(idx, Qt.ItemDataRole.ForegroundRole)
    assert colour.name().lower() == palette("شب")["due_soon"].lower()


def test_completed_task_is_struck_through_and_dimmed():
    m = TaskTableModel(theme_name="شب")
    m.set_tasks([{"id": 1, "description": "x", "status": "completed"}])
    idx = m.index(0, _row(m, "description"))
    assert m.data(idx, Qt.ItemDataRole.FontRole).strikeOut() is True
    assert m.data(idx, Qt.ItemDataRole.ForegroundRole).name().lower() == \
        palette("شب")["completed"].lower()


def test_set_tasks_resets_model(qtbot):
    m = TaskTableModel()
    with qtbot.waitSignal(m.modelReset):
        m.set_tasks([{"id": 1, "description": "a", "status": "pending"}])
    assert m.rowCount() == 1
    assert m.data(m.index(0, 0), TASK_ROLE)["description"] == "a"
