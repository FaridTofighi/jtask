"""TaskTableModel formatting and colour roles."""

import datetime

import pytest
from PyQt6.QtCore import Qt

from jtask.rtl import bidi_isolate
from jtask_gui.models.task_model import TASK_ROLE, TaskTableModel
from jtask_gui.theme import palette


def _row(model, col_key):
    keys = model.visible_columns()
    return keys.index(col_key)


def _plain(text: str) -> str:
    """Strip the bidi isolate wrappers (LRI / FSI / PDI) for readable assertions."""
    for ch in ("⁦", "⁨", "⁩"):
        text = text.replace(ch, "")
    return text


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


def test_foreground_muting_and_priority_colours():
    """Governed convention (mission-m audit, kept-with-test): the description
    leads — `id` / `urgency` render muted, `priority` is colour-coded by level,
    and none of this overrides a row-state colour."""
    pal = palette("شب")
    m = TaskTableModel(theme_name="شب")
    m.set_tasks([
        {"id": 1, "description": "high", "status": "pending", "priority": "H", "urgency": 9.0},
        {"id": 2, "description": "med", "status": "pending", "priority": "M", "urgency": 3.0},
        {"id": 3, "description": "low", "status": "pending", "priority": "L", "urgency": 1.0},
        {"id": 4, "description": "none", "status": "pending", "urgency": 0.0},
    ])

    def fg(row, key):
        c = m.data(m.index(row, _row(m, key)), Qt.ItemDataRole.ForegroundRole)
        return c.name().lower() if c is not None else None

    # id / urgency are muted on every row
    for r in range(4):
        assert fg(r, "id") == pal["text_muted"].lower()
        assert fg(r, "urgency") == pal["text_muted"].lower()

    # priority: H -> overdue (red), M -> due_soon (amber), L / none -> muted
    assert fg(0, "priority") == pal["overdue"].lower()
    assert fg(1, "priority") == pal["due_soon"].lower()
    assert fg(2, "priority") == pal["text_muted"].lower()
    assert fg(3, "priority") == pal["text_muted"].lower()

    # the description column keeps the default colour (no override) for a plain row
    assert fg(0, "description") is None

    # a row-state colour still wins over the per-column muting
    m.set_tasks([{"id": 9, "description": "done", "status": "completed",
                  "priority": "H", "urgency": 5.0}])
    assert fg(0, "id") == pal["completed"].lower()
    assert fg(0, "priority") == pal["completed"].lower()


@pytest.fixture
def ui_fa(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    yield
    qapp.setLayoutDirection(prev)


@pytest.fixture
def ui_en(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    yield
    qapp.setLayoutDirection(prev)


def _align(m, row, key):
    return m.data(m.index(row, _row(m, key)), Qt.ItemDataRole.TextAlignmentRole)


# the exact strings the first-strong heuristic mis-classified as LTR
BUG_DESCRIPTIONS = [
    "Backup را بررسی کنم مربوط به دیتابیس Production",
    "SSL Certificate یکی از سرویس‌ها را تمدید کنم",
]


@pytest.mark.parametrize("desc", BUG_DESCRIPTIONS)
def test_persian_sentence_starting_with_a_latin_term_is_right_aligned(ui_fa, desc):
    m = TaskTableModel()
    m.set_tasks([{"id": 1, "description": desc, "status": "pending"}])
    align = _align(m, 0, "description")
    assert align & int(Qt.AlignmentFlag.AlignRight)
    assert not align & int(Qt.AlignmentFlag.AlignLeft)
    assert align & int(Qt.AlignmentFlag.AlignAbsolute)
    # the cell text is wrapped in a RIGHT-TO-LEFT ISOLATE so the paragraph
    # reads RTL regardless of the view; the embedded Latin runs are untouched
    disp = _display(m, 0, "description")
    assert disp.startswith("⁧") and disp.endswith("⁩")
    assert disp[1:-1] == desc


@pytest.mark.parametrize("desc", BUG_DESCRIPTIONS)
def test_the_bug_descriptions_are_rtl_in_the_english_ui_too(ui_en, desc):
    m = TaskTableModel()
    m.set_tasks([{"id": 1, "description": desc, "status": "pending"}])
    assert _align(m, 0, "description") & int(Qt.AlignmentFlag.AlignRight)


def test_persian_first_sentence_still_right_aligned(ui_fa):
    m = TaskTableModel()
    m.set_tasks([{"id": 1, "description": "جلسه‌ی هفتگی شناخت فردی و تیمی",
                  "status": "pending"}])
    assert _align(m, 0, "description") & int(Qt.AlignmentFlag.AlignRight)


def test_a_real_english_description_is_left_aligned_in_the_persian_ui(ui_fa):
    """The majority-script override still catches a genuinely English value."""
    m = TaskTableModel()
    m.set_tasks([{"id": 1, "description": "Upgrade Docker Engine on staging servers",
                  "status": "pending"}])
    align = _align(m, 0, "description")
    assert align & int(Qt.AlignmentFlag.AlignLeft)
    assert not align & int(Qt.AlignmentFlag.AlignRight)
    assert _display(m, 0, "description").startswith("⁦")   # LEFT-TO-RIGHT ISOLATE


def test_persian_description_stays_visual_right_after_the_views_rtl_pass(ui_fa):
    """A bare AlignRight is flipped to the visual left by an RTL view; the model
    pins the edge absolutely so the description keeps reading from the right."""
    from PyQt6.QtWidgets import QStyle

    m = TaskTableModel()
    m.set_tasks([{"id": 1, "description": BUG_DESCRIPTIONS[0], "status": "pending"}])
    align = Qt.AlignmentFlag(_align(m, 0, "description"))
    visual = QStyle.visualAlignment(Qt.LayoutDirection.RightToLeft, align)
    assert visual & Qt.AlignmentFlag.AlignRight
    assert not visual & Qt.AlignmentFlag.AlignLeft


def test_id_column_alignment_is_unaffected_by_description_direction():
    """The fix for description direction must not regress the numeric columns:
    id / urgency always trail (number convention), regardless of any RTL text
    in the same row."""
    m = TaskTableModel()
    m.set_tasks([{"id": 7, "description": "جلسه با آرش", "status": "pending",
                  "urgency": 4.2}])
    for key in ("id", "urgency"):
        align = m.data(m.index(0, _row(m, key)), Qt.ItemDataRole.TextAlignmentRole)
        assert align & int(Qt.AlignmentFlag.AlignRight)


def test_project_column_direction_follows_content(ui_en):
    m = TaskTableModel()
    m.set_tasks([
        {"id": 1, "description": "x", "project": "Website", "status": "pending"},
        {"id": 2, "description": "y", "project": "خانه", "status": "pending"},
    ])
    col = _row(m, "project")
    assert m.data(m.index(0, col), Qt.ItemDataRole.TextAlignmentRole) \
        & int(Qt.AlignmentFlag.AlignLeft)
    assert m.data(m.index(1, col), Qt.ItemDataRole.TextAlignmentRole) \
        & int(Qt.AlignmentFlag.AlignRight)
    assert _display(m, 1, "project").startswith("⁧")     # RTL project name → RLI


def test_set_tasks_resets_model(qtbot):
    m = TaskTableModel()
    with qtbot.waitSignal(m.modelReset):
        m.set_tasks([{"id": 1, "description": "a", "status": "pending"}])
    assert m.rowCount() == 1
    assert m.data(m.index(0, 0), TASK_ROLE)["description"] == "a"
