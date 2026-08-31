"""Persian text shaping, bidi reordering and digit rendering.

Every piece of Persian text in jtask is passed through :func:`rtl` immediately
before it is printed.  Terminals render left-to-right and do not join Arabic
letters, so raw Persian strings would appear disconnected and mirrored.
:func:`rtl` reshapes (contextual letter forms) then applies the Unicode bidi
algorithm so the visual byte order is what a Persian reader expects.
"""

from __future__ import annotations

import unicodedata

import arabic_reshaper
from bidi.algorithm import get_display

from .jalali import normalize_digits, to_persian_digits

__all__ = [
    "rtl", "fa_digits", "en_digits", "num", "set_digit_mode", "digit_mode",
    "bidi_isolate", "first_strong_dir", "auto_isolate",
]

# Unicode isolate controls — wrap a structured token (a signed number, a
# hyphen-separated date) so the bidi algorithm treats it as one atomic LTR run
# and never floats its sign/separators to the wrong side inside RTL text.
_LRI = "⁦"  # LEFT-TO-RIGHT ISOLATE
_PDI = "⁩"  # POP DIRECTIONAL ISOLATE
_FSI = "⁨"  # FIRST STRONG ISOLATE — base direction taken from 1st strong char


def bidi_isolate(text: str) -> str:
    """Return *text* wrapped so bidi renders it as one left-to-right unit."""
    if not text:
        return text
    return f"{_LRI}{text}{_PDI}"


def first_strong_dir(text: str) -> str | None:
    """``"ltr"`` / ``"rtl"`` / ``None`` from the first strong directional char.

    This is what decides whether a free-text field like a task description
    should read left-to-right ("Meeting with Arash") or right-to-left
    ("جلسه با آرش"), independent of the app's global layout direction.
    """
    for ch in text:
        bidi = unicodedata.bidirectional(ch)
        if bidi == "L":
            return "ltr"
        if bidi in ("R", "AL"):
            return "rtl"
    return None


def auto_isolate(text: str) -> str:
    """Wrap *text* in a FIRST STRONG ISOLATE so the bidi algorithm picks its
    base direction from its own first strong character — a Latin phrase renders
    LTR and a Persian phrase RTL even inside an otherwise RTL paragraph."""
    if not text:
        return text
    return f"{_FSI}{text}{_PDI}"

_PERSIAN_DIGITS_DEFAULT = True
_state = {"persian_digits": _PERSIAN_DIGITS_DEFAULT}

_reshaper = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False, "support_ligatures": True}
)


def set_digit_mode(persian: bool) -> None:
    """Set whether :func:`num` renders Persian digits by default."""
    _state["persian_digits"] = persian


def digit_mode() -> bool:
    """Return the current default digit mode (True == Persian digits)."""
    return _state["persian_digits"]


def rtl(text: str) -> str:
    """Reshape and bidi-reorder *text* for correct terminal display.

    Safe on mixed content: Latin words, URLs and tags inside Persian text are
    preserved verbatim and kept in reading order by the bidi algorithm.
    """
    if not text:
        return text
    return get_display(_reshaper.reshape(text))


def fa_digits(text: str) -> str:
    """Convert ASCII digits in *text* to Persian digits."""
    return to_persian_digits(text)


def en_digits(text: str) -> str:
    """Convert Persian/Arabic digits in *text* to ASCII digits."""
    return normalize_digits(text)


def num(value: object, *, is_id: bool = False, persian: bool | None = None) -> str:
    """Render *value* as a string, using Persian digits unless disabled.

    *is_id* forces ASCII digits (task IDs stay easy to type regardless of the
    global digit mode).  *persian* overrides the global mode explicitly.
    """
    s = str(value)
    if is_id:
        return normalize_digits(s)
    use_persian = _state["persian_digits"] if persian is None else persian
    return to_persian_digits(s) if use_persian else normalize_digits(s)
