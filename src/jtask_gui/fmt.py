"""The one number-formatting path for the whole GUI.

Every user-facing number — table cells, chart ticks, progress percentages,
status-bar counts — goes through :func:`num` so Persian/ASCII digit mode is
honoured consistently and signed/structured tokens stay bidi-atomic.
"""

from __future__ import annotations

from jtask import jalali
from jtask.rtl import bidi_isolate, digit_mode

__all__ = ["num", "pct", "digits"]


def _plain(value) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else f"{value:.1f}"
    return str(value)


def digits(text: str) -> str:
    """Apply the active digit mode to an already-formatted string."""
    return jalali.to_persian_digits(text) if digit_mode() else jalali.normalize_digits(text)


def num(value, *, isolate: bool = False) -> str:
    """Format *value* respecting the active digit mode.

    *isolate* wraps the result in bidi isolates so a sign / separator never
    floats to the wrong end inside RTL text.
    """
    s = digits(_plain(value))
    return bidi_isolate(s) if isolate else s


def pct(value) -> str:
    return num(value) + "٪"
