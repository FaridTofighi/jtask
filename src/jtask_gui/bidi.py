"""Base direction for text the user authored (task descriptions, annotations …).

Like a word processor, the *paragraph* base direction is tied to the active
input language, not re-derived per string from whichever character comes first
(that misclassifies a Persian sentence starting with a Latin term — a product
name, an acronym — as an English paragraph). The rule:

1. **default = the UI language's direction** (Persian UI → RTL, English UI → LTR);
2. **overridden to the opposite direction only when the text is a clear
   majority of the opposite script** (``_MAJORITY`` of its letters) — a
   genuinely foreign-language value, e.g. an English task description shown
   while the UI is Persian.

Embedded runs of the other script (a Latin word inside a Persian sentence) keep
shaping and ordering natively *within* the paragraph — Qt handles that; this
module only fixes the paragraph's base direction and alignment.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLineEdit

from jtask.rtl import bidi_isolate, bidi_isolate_rtl, script_balance

__all__ = [
    "content_direction",
    "content_alignment",
    "directional_isolate",
    "apply_content_direction",
    "align_item",
    "bind_auto_direction",
]

_RTL = Qt.LayoutDirection.RightToLeft
_LTR = Qt.LayoutDirection.LeftToRight

# fraction of a string's letters that must be the *opposite* script before it
# overrides the UI-language default. A Persian sentence with one leading Latin
# term stays well under this; a real English description is at/above it.
_MAJORITY = 0.6


def _ui_direction() -> Qt.LayoutDirection:
    app = QApplication.instance()
    return app.layoutDirection() if app is not None else _LTR


def content_direction(text: str) -> Qt.LayoutDirection:
    """Base layout direction *text* should render in (see the module docstring)."""
    ui = _ui_direction()
    rtl_n, ltr_n = script_balance(text)
    total = rtl_n + ltr_n
    if total == 0:
        return ui                                   # no letters → follow the UI
    if ui == _RTL and ltr_n / total >= _MAJORITY:
        return _LTR
    if ui == _LTR and rtl_n / total >= _MAJORITY:
        return _RTL
    return ui


def content_alignment(text: str) -> Qt.AlignmentFlag:
    """Horizontal alignment matching :func:`content_direction` (no vertical bit).

    ``AlignAbsolute`` is always set: a bare ``AlignRight`` is direction-relative
    and Qt flips it to the visual left inside an RTL view/widget — the wrong
    edge. The flag names the *visual* edge.
    """
    visual = (
        Qt.AlignmentFlag.AlignRight
        if content_direction(text) == _RTL
        else Qt.AlignmentFlag.AlignLeft
    )
    return visual | Qt.AlignmentFlag.AlignAbsolute


def directional_isolate(text: str) -> str:
    """Wrap *text* so its paragraph base direction is pinned to
    :func:`content_direction` no matter what widget / view it lands in — for
    surfaces (table cells, graphics items) where the base direction can't be
    set on the widget itself. Embedded opposite-script runs are unaffected."""
    if not text:
        return text
    if content_direction(text) == _RTL:
        return bidi_isolate_rtl(text)
    return bidi_isolate(text)          # LRI … PDI


def apply_content_direction(widget, text: str) -> None:
    """Orient a read-only text widget (``QLabel``, ``QAbstractButton``) to
    :func:`content_direction` of *text*."""
    widget.setLayoutDirection(content_direction(text))
    if hasattr(widget, "setAlignment"):
        widget.setAlignment(content_alignment(text) | Qt.AlignmentFlag.AlignVCenter)


def align_item(item, text: str) -> None:
    """Set a view item's text alignment from :func:`content_direction` of *text*."""
    item.setTextAlignment(content_alignment(text) | Qt.AlignmentFlag.AlignVCenter)


def _apply(widget) -> None:
    text = widget.toPlainText() if hasattr(widget, "toPlainText") else widget.text()
    direction = content_direction(text)
    if widget.layoutDirection() != direction:
        widget.setLayoutDirection(direction)


def bind_auto_direction(widget) -> None:
    """Keep an editable field's base direction in step with its content
    (``content_direction``) — the UI language until it's typed/pasted full of
    the other script. Applies once immediately."""
    if isinstance(widget, QLineEdit):
        widget.textChanged.connect(lambda _t: _apply(widget))
    else:  # QTextEdit / QPlainTextEdit — textChanged carries no argument
        widget.textChanged.connect(lambda: _apply(widget))
    _apply(widget)
