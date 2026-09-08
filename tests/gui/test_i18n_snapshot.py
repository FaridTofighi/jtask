"""i1 acceptance gate (Resolution 2): the catalog migration must not change one
visible character in the default Persian configuration.

A baseline of every Persian string shown on the representative screens is
committed at ``tests/gui/_snapshots/fa_visible_strings.json``. This test
re-collects them and asserts an exact match. Regenerate deliberately with
``JTASK_WRITE_SNAPSHOT=1`` only when a *wording* change is intended and
reviewed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ._i18n_util import persian_snapshot

_SNAP = Path(__file__).parent / "_snapshots" / "fa_visible_strings.json"


def _build_screens(qapp, qtbot, wait_for_done):
    """Instantiate a representative slice of the UI and return the roots."""
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw

    tw.add(["نمونه برای عکس فوری", "project:آزمون", "priority:H", "due:2024-11-10"])
    tw.add(["کار دوم", "+مهم"])

    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings

    win = MainWindow(Settings())
    qtbot.addWidget(win)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    roots = [win]

    # detail panel loaded with a task
    task = tw.export(["project:آزمون"])[0]
    win._show_detail(task)
    for _ in range(4):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    from jtask_gui.settings_dialog import SettingsDialog
    from jtask_gui.widgets.bulk_edit import BulkEditDialog
    from jtask_gui.widgets.export_dialog import ExportDialog
    from jtask_gui.widgets.task_form import TaskFormDialog

    # SettingsDialog now hosts the Taskwarrior managers + tools that used to
    # live in the standalone ManagerDialog / ToolsDialog. Force every panel to
    # load so their populated wording is captured (they load lazily on reveal).
    sd = SettingsDialog(Settings())
    sd.show()
    for _i in range(sd._tw_stack.count()):
        sd._load_tw_panel(_i)
    roots.append(sd)
    roots.append(TaskFormDialog("add", ["آزمون"], ["مهم"]))
    roots.append(BulkEditDialog(3, ["آزمون"], ["مهم"]))
    roots.append(ExportDialog(["project:آزمون"]))
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    return roots


@pytest.fixture
def screens(qapp, qtbot, tw_env, monkeypatch):
    from jtask import timew
    from jtask_gui.workers import wait_for_done

    # TimesheetView's note wording branches live on whether the `timew`
    # binary is on PATH (jtask.timew.available() is a bare shutil.which()
    # call) — pin it so this wording gate tests catalog text, not which
    # machine happens to have Timewarrior installed. The baseline was
    # captured with it present; keep that branch deterministic here too.
    monkeypatch.setattr(timew, "available", lambda: True)

    roots = _build_screens(qapp, qtbot, wait_for_done)
    yield roots
    wait_for_done(4000)


def test_persian_visible_strings_unchanged(screens):
    current = persian_snapshot(*screens)

    if os.environ.get("JTASK_WRITE_SNAPSHOT") == "1":
        _SNAP.parent.mkdir(exist_ok=True)
        _SNAP.write_text(
            json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        pytest.skip(f"snapshot written: {len(current)} strings")

    assert _SNAP.exists(), "run once with JTASK_WRITE_SNAPSHOT=1 to capture the baseline"
    baseline = json.loads(_SNAP.read_text(encoding="utf-8"))

    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    assert not added and not removed, (
        f"visible Persian text changed.\n  ADDED ({len(added)}): {added[:20]}\n"
        f"  REMOVED ({len(removed)}): {removed[:20]}"
    )
