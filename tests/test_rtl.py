"""Tests for the Persian shaping / RTL / digit helper."""

import pytest

from jtask import rtl


@pytest.fixture(autouse=True)
def _reset_digit_mode():
    rtl.set_digit_mode(True)
    yield
    rtl.set_digit_mode(True)


def test_pure_latin_text_is_untouched():
    assert rtl.rtl("hello world") == "hello world"


def test_persian_letters_are_reshaped_to_presentation_forms():
    out = rtl.rtl("سلام")
    assert any("ﹰ" <= ch <= "﻿" for ch in out)
    assert "س" not in out  # bare isolated 'س' replaced by a joined form


def test_persian_run_is_visually_reordered():
    # logical "الف ب" -> visually "ب" comes first
    out = rtl.rtl("الف ب")
    from arabic_reshaper import reshape

    assert out.split()[0] == reshape("ب")


def test_mixed_persian_and_latin_keeps_latin_intact():
    out = rtl.rtl("پروژه Website")
    assert "Website" in out


def test_mixed_persian_and_url_keeps_url_intact():
    out = rtl.rtl("لینک https://example.io/x?a=1")
    assert "https://example.io/x?a=1" in out


def test_fa_and_en_digits():
    assert rtl.fa_digits("123") == "۱۲۳"
    assert rtl.en_digits("۱۲۳") == "123"


def test_num_uses_persian_digits_by_default():
    assert rtl.num(1403) == "۱۴۰۳"


def test_num_keeps_ids_ascii_even_when_persian_mode_on():
    assert rtl.num(42, is_id=True) == "42"


def test_num_respects_disabled_digit_mode():
    rtl.set_digit_mode(False)
    assert rtl.num(1403) == "1403"


def test_bidi_isolate_wraps_token_atomically():
    out = rtl.bidi_isolate("-۲۰.۰")
    assert out.startswith("⁦") and out.endswith("⁩")
    assert out[1:-1] == "-۲۰.۰"


def test_bidi_isolate_empty_is_noop():
    assert rtl.bidi_isolate("") == ""
