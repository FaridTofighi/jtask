"""d3 — dialog & form standards.

* A dialog sizes to its content: it never sets an oversized fixed / minimum
  height that reserves dead space (§2 — the audit's "empty space" was a
  screenshot-script artifact; this guard keeps it that way).
* A pristine, untouched form shows **no** validation error (§6.1).
* First-run uses the same label-beside-field form layout as Settings (§3).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGETS = Path(__file__).parents[2] / "src" / "jtask_gui" / "widgets"
_DIALOG_FILES = sorted(
    p for p in _WIDGETS.glob("*.py")
    if re.search(r"class \w+\(QDialog\)", p.read_text())
) + [_WIDGETS.parent / "settings_dialog.py"]


# --- §2: no dialog forces its own height ------------------------------

def test_no_dialog_forces_its_own_height():
    offenders = []
    for p in _DIALOG_FILES:
        for m in re.finditer(
            r"self\.(setFixedHeight|setMinimumHeight|setFixedSize|setMinimumSize)\(",
            p.read_text(),
        ):
            offenders.append(f"{p.name}: self.{m.group(1)}(...)")
    assert not offenders, (
        "dialogs must size to content, not a fixed/minimum height:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _mk("widgets.sync_dialog", "SyncManagerDialog", _settings()),
        lambda: _mk("settings_dialog", "SettingsDialog", _settings()),
        lambda: _mk("widgets.error_dialog", "ErrorDialog", "boom", "trace\nx"),
        lambda: _mk("widgets.confirm", "ConfirmDialog",
                    title="t", body="b", destructive=True, confirm_label="ok"),
    ],
    ids=["sync", "settings", "error", "confirm"],
)
def test_dialog_height_tracks_content(factory, qapp, qtbot, tw_env):
    dlg = factory()
    qtbot.addWidget(dlg)
    dlg.adjustSize()
    qapp.processEvents()
    hint = dlg.sizeHint().height()
    # a dialog may be a little taller than the hint (frame, button box) but not
    # by a large fixed margin of dead space
    assert dlg.height() <= hint + 40, (
        f"{type(dlg).__name__}: height {dlg.height()} >> content hint {hint}"
    )


# --- §6.1: no validation on a pristine form ---------------------------

def test_pristine_add_task_form_has_no_error(qapp, qtbot, tw_env):
    from jtask_gui.widgets.task_form import TaskFormDialog

    dlg = TaskFormDialog("add", [], [])
    qtbot.addWidget(dlg)
    qapp.processEvents()
    # isHidden() reflects the explicit show/hide state regardless of whether the
    # (never-shown) dialog is on screen
    assert dlg._hint.isHidden(), (
        "Add-Task shows a validation error before any interaction"
    )
    assert not dlg._ok.isEnabled()  # a disabled submit is the pristine signal
    # after a failed submit the hint appears
    dlg._try_accept()
    qapp.processEvents()
    assert not dlg._hint.isHidden()
    assert dlg._hint.text()


def test_no_form_validates_at_construction():
    """Grep guard: a `_revalidate()` / `_validate()` call in __init__ shows
    errors before the user has touched anything."""
    offenders = []
    for p in _WIDGETS.glob("*.py"):
        src = p.read_text()
        for m in re.finditer(r"def __init__.*?(?=\n    def |\Z)", src, re.S):
            body = m.group(0)
            if re.search(r"\bself\._(revalidate|validate)\(\)", body):
                offenders.append(p.name)
    assert not offenders, (
        f"forms validating in __init__ (premature errors): {offenders}"
    )


# --- §3: first-run form layout matches Settings ---------------------

def test_first_run_uses_form_layout_like_settings(qapp, qtbot):
    from PyQt6.QtWidgets import QFormLayout

    from jtask_gui.widgets.first_run import FirstRunWizard

    dlg = FirstRunWizard(_settings())
    qtbot.addWidget(dlg)
    assert dlg.findChild(QFormLayout) is not None, (
        "first-run wizard should use a QFormLayout (label beside field), "
        "like the Settings dialog"
    )


# --- helpers -------------------------------------------------------

def _settings():
    from PyQt6.QtCore import QSettings

    from jtask_gui.settings import Settings

    QSettings("jtask", "jtask-gui").clear()
    return Settings()


def _mk(mod: str, cls: str, *args, **kw):
    import importlib

    m = importlib.import_module(f"jtask_gui.{mod}")
    return getattr(m, cls)(*args, **kw)
