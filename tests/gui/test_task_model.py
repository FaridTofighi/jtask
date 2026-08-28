"""TaskTableModel formatting and colour roles."""

import datetime

from PyQt6.QtCore import Qt

from jtask.rtl import bidi_isolate
from jtask_gui.models.task_model import TASK_ROLE, TaskTableModel
from jtask_gui.theme import palette


def _row(model, col_key):
    keys = model.visible_columns()
    return keys.index(col_key)


def _plain(text: str) -> str:
    """Strip the bidi isolate wrapper for readable assertions."""
    return text.replace("⁦", "").replace("⁩", "")


def _display(model, row, key):
    return model.data(model.index(row, _row(model, key)), Qt.ItemDataRole.DisplayRole)


def test_dates_render_with_persian_digits_by_default():
    m = TaskTableModel(persian_digits=True)
    m.set_tasks([{"id": 1, "description": "x", "due": "۱۴۰۳-۰۷-۱۰", "status": "pending"}])
    assert _plain(_display(m, 0, "due")) == "۱۴۰۳-۰۷-۱۰"


def test_persian_digits_can_be_disabled():
    m = TaskTableModel(persian_digits=False)
    m.set_tasks([{"id": 1, "description": "x", "due": "۱۴۰۳-۰۷-۱۰", "status": "pending"}])
    assert _plain(_display(m, 0, "due")) == "1403-07-10"


def test_id_column_is_always_ascii():
    m = TaskTableModel(persian_digits=True)
    m.set_tasks([{"id": 42, "description": "x", "status": "pending"}])
    assert _plain(_display(m, 0, "id")) == "42"


def test_negative_urgency_keeps_sign_adjacent_to_number():
    m = TaskTableModel(persian_digits=True)
    m.set_tasks([{"id": 1, "description": "x", "status": "pending", "urgency": -20.0}])
    raw = _display(m, 0, "urgency")
    # the sign+number is one bidi-isolated unit → '-' immediately before digits
    assert raw == bidi_isolate("-۲۰.۰")
    assert _plain(raw) == "-۲۰.۰"
    assert _plain(raw)[0] == "-"


def test_positive_urgency_and_ascii_mode():
    m = TaskTableModel(persian_digits=False)
    m.set_tasks([{"id": 1, "description": "x", "status": "pending", "urgency": 8.62}])
    assert _display(m, 0, "urgency") == bidi_isolate("8.6")


def test_zero_urgency_renders_without_sign():
    m = TaskTableModel(persian_digits=True)
    m.set_tasks([{"id": 1, "description": "x", "status": "pending", "urgency": 0}])
    assert _plain(_display(m, 0, "urgency")) == "۰.۰"


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
