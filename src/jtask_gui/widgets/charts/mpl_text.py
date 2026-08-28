"""Persian text preparation for **matplotlib only**.

matplotlib is a low-level text renderer.  It shapes and bidi-reorders Arabic
script **only when it was built against libraqm** — the PyPI wheels usually are,
but a stripped install, an old version, or a PyInstaller bundle that drops the
shared lib will not be, and then raw Persian renders reversed and unjoined
(``نتخوس رادومن`` instead of ``نمودار سوختن``).

So this module is capability-aware:

* raqm present  → matplotlib shapes it; pass the string through unchanged
  (reshaping it ourselves would double-process and *break* it).
* raqm absent   → we reshape (arabic-reshaper) and reorder (python-bidi)
  ourselves, exactly as the CLI does for the terminal.

**Never** use this in the Qt widget layer — Qt always shapes natively (M1 rule);
running Qt text through this as well would double-process it.
"""

from __future__ import annotations

import arabic_reshaper
from bidi.algorithm import get_display

from ... import fmt


def _matplotlib_shapes_arabic() -> bool:
    try:
        from matplotlib import ft2font

        return bool(getattr(ft2font, "__libraqm_version__", ""))
    except Exception:  # noqa: BLE001 - be conservative, do it ourselves
        return False


MPL_SHAPES_ARABIC = _matplotlib_shapes_arabic()

_reshaper = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False, "support_ligatures": True}
)


def fa(text: str) -> str:
    """Prepare *text* for a matplotlib artist (title/label/legend/tick).

    Applies the active Persian-digit mode, then — only when matplotlib itself
    won't — reshapes and bidi-reorders the string.
    """
    if text is None:
        return ""
    out = fmt.digits(str(text))
    if MPL_SHAPES_ARABIC:
        return out
    return get_display(_reshaper.reshape(out))
