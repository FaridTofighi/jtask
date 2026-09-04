"""The annotations tab redesign: wrapped note cards, the multi-line input
above the button row, bounded theme-derived per-note tints, and reusing the
table-row selection convention (background-only, no per-card border)."""

from __future__ import annotations

from PyQt6.QtWidgets import QPlainTextEdit

from jtask.rtl import bidi_isolate
from jtask_gui.calendar_system import active
from jtask_gui.theme import NOTE_TINT_ROLES, THEMES
from jtask_gui.widgets.annotations_view import AnnotationsView

LONG_NOTE = (
    "پیگیری با تیم پشتیبانی دربارهٔ خطای گزارش‌شده در محیط تولید و هماهنگی برای "
    "برنامه‌ریزی یک جلسهٔ فوری با مسئول زیرساخت جهت بررسی علت اصلی مشکل"
)


def _card(view, row):
    return view._list.itemWidget(view._list.item(row))


# --- 1. wrapping (the display bug) ------------------------------

def test_long_note_wraps_instead_of_needing_horizontal_scroll(qtbot):
    from PyQt6.QtCore import Qt

    v = AnnotationsView()
    qtbot.addWidget(v)
    assert v._list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    v.load_task({"uuid": "u", "annotations": [{"entry": "", "description": LONG_NOTE}]})
    card = _card(v, 0)
    assert card._body.wordWrap()

    # a real wrap: the same text needs much more vertical room in a narrow
    # column than in a wide one (a clipped/scrolling single line would not)
    narrow = card._body.heightForWidth(180)
    wide = card._body.heightForWidth(900)
    assert narrow > wide > 0


def test_relayout_updates_item_size_hints_to_the_viewport_width(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    v.load_task({"uuid": "u", "annotations": [{"entry": "", "description": LONG_NOTE}]})
    v.resize(500, 400)
    v._list.relayout()
    item = v._list.item(0)
    card = v._list.itemWidget(item)
    assert item.sizeHint().height() == card.sizeHint().height()


# --- 2. the add-note input: multi-line, above the buttons -------

def test_input_is_multiline_and_sits_above_the_button_row(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    assert isinstance(v._input, QPlainTextEdit)
    assert v._input.minimumHeight() > 24        # comfortably more than one line

    lay = v.layout()
    positions = {}
    for i in range(lay.count()):
        item = lay.itemAt(i)
        if item.widget() is v._input:
            positions["input"] = i
        if item.layout() is v._button_row:
            positions["buttons"] = i
    assert positions["input"] < positions["buttons"]


def test_add_reads_the_multiline_text_and_clears_it(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    v._uuid = "u"
    v._input.setPlainText("line one\nline two")
    got = []
    v.annotateRequested.connect(lambda u, txt: got.append((u, txt)))
    v._add()
    assert got == [("u", "line one\nline two")]
    assert v._input.toPlainText() == ""


# --- 3. per-note tint: bounded, theme-derived, cycled -----------

def test_note_tint_roles_are_a_small_bounded_set_present_in_every_theme():
    assert len(NOTE_TINT_ROLES) == 4
    for name, pal in THEMES.items():
        for role in NOTE_TINT_ROLES:
            assert role in pal, (name, role)


def test_consecutive_cards_cycle_through_the_tint_set(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    v.load_task({"uuid": "u", "annotations": [
        {"entry": "", "description": f"note {i}"} for i in range(6)
    ]})
    tints = [_card(v, i).property("tint") for i in range(6)]
    assert tints == ["1", "2", "3", "4", "1", "2"]
    assert set(tints) <= {"1", "2", "3", "4"}


# --- timestamp: shared formatter + bidi_isolate, separated from body ---

def test_timestamp_uses_the_shared_formatter_and_is_bidi_isolated(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    raw = "20250101T091500Z"
    v.load_task({"uuid": "u", "annotations": [{"entry": raw, "description": "x"}]})
    card = _card(v, 0)
    expected = bidi_isolate(active().format_utc(raw, "short"))
    assert card._when_label.text() == expected
    assert card._when_label.text() != card._body.text()   # separated, not run together


# --- selection: same background-only convention as table rows ---

def test_selecting_a_card_sets_the_selected_property_like_a_table_row(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    v.load_task({"uuid": "u", "annotations": [
        {"entry": "", "description": "a"}, {"entry": "", "description": "b"},
    ]})
    v._list.setCurrentRow(0)
    assert _card(v, 0).property("selected") is True
    assert not _card(v, 1).property("selected")

    v._list.setCurrentRow(1)
    assert not _card(v, 0).property("selected")
    assert _card(v, 1).property("selected") is True


def test_selected_card_qss_reuses_the_selection_token_not_a_new_style():
    import re

    from jtask_gui import theme

    qss = re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)
    m = re.search(r'AnnotationCard\[selected="true"\]\s*\{([^}]*)\}', qss)
    assert m and "@selection@" in m.group(1)


def test_delete_emits_for_the_selected_note(qtbot):
    v = AnnotationsView()
    qtbot.addWidget(v)
    v.load_task({"uuid": "u", "annotations": [
        {"entry": "", "description": "keep"}, {"entry": "", "description": "drop me"},
    ]})
    v._list.setCurrentRow(1)
    got = []
    v.denotateRequested.connect(lambda u, txt: got.append((u, txt)))
    v._delete()
    assert got == [("u", "drop me")]


# --- both themes render without missing tokens -------------------

def test_annotation_card_renders_in_both_themes(qtbot):
    from jtask_gui import icons
    from jtask_gui.theme import render_qss

    v = AnnotationsView()
    qtbot.addWidget(v)
    v.load_task({"uuid": "u", "annotations": [
        {"entry": "20250101T000000Z", "description": LONG_NOTE},
    ]})
    for name in THEMES:
        icons.set_theme(name)
        qss = render_qss(name)
        assert "@" not in qss.split("/* annotations")[1].split("/*")[0]
