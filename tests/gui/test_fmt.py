"""The single GUI number-formatting path."""

import pytest

from jtask.rtl import set_digit_mode


@pytest.fixture(autouse=True)
def _reset():
    set_digit_mode(True)
    yield
    set_digit_mode(True)


def test_num_persian_digits_default():
    from jtask_gui import fmt

    assert fmt.num(24) == "۲۴"
    assert fmt.num(50.0) == "۵۰"
    assert fmt.num(8.62) == "۸.۶"


def test_num_ascii_when_disabled():
    from jtask_gui import fmt

    set_digit_mode(False)
    assert fmt.num(24) == "24"
    assert fmt.num("۱۴۰۳-۰۷-۱۰") == "1403-07-10"


def test_num_isolate_keeps_sign_adjacent():
    from jtask.rtl import bidi_isolate
    from jtask_gui import fmt

    assert fmt.num(-4, isolate=True) == bidi_isolate("-۴")


def test_pct_appends_persian_percent_sign():
    from jtask_gui import fmt

    assert fmt.pct(42) == "۴۲٪"
