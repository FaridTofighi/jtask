"""bd — text the user authored displays in its own first-strong direction,
regardless of which way the surrounding UI runs.

A Persian sentence must be right-aligned + RTL even in the English (LTR) UI;
an English one left-aligned + LTR even in the Persian (RTL) UI; a neutral /
empty value follows the application.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

from jtask_gui.bidi import (
    apply_content_direction,
    content_alignment,
    content_direction,
)

FA = "خرید نان از نانوایی"
EN = "Buy bread from the bakery"
NEUTRAL = "  123 — @#$"


@pytest.fixture
def app_ltr(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    yield qapp
    qapp.setLayoutDirection(prev)


@pytest.fixture
def app_rtl(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    yield qapp
    qapp.setLayoutDirection(prev)


def test_direction_follows_the_first_strong_char_not_the_app(app_ltr):
    assert content_direction(FA) == Qt.LayoutDirection.RightToLeft
    assert content_direction(EN) == Qt.LayoutDirection.LeftToRight


def test_direction_of_an_english_string_in_the_rtl_ui(app_rtl):
    assert content_direction(EN) == Qt.LayoutDirection.LeftToRight
    assert content_direction(FA) == Qt.LayoutDirection.RightToLeft


def test_neutral_or_empty_text_follows_the_application(app_ltr):
    assert content_direction(NEUTRAL) == Qt.LayoutDirection.LeftToRight
    assert content_direction("") == Qt.LayoutDirection.LeftToRight


def test_neutral_text_follows_an_rtl_application(app_rtl):
    assert content_direction(NEUTRAL) == Qt.LayoutDirection.RightToLeft
    assert content_direction("") == Qt.LayoutDirection.RightToLeft


def test_alignment_matches_direction(app_ltr):
    assert content_alignment(FA) & Qt.AlignmentFlag.AlignRight
    assert content_alignment(EN) & Qt.AlignmentFlag.AlignLeft
    assert content_alignment(NEUTRAL) & Qt.AlignmentFlag.AlignLeft


def test_alignment_is_absolute_so_an_rtl_view_cannot_flip_it(app_rtl):
    """A bare AlignRight is direction-relative — Qt flips it to visual-left in
    an RTL view. The flag must pin the visual edge (AlignAbsolute)."""
    assert content_alignment(FA) & Qt.AlignmentFlag.AlignAbsolute
    assert content_alignment(FA) & Qt.AlignmentFlag.AlignRight     # Persian → visual right
    assert content_alignment(EN) & Qt.AlignmentFlag.AlignLeft      # English → visual left
    assert content_alignment(EN) & Qt.AlignmentFlag.AlignAbsolute


def test_apply_orients_a_label_by_its_text(app_ltr, qtbot):
    from PyQt6.QtWidgets import QLabel

    lbl = QLabel(FA)
    qtbot.addWidget(lbl)
    apply_content_direction(lbl, FA)
    assert lbl.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert lbl.alignment() & Qt.AlignmentFlag.AlignRight

    lbl.setText(EN)
    apply_content_direction(lbl, EN)
    assert lbl.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert lbl.alignment() & Qt.AlignmentFlag.AlignLeft
