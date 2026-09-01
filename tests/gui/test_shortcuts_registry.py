"""The shortcut registry is the single source of truth and stays conflict-free."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QKeySequence, QShortcut

from jtask_gui import shortcuts
from jtask_gui.i18n import t


def _norm(keys: str) -> str:
    s = QKeySequence(keys).toString()
    return "Return" if s == "Enter" else s  # keypad Enter ≡ Return


def test_no_key_sequence_is_bound_twice_for_different_actions():
    by_keys: dict[str, set[str]] = {}
    for sc in shortcuts.SHORTCUTS:
        by_keys.setdefault(_norm(sc.keys), set()).add(sc.desc_key)
    clashes = {k: v for k, v in by_keys.items() if len(v) > 1}
    assert not clashes, f"same keys, different actions: {clashes}"


def test_every_registry_entry_has_real_i18n_text():
    for sc in shortcuts.SHORTCUTS:
        assert t(sc.desc_key) != sc.desc_key
        assert t(sc.cat_key) != sc.cat_key


def test_by_category_covers_every_entry_in_order():
    grouped = shortcuts.by_category()
    assert [c for c, _ in grouped] == [
        c for c in shortcuts.CATEGORY_ORDER
        if any(s.cat_key == c for s in shortcuts.SHORTCUTS)
    ]
    assert sum(len(items) for _c, items in grouped) == len(shortcuts.SHORTCUTS)


@pytest.fixture
def win(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    return w


def test_every_live_qshortcut_is_documented(win):
    """Coverage + conflict guard the brief asked for: nothing is bound in the
    app that the cheat sheet doesn't list."""
    registered = {_norm(sc.keys) for sc in shortcuts.SHORTCUTS}
    live = {
        _norm(sc.key().toString())
        for sc in win.findChildren(QShortcut)
        if not sc.key().isEmpty()
    }
    # action shortcuts (undo, add-full) too
    for act in win.findChildren(type(win._undo_action)):
        if not act.shortcut().isEmpty():
            live.add(_norm(act.shortcut().toString()))
    undocumented = live - registered
    assert not undocumented, f"bound but not in shortcuts.SHORTCUTS: {undocumented}"
