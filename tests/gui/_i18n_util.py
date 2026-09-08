"""Shared helpers for the i18n snapshot gate (Resolution 2).

``visible_strings(widget)`` walks a widget tree and returns every piece of
user-facing text it can see — window titles, labels, buttons, placeholders,
tooltips, table headers + cells, tree items, combo items, tab labels, menu
actions. The snapshot test renders a representative set of screens, collects
these, keeps the ones containing Persian, and asserts the sorted set is
byte-for-byte identical to a committed baseline.
"""

from __future__ import annotations

import re

from PyQt6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

_PLACEHOLDER_WIDGETS = (QLineEdit, QPlainTextEdit, QTextEdit)

_PERSIAN = re.compile(r"[؀-ۿ]")
_PERSIAN_LETTER = re.compile(r"[ء-يٹ-ۿ]")
_DIGITS = re.compile(r"[0-9۰-۹]+")


def has_persian(s: str) -> bool:
    return bool(_PERSIAN.search(s or ""))


def normalize_for_snapshot(s: str) -> str:
    """Mask data (digits, Jalali month/weekday names) so the snapshot captures
    *wording*, not rendered dates/counts. ``«۱۴۰۵-۰۶-۰۸ ۱۲:۲۳»`` → ``«#-#-# #:#»``,
    ``یک‌شنبه ۸ شهریور ۱۴۰۵`` → ``‹D› # ‹M› #``."""
    from jtask.jalali import MONTH_NAMES, WEEKDAY_NAMES

    out = s
    # absolute filesystem paths are machine-specific data, not wording
    out = re.sub(r"(?<![\w])[~/][\w./~-]{2,}", "‹path›", out)
    # longest first: "شنبه" (Saturday) is a substring of "یک‌شنبه", "دوشنبه", …
    for name in sorted(WEEKDAY_NAMES, key=len, reverse=True):
        out = out.replace(name, "‹D›")
    for name in sorted(MONTH_NAMES, key=len, reverse=True):
        out = out.replace(name, "‹M›")
    out = _DIGITS.sub("#", out)
    return out.strip()


def _tree_items(item: QTreeWidgetItem, out: list[str]) -> None:
    for c in range(item.columnCount()):
        out.append(item.text(c))
    for i in range(item.childCount()):
        _tree_items(item.child(i), out)


def visible_strings(root: QWidget) -> list[str]:
    out: list[str] = []
    if root.windowTitle():
        out.append(root.windowTitle())

    widgets = [root, *root.findChildren(QWidget)]
    for w in widgets:
        tt = w.toolTip()
        if tt:
            out.append(tt)
        if isinstance(w, (QLabel, QAbstractButton, QGroupBox)):
            if w.text():
                out.append(w.text())
        if isinstance(w, _PLACEHOLDER_WIDGETS) and w.placeholderText():
            out.append(w.placeholderText())
        if isinstance(w, QComboBox):
            out.extend(w.itemText(i) for i in range(w.count()))
        if isinstance(w, QListWidget):
            out.extend(w.item(i).text() for i in range(w.count()))
        if isinstance(w, QTabWidget):
            out.extend(w.tabText(i) for i in range(w.count()))
        if isinstance(w, QTableWidget):
            for c in range(w.columnCount()):
                h = w.horizontalHeaderItem(c)
                if h:
                    out.append(h.text())
            for r in range(w.rowCount()):
                for c in range(w.columnCount()):
                    it = w.item(r, c)
                    if it:
                        out.append(it.text())
        if isinstance(w, QTreeWidget):
            for c in range(w.columnCount()):
                out.append(w.headerItem().text(c))
            for i in range(w.topLevelItemCount()):
                _tree_items(w.topLevelItem(i), out)

    for m in root.findChildren(QMenu):
        for a in m.actions():
            if a.text():
                out.append(a.text())
            if a.toolTip() and a.toolTip() != a.text():
                out.append(a.toolTip())

    return out


def persian_snapshot(*roots: QWidget) -> list[str]:
    """Sorted set of normalized Persian *wording* strings across *roots*.

    Data-only strings (bare numbers, pure dates) are dropped — after masking,
    an entry must still contain a Persian letter to count as wording.
    """
    seen: set[str] = set()
    for r in roots:
        for s in visible_strings(r):
            if not has_persian(s):
                continue
            norm = normalize_for_snapshot(s)
            if _PERSIAN_LETTER.search(norm):
                seen.add(norm)
    return sorted(seen)
