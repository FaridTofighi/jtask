"""Feature: a `string`-type UDA that also has a `uda.<name>.values` list
configured renders as a **strict, non-editable** dropdown of those values —
not a free-text field.

Decision (strict vs editable): **strict**. Taskwarrior *enforces*
`uda.*.values` as a hard constraint — verified against both the real 2.6.2
and 3.5.0 binaries, `task add`/`modify` with an off-list value fails with
exit 2 ("The '<name>' attribute does not allow a value of '<x>'."). A
free-typed value would only ever error on save, so the picker is locked to
the list (plus a blank option, which clears the attribute — that *is*
allowed). Options appear in the order Taskwarrior reports them (config
order). See docs/taskwarrior-compatibility.md.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QComboBox, QLineEdit


@pytest.fixture
def udas(tw_env):
    from jtask import taskwarrior as tw

    tw.uda_set("assignee", "type", "string")
    tw.uda_set("assignee", "label", "مسئول")
    tw.uda_set("assignee", "values", "فرید,سارا,آرش,علی")
    tw.uda_set("notes", "type", "string")
    tw.uda_set("notes", "label", "یادداشت")   # no values -> stays free text
    tw.refresh_lookups()
    yield
    tw.refresh_lookups()


# --- core: the shared values-parsing helper ----------------------------

def test_uda_values_parses_in_config_order_trimmed(udas):
    from jtask import taskwarrior as tw

    assert tw.uda_values("assignee") == ["فرید", "سارا", "آرش", "علی"]
    assert tw.uda_values("notes") == []
    assert tw.uda_values("nonexistent") == []


# --- detail panel ----------------------------------------------------

def test_string_uda_with_values_renders_as_strict_combo(udas, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.detail_panel import DetailPanel

    tw.add(["کار الف", "assignee:سارا"])
    panel = DetailPanel()
    panel.load_task(tw.export()[0])

    w = panel._uda_widgets["assignee"]
    assert isinstance(w, QComboBox)
    assert w.isEditable() is False                       # strict
    assert [w.itemText(i) for i in range(w.count())] == \
        ["", "فرید", "سارا", "آرش", "علی"]               # blank + config order
    assert w.currentText() == "سارا"                      # reflects the task


def test_string_uda_without_values_stays_plain_text(udas, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.detail_panel import DetailPanel

    tw.add(["کار ب", "notes:چیزی"])
    panel = DetailPanel()
    panel.load_task(tw.export()[0])

    w = panel._uda_widgets["notes"]
    assert isinstance(w, QLineEdit)
    assert w.text() == "چیزی"


def test_changing_the_combo_emits_a_valid_mod(udas, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.detail_panel import DetailPanel

    tw.add(["کار ج", "assignee:سارا"])
    task = tw.export()[0]
    panel = DetailPanel()
    panel.load_task(task)

    seen: list = []
    panel.saveRequested.connect(lambda _u, mods: seen.extend(mods))
    panel._uda_widgets["assignee"].setCurrentText("آرش")
    panel._save()
    assert seen == ["assignee:آرش"]
    # and Taskwarrior actually accepts it (would raise on an off-list value)
    tw.command([task["uuid"]], "modify", seen)
    assert tw.export([task["uuid"]])[0]["assignee"] == "آرش"


def test_preexisting_off_list_value_is_kept_selectable(udas, qapp):
    """If the values list changed after a task was set (or a value was
    written straight through `task`), the strict combo must still show and
    round-trip that value rather than silently dropping it."""
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.detail_panel import DetailPanel

    tw.add(["کار د", "assignee:سارا"])
    task = tw.export()[0]
    tw.uda_set("assignee", "values", "فرید,آرش")   # "سارا" removed from the list
    tw.refresh_lookups()

    panel = DetailPanel()
    panel.load_task(tw.export([task["uuid"]])[0])
    w = panel._uda_widgets["assignee"]
    assert "سارا" in [w.itemText(i) for i in range(w.count())]
    assert w.currentText() == "سارا"


def test_priority_pseudo_uda_is_not_rendered_in_the_uda_section(udas, qapp):
    """Taskwarrior models `priority` as a UDA internally, so it comes back
    from uda_definitions(); the panel has a dedicated priority control and
    must not render it twice."""
    from jtask import taskwarrior as tw
    from jtask_gui.widgets.detail_panel import DetailPanel

    assert "priority" in tw.uda_definitions()             # TW really does report it
    tw.add(["کار ه"])
    panel = DetailPanel()
    panel.load_task(tw.export()[0])
    assert "priority" not in panel._uda_widgets


# --- filter builder: same source, same strict combo -----------------

def test_filter_builder_uses_the_same_values_and_a_strict_combo(udas, qapp):
    from jtask_gui.widgets.filter_builder import FilterBuilder

    dlg = FilterBuilder()
    row = next(r for r in dlg._uda_rows if r[0] == "assignee")
    editor = row[2]
    assert isinstance(editor, QComboBox)
    assert editor.isEditable() is False
    assert [editor.itemText(i) for i in range(editor.count())] == \
        ["", "فرید", "سارا", "آرش", "علی"]
