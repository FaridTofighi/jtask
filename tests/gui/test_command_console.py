"""The raw command console must show plain text, not ANSI escape codes."""

from __future__ import annotations


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
