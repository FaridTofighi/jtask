"""Per-content bidi direction for text that the user authored.

A free-text value (task description, annotation, project name) must display in
the direction of its *own* first strong character — a Persian sentence right to
right-aligned and RTL, an English one left-aligned and LTR — no matter which
way the surrounding UI runs. ``jtask.rtl.first_strong_dir`` decides; this module
turns that decision into Qt layout-direction / alignment:

* :func:`content_direction` / :func:`content_alignment` — pure, widget-free.
* :func:`apply_content_direction` — orient a read-only ``QLabel`` (etc.).
* :func:`align_item` — orient a ``QListWidgetItem`` / ``QTreeWidgetItem``.
* :func:`bind_auto_direction` — track an *editable* field as the user types.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLineEdit

from jtask.rtl import first_strong_dir

__all__ = [
    "content_direction",
    "content_alignment",
    "apply_content_direction",
    "align_item",
    "bind_auto_direction",
]

_DIR = {
    "ltr": Qt.LayoutDirection.LeftToRight,
    "rtl": Qt.LayoutDirection.RightToLeft,
}
_HALIGN = {
    "ltr": Qt.AlignmentFlag.AlignLeft,
    "rtl": Qt.AlignmentFlag.AlignRight,
}


def _app_direction() -> Qt.LayoutDirection:
    app = QApplication.instance()
    return app.layoutDirection() if app is not None else Qt.LayoutDirection.LeftToRight


def content_direction(text: str) -> Qt.LayoutDirection:
    """Layout direction *text* should render in. Neutral / empty follows the app."""
    return _DIR.get(first_strong_dir(text)) or _app_direction()


def content_alignment(text: str) -> Qt.AlignmentFlag:
    """Horizontal alignment flag matching :func:`content_direction` (no vertical
    bit — combine with ``AlignVCenter`` / ``AlignTop`` at the call site)."""
    d = first_strong_dir(text)
    if d in _HALIGN:
        return _HALIGN[d]
    return (
        Qt.AlignmentFlag.AlignRight
        if _app_direction() == Qt.LayoutDirection.RightToLeft
        else Qt.AlignmentFlag.AlignLeft
    )


def apply_content_direction(widget, text: str) -> None:
    """Orient a read-only text widget (``QLabel``, ``QAbstractButton``) to the
    first-strong direction of *text*."""
    widget.setLayoutDirection(content_direction(text))
    if hasattr(widget, "setAlignment"):
        widget.setAlignment(content_alignment(text) | Qt.AlignmentFlag.AlignVCenter)


def align_item(item, text: str) -> None:
    """Set a view item's text alignment from the first-strong direction of *text*."""
    item.setTextAlignment(content_alignment(text) | Qt.AlignmentFlag.AlignVCenter)


def _apply(widget) -> None:
    if hasattr(widget, "toPlainText"):
        text = widget.toPlainText()
    else:
        text = widget.text()
    direction = _DIR.get(first_strong_dir(text)) or _app_direction()
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
