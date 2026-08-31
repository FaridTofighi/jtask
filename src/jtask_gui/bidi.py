"""Per-content bidi direction for editable text fields.

A free-text field (task description, annotation) must follow its *content*, not
the app's global layout direction: an English phrase left-aligned and LTR, a
Persian phrase right-aligned and RTL. ``bind_auto_direction`` flips a widget's
layout direction on every edit based on the first strong directional character.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLineEdit

from jtask.rtl import first_strong_dir

__all__ = ["bind_auto_direction"]

_DIR = {
    "ltr": Qt.LayoutDirection.LeftToRight,
    "rtl": Qt.LayoutDirection.RightToLeft,
}


def _apply(widget) -> None:
    if hasattr(widget, "toPlainText"):
        text = widget.toPlainText()
    else:
        text = widget.text()
    direction = _DIR.get(first_strong_dir(text))
    if direction is None:  # empty / neutral → follow the application
        app = QApplication.instance()
        direction = app.layoutDirection() if app else Qt.LayoutDirection.LeftToRight
    if widget.layoutDirection() != direction:
        widget.setLayoutDirection(direction)


def bind_auto_direction(widget) -> None:
    """Track *widget*'s content direction from now on (QLineEdit / QTextEdit /
    QPlainTextEdit). Applies once immediately so an empty field follows the app."""
    if isinstance(widget, QLineEdit):
        widget.textChanged.connect(lambda _t: _apply(widget))
    else:  # QTextEdit / QPlainTextEdit — textChanged carries no argument
        widget.textChanged.connect(lambda: _apply(widget))
    _apply(widget)
