"""The raw command console must show plain text, not ANSI escape codes."""

from __future__ import annotations


def test_clean_output_drops_the_rc_override_noise():
    from jtask_gui.widgets.command_console import clean_output

    raw = (
        "TASKRC override: /home/x/.taskrc\n"
        "TASKDATA override: /home/x/.task\n"
        "Context 'sample' set. Use 'task context none' to remove.\n"
        "Configuration override rc.confirmation=off\n"
        "Configuration override rc.search.case.sensitive=no\n"
    )
    assert clean_output(raw) == "Context 'sample' set. Use 'task context none' to remove."
    # a genuine error on stderr is NOT noise — it stays
    assert clean_output("Configuration override rc.color=off\nNo matches.") == "No matches."
    # ANSI still stripped
    assert clean_output("\x1b[4mID\x1b[0m\n1 task") == "ID\n1 task"


def test_strip_ansi_removes_sgr_and_osc():
    from jtask_gui.widgets.command_console import strip_ansi

    raw = (
        "\x1b[4mName    \x1b[0m \x1b[4mType \x1b[0m \x1b[4mActive\x1b[0m\n"
        "personal read  no\n"
    )
    out = strip_ansi(raw)
    assert "\x1b" not in out
    assert out == "Name     Type  Active\npersonal read  no\n"
    # a hyperlink OSC sequence too
    assert strip_ansi("\x1b]8;;http://x\x07link\x1b]8;;\x07") == "link"


def test_console_output_is_stripped_before_display(qtbot, tw_env):
    from jtask import taskwarrior
    from jtask_gui.widgets.command_console import CommandConsole
    from jtask_gui.workers import wait_for_done

    taskwarrior.run(["context", "define", "work", "+work"])
    taskwarrior.refresh_lookups()

    con = CommandConsole()
    qtbot.addWidget(con)
    con._in.setText("context list")
    con._run()
    wait_for_done()
    for _ in range(6):
        qtbot.wait(20)

    shown = con._out.toPlainText()
    assert "\x1b" not in shown
    assert "[4m" not in shown          # the literal codes the user was seeing
    assert "work" in shown and "Definition" in shown


def test_console_is_a_dark_terminal_in_every_theme():
    """The Raw Command Console keeps a fixed dark surface (#2e3440) under both
    themes — like an IDE's integrated terminal."""
    import re

    from jtask_gui import theme

    for name, pal in theme.THEMES.items():
        assert pal["console_bg"].lower() == "#2e3440", name
        for key in ("console_fg", "console_border", "console_prompt"):
            assert key in pal, (name, key)

    qss = re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)
    for sel in ("QWidget#CommandConsole", "QPlainTextEdit#ConsoleOutput",
                "QLineEdit#ConsoleInput"):
        m = re.search(rf"{re.escape(sel)}\s*\{{([^}}]*)\}}", qss)
        assert m and "@console_bg@" in m.group(1), sel


def test_console_input_carries_its_object_name(qtbot):
    from jtask_gui.widgets.command_console import CommandConsole

    con = CommandConsole()
    qtbot.addWidget(con)
    assert con._in.objectName() == "ConsoleInput"   # so the QSS actually applies
    assert con._in.actions()                        # the ❯ prompt glyph


def test_mutating_commands_trigger_a_sync_signal_and_reads_do_not(qtbot):
    from jtask_gui.widgets.command_console import CommandConsole, _is_mutating

    assert _is_mutating(["context", "define", "work", "project:Work"])
    assert _is_mutating(["1", "modify", "priority:H"])
    assert _is_mutating(["config", "color.project.Work", "blue"])
    assert _is_mutating(["rc.context=work", "list"])
    assert not _is_mutating(["list"])
    assert not _is_mutating(["_get", "rc.context"])
    assert not _is_mutating(["diagnostics"])

    con = CommandConsole()
    qtbot.addWidget(con)
    fired = []
    con.stateChanged.connect(lambda: fired.append(True))

    con._mutating = True
    con._done("ok")
    assert fired == [True]
    con._mutating = False
    con._done("ID Age ...")
    assert fired == [True]          # a read command did not re-fire


def test_main_window_resyncs_after_a_console_context_define(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask import taskwarrior as tw
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()
    assert tw.list_contexts() == []

    w._console._in.setText("context define home project:Home")
    w._console._run()
    for _ in range(20):
        qapp.processEvents()
        wait_for_done(3000)
        qapp.processEvents()

    assert "home" in tw.list_contexts()
    rows = [w._sidebar._contexts.child(i).text(0)
            for i in range(w._sidebar._contexts.childCount())]
    assert any("home" in r for r in rows)          # sidebar updated on the fly


def test_one_shortcut_toggles_the_console_open_and_shut(qapp, qtbot, tw_env):
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

    keys = {s.toString() for s in w._console_action.shortcuts()}
    assert keys == {"Ctrl+`", "F12"}
    assert w._console_action.isCheckable()

    # one action — its shortcut both opens and closes the dock
    assert not w._console_dock.isVisibleTo(w)
    w._console_action.trigger()          # the shortcut
    qapp.processEvents()
    assert w._console_dock.isVisibleTo(w)
    assert w.settings.console_visible
    w._console_action.trigger()          # same shortcut again
    qapp.processEvents()
    assert not w._console_dock.isVisibleTo(w)
    assert not w.settings.console_visible
