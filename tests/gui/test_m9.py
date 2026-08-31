"""M9 — diagnostics / help / calc + filter builder extensions."""

from __future__ import annotations

import pytest


def _drain(qapp):
    from jtask_gui.workers import wait_for_done

    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()


@pytest.fixture(autouse=True)
def _warm_db(tw_env):
    """Initialise the fresh TaskChampion DB single-threaded before any test
    fires several concurrent ``task`` workers at it."""
    from jtask import taskwarrior

    taskwarrior.export()
    yield


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------


def test_taskwarrior_version_and_diagnostics(tw_env):
    from jtask import taskwarrior as tw

    assert tw.version()  # non-empty on this machine
    diag = tw.diagnostics()
    assert "task" in diag.lower()
    ref = tw.command_reference()
    assert any(inv.startswith("task") and "add" in inv for inv, _d in ref)


def test_taskwarrior_calc(tw_env):
    from jtask import taskwarrior as tw
    from jtask.errors import TaskCommandError

    assert tw.calc("3 * (4 + 2)") == "18"
    assert tw.calc("2 ^ 10") == "1024"
    with pytest.raises(TaskCommandError):
        tw.calc("(( bad")


# ---------------------------------------------------------------------------
# tools dialog
# ---------------------------------------------------------------------------


def test_tools_dialog_populates(qapp, tw_env):
    from jtask_gui.widgets.tools_dialog import ToolsDialog

    d = ToolsDialog()
    _drain(qapp)
    assert "task" in d.diagnostics._text.toPlainText().lower()
    assert d.help._table.rowCount() > 10

    d.help._search.setText("annotate")
    assert d.help._table.rowCount() >= 1
    assert all(
        "annotate" in d.help._table.item(r, 0).text().lower()
        or "annotate" in d.help._table.item(r, 1).text().lower()
        for r in range(d.help._table.rowCount())
    )


def test_calc_tab_computes_and_shows_jalali_for_dates(qapp, tw_env):
    from jtask_gui.widgets.tools_dialog import ToolsDialog

    d = ToolsDialog()
    d.calc._in.setText("40 + 2")
    d.calc._go()
    _drain(qapp)
    assert "= 42" in d.calc._out.text()

    d.calc._in.setText("now + 1d")
    d.calc._go()
    _drain(qapp)
    # ISO result annotated with a Jalali rendering (Persian digits)
    assert "۱۴" in d.calc._out.text()


def test_calc_tab_reports_errors(qapp, tw_env):
    from jtask_gui.widgets.tools_dialog import ToolsDialog

    d = ToolsDialog()
    d.calc._in.setText("(( nonsense")
    d.calc._go()
    _drain(qapp)
    assert "خطا" in d.calc._out.text()


# ---------------------------------------------------------------------------
# filter builder extensions
# ---------------------------------------------------------------------------


def test_filter_builder_virtual_tags_regex_ids(qapp, tw_env):
    from jtask_gui.widgets.filter_builder import FilterBuilder

    b = FilterBuilder()
    b._ids.setText("1-5")
    b._regex.setText("/فوری/")
    for btn in b._vtags:
        if btn.property("vtag") == "OVERDUE":
            btn.setChecked(True)

    tokens = b._raw_tokens()
    assert "1-5" in tokens
    assert "/فوری/" in tokens
    assert "+OVERDUE" in tokens


def test_filter_builder_typed_uda_rows(qapp, tw_env):
    from jtask import taskwarrior
    from jtask_gui.widgets.filter_builder import FilterBuilder

    taskwarrior.uda_set("effort", "type", "numeric")
    taskwarrior.uda_set("effort", "label", "Effort")
    taskwarrior.uda_set("size", "type", "string")
    taskwarrior.uda_set("size", "values", "S,M,L")
    taskwarrior.refresh_lookups()

    b = FilterBuilder()
    names = {n for n, *_ in b._uda_rows}
    assert {"effort", "size"} <= names

    for name, _utype, editor, op in b._uda_rows:
        if name == "effort":
            editor.setText("3")
            op.setCurrentIndex(op.findData("over"))
        elif name == "size":
            editor.setCurrentText("M")

    tokens = b._raw_tokens()
    assert "effort.over:3" in tokens
    assert "size:M" in tokens


def test_filter_builder_still_emits_gregorian_dates(qapp, tw_env):
    import jdatetime

    from jtask_gui.widgets.filter_builder import FilterBuilder

    b = FilterBuilder()
    b._due_before.set_value(jdatetime.date(1403, 7, 10))
    tokens = b._raw_tokens()
    assert any(t.startswith("due.before:2024-10-01") for t in tokens)


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------


def test_main_window_shows_version_and_opens_tools(win, qapp, monkeypatch):
    assert win._status_binary.text().startswith("Taskwarrior")

    calls = []

    class _FakeTools:
        sendToConsole = _NoSignal()

        def exec(self):
            calls.append(1)

    monkeypatch.setattr(
        "jtask_gui.widgets.tools_dialog.ToolsDialog", lambda *a, **k: _FakeTools()
    )
    win._open_tools()
    assert calls == [1]


class _NoSignal:
    def connect(self, *_a):
        pass


def test_help_send_to_console_reveals_and_prefills(win, qapp, qtbot):
    from jtask_gui.widgets.tools_dialog import ToolsDialog

    dlg = ToolsDialog(win)
    dlg.help._set([("task add <mods>", "Add a new task")])
    dlg.help._table.selectRow(0)
    dlg.sendToConsole.connect(win._send_to_console)

    with qtbot.waitSignal(dlg.sendToConsole, timeout=1000):
        dlg.help._emit_to_console()

    assert not win._console_dock.isHidden()
    assert win._console_action.isChecked()
    assert win._console._in.text() == "task add <mods>"


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
        wait_for_done(4000)
        qapp.processEvents()
    yield w
    wait_for_done(4000)
