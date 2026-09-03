"""Base direction for user-authored free text.

The rule (see ``jtask_gui.bidi``): the paragraph base direction is the **UI
language's** direction, overridden to the opposite direction **only when the
text is a clear majority of the opposite script** — not merely first-charactered
that way. This is what stops a Persian sentence that happens to start with a
Latin term ("Backup را بررسی کنم…") from rendering as an LTR paragraph.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

from jtask_gui.bidi import (
    apply_content_direction,
    content_alignment,
    content_direction,
    directional_isolate,
)

RTL = Qt.LayoutDirection.RightToLeft
LTR = Qt.LayoutDirection.LeftToRight

# --- the concrete evidence the first-strong heuristic failed on ---
BUG_1 = "Backup را بررسی کنم مربوط به دیتابیس Production"
BUG_2 = "SSL Certificate یکی از سرویس‌ها را تمدید کنم"

FA_PLAIN = "جلسه‌ی هفتگی شناخت فردی و تیمی"          # starts Persian
EN_PLAIN = "Upgrade Docker Engine on staging servers"  # genuinely English
EN_ONE_FA_WORD = "Deploy کن به production"             # majority Latin
NEUTRAL = "  1403-06-14  #42"


@pytest.fixture
def ui_fa(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(RTL)
    yield
    qapp.setLayoutDirection(prev)


@pytest.fixture
def ui_en(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(LTR)
    yield
    qapp.setLayoutDirection(prev)


# --- 1. the bug: Persian sentence starting with a Latin word ------

@pytest.mark.parametrize("text", [BUG_1, BUG_2])
def test_persian_sentence_starting_with_a_latin_term_is_rtl_in_the_persian_ui(ui_fa, text):
    assert content_direction(text) == RTL
    assert content_alignment(text) & Qt.AlignmentFlag.AlignRight


@pytest.mark.parametrize("text", [BUG_1, BUG_2])
def test_the_same_sentence_is_rtl_in_the_english_ui_too_by_majority(ui_en, text):
    # majority-Persian → RTL even though the UI default is LTR
    assert content_direction(text) == RTL


# --- 2. no regression: Persian-first sentence still RTL ----------

def test_persian_first_sentence_is_rtl(ui_fa):
    assert content_direction(FA_PLAIN) == RTL


# --- 3. the majority override still catches real English --------

def test_a_genuinely_english_description_is_ltr_in_the_persian_ui(ui_fa):
    assert content_direction(EN_PLAIN) == LTR
    assert content_alignment(EN_PLAIN) & Qt.AlignmentFlag.AlignLeft


def test_mostly_english_with_one_persian_word_is_ltr(ui_fa):
    assert content_direction(EN_ONE_FA_WORD) == LTR


# --- 4. mirror cases with the UI in English --------------------

def test_persian_sentence_in_the_english_ui_is_rtl(ui_en):
    assert content_direction(FA_PLAIN) == RTL


def test_english_sentence_in_the_english_ui_is_ltr(ui_en):
    assert content_direction(EN_PLAIN) == LTR


# --- neutral / empty follows the UI ---------------------------

def test_neutral_text_follows_the_ui_language(ui_fa):
    assert content_direction(NEUTRAL) == RTL
    assert content_direction("") == RTL


def test_neutral_text_follows_the_ui_language_en(ui_en):
    assert content_direction(NEUTRAL) == LTR
    assert content_direction("") == LTR


# --- alignment is absolute (an RTL view can't flip it) --------

def test_alignment_is_absolute(ui_fa):
    for text in (BUG_1, FA_PLAIN, EN_PLAIN):
        assert content_alignment(text) & Qt.AlignmentFlag.AlignAbsolute


# --- directional_isolate pins the paragraph direction --------

def test_directional_isolate_wraps_by_resolved_direction(ui_fa):
    _RLI, _LRI, _PDI = "⁧", "⁦", "⁩"
    assert directional_isolate(BUG_1).startswith(_RLI)      # Persian sentence → RLI
    assert directional_isolate(BUG_1).endswith(_PDI)
    assert directional_isolate(EN_PLAIN).startswith(_LRI)   # English → LRI
    # the inner text is untouched — embedded runs still shape natively
    assert directional_isolate(BUG_1)[1:-1] == BUG_1


def test_apply_orients_a_label(ui_fa, qtbot):
    from PyQt6.QtWidgets import QLabel

    lbl = QLabel()
    qtbot.addWidget(lbl)
    apply_content_direction(lbl, BUG_1)
    assert lbl.layoutDirection() == RTL
    assert lbl.alignment() & Qt.AlignmentFlag.AlignRight

    apply_content_direction(lbl, EN_PLAIN)
    assert lbl.layoutDirection() == LTR
    assert lbl.alignment() & Qt.AlignmentFlag.AlignLeft
