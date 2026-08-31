"""Per-content bidi direction — free text follows its own first strong char."""

from __future__ import annotations

from jtask import rtl


def test_first_strong_dir():
    assert rtl.first_strong_dir("Meeting with Arash") == "ltr"
    assert rtl.first_strong_dir("جلسه با آرش") == "rtl"
    assert rtl.first_strong_dir("  Meeting") == "ltr"          # skips whitespace
    assert rtl.first_strong_dir("۱۲۳ خرید") == "rtl"           # digits are neutral
    assert rtl.first_strong_dir("123 buy milk") == "ltr"
    assert rtl.first_strong_dir("") is None
    assert rtl.first_strong_dir("— · :") is None               # only neutrals
    assert rtl.first_strong_dir("!!! تماس") == "rtl"


def test_auto_isolate_wraps_with_first_strong_isolate():
    out = rtl.auto_isolate("Meeting with Arash")
    assert out.startswith("⁨") and out.endswith("⁩")
    assert "Meeting with Arash" in out
    assert rtl.auto_isolate("") == ""
