"""Every surface that shows user-authored free text orients it by the two-tier
rule (UI language, overridden only by a clear majority of the opposite script)
— including a Persian sentence that starts with a Latin term."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

FA = "خرید نان از نانوایی"
EN = "Buy bread from the bakery"
FA_LATIN_FIRST = "Backup را بررسی کنم مربوط به دیتابیس Production"

RTL = Qt.LayoutDirection.RightToLeft
LTR = Qt.LayoutDirection.LeftToRight


@pytest.fixture(autouse=True)
def _ltr_app(qapp):
    """Run these in the English (LTR) UI so a Persian value going RTL is a real
    signal, not the ambient direction."""
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(LTR)
    yield
    qapp.setLayoutDirection(prev)


def _card_title(card):
    from PyQt6.QtWidgets import QLabel

    return next(w for w in card.findChildren(QLabel) if w.objectName() == "CardTitle")


def test_board_card_description_orients_to_its_text(qtbot):
    from jtask_gui.widgets.board_card import BoardCard

    fa_card = BoardCard({"uuid": "1", "description": FA})
    en_card = BoardCard({"uuid": "2", "description": EN})
    bug_card = BoardCard({"uuid": "3", "description": FA_LATIN_FIRST})
    for c in (fa_card, en_card, bug_card):
        qtbot.addWidget(c)

    assert _card_title(fa_card).layoutDirection() == RTL
    assert _card_title(fa_card).alignment() & Qt.AlignmentFlag.AlignRight
    assert _card_title(en_card).layoutDirection() == LTR
    assert _card_title(en_card).alignment() & Qt.AlignmentFlag.AlignLeft
    # the bug case: Persian sentence, Latin first word → still RTL
    assert _card_title(bug_card).layoutDirection() == RTL
    assert _card_title(bug_card).alignment() & Qt.AlignmentFlag.AlignRight


def test_annotation_rows_align_to_their_text(qtbot, tw_env):
    from jtask_gui.widgets.annotations_view import AnnotationsView

    v = AnnotationsView()
    qtbot.addWidget(v)
    v.load_task({"uuid": "u", "annotations": [
        {"entry": "20250101T000000Z", "description": FA},
        {"entry": "20250101T000100Z", "description": EN},
        {"entry": "20250101T000200Z", "description": FA_LATIN_FIRST},
    ]})
    assert v._list.item(0).textAlignment() & Qt.AlignmentFlag.AlignRight
    assert v._list.item(1).textAlignment() & Qt.AlignmentFlag.AlignLeft
    assert v._list.item(2).textAlignment() & Qt.AlignmentFlag.AlignRight  # bug case


def test_timer_indicator_follows_the_running_task_description(qtbot):
    from jtask_gui.widgets.timer_indicator import TimerIndicator

    ti = TimerIndicator()
    qtbot.addWidget(ti)
    ti.set_active_tasks([{"uuid": "u", "description": FA, "start": "20250101T000000Z"}])
    assert ti.layoutDirection() == RTL
    ti.set_active_tasks([{"uuid": "u", "description": EN, "start": "20250101T000000Z"}])
    assert ti.layoutDirection() == LTR


def test_detail_panel_annotation_summary_orients_to_its_text(qtbot, tw_env):
    from jtask_gui.widgets.detail_panel import DetailPanel

    p = DetailPanel()
    qtbot.addWidget(p)
    p.load_task({"uuid": "u", "description": "x", "status": "pending",
                 "annotations": [{"entry": "20250101T000000Z", "description": FA}]})
    assert p._ann_summary.layoutDirection() == RTL
    assert p._ann_summary.alignment() & Qt.AlignmentFlag.AlignRight
