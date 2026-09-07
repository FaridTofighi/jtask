"""Systemic guard — the detail panel must stay a genuinely scrollable
container where **every** section (Description → dependency graph) is
reachable, no matter how many rows/widgets precede it.

This is the third time a layout change has hidden the panel's later
sections:
  1. M1  — a hidden second splitter pane reserved dead space.
  2. M3  — the dependency-graph empty state painted oversized on first paint.
  3. now — the unified Status control's button row had a large fixed minimum
           width, forcing the scroll body wider than the viewport; with the
           horizontal scrollbar off, later sections were pushed out of reach.

Root cause each time: a child widget whose *minimum size* the panel can't
honour. So this test loads a task with data in every section (annotations,
multiple UDAs, a dependency) in the worst-case status state (waiting = 4
action buttons) at a deliberately narrow panel width and asserts:
  - no child forces the scroll body wider than the panel (no horizontal
    overflow — the h-scrollbar is off, so overflow == unreachable content);
  - every section container has non-zero height;
  - scrolling to the bottom fully reveals the last section.
"""

from __future__ import annotations

import pytest

_NARROW = 360  # narrower than the real detail pane (~400) — stricter


@pytest.fixture
def panel(qtbot, tw_env, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui import i18n
    from jtask_gui.widgets.detail_panel import DetailPanel

    i18n.set_language("fa")
    tw.uda_set("assignee", "type", "string")
    tw.uda_set("assignee", "label", "مسئول")
    tw.uda_set("assignee", "values", "فرید,سارا,آرش,علی")
    tw.uda_set("effort", "type", "numeric")
    tw.uda_set("effort", "label", "تلاش")
    tw.add(["کار وابسته"])
    tw.add(["کار پُر", "assignee:سارا", "priority:H", "effort:3"])
    dep = tw.export(["description:کار وابسته"])[0]
    main = tw.export(["description:کار پُر"])[0]
    tw.command([main["uuid"]], "modify", [f"depends:{dep['id']}",
                                          "wait:2099-01-01", "due:2098-01-01"])
    tw.command([main["uuid"]], "annotate", ["یک یادداشت نسبتاً بلند برای پر کردن این بخش"])
    tw.refresh_lookups()

    p = DetailPanel()
    qtbot.addWidget(p)
    p.set_all_tasks([main, dep])
    p.resize(_NARROW, 620)
    p.show()
    for _ in range(10):
        qapp.processEvents()
    p.load_task(tw.export([main["uuid"]])[0])
    for _ in range(10):
        qapp.processEvents()
    return p


def _body(panel):
    return panel.widget()


def test_no_child_forces_horizontal_overflow(panel):
    body = _body(panel)
    # the body must fit the panel's width — a child with a bigger minimum
    # width is exactly what makes later sections unreachable
    assert body.minimumSizeHint().width() <= _NARROW, (
        f"detail body min width {body.minimumSizeHint().width()} > panel {_NARROW} "
        "— some child forces horizontal overflow"
    )
    assert panel.horizontalScrollBar().maximum() == 0, (
        "horizontal scrollbar has a range (content is wider than the viewport, "
        "and the h-scrollbar is disabled — so that content is unreachable)"
    )


def test_status_control_never_forces_a_wide_minimum(qapp):
    # regardless of state, the status row must be able to wrap, not dictate
    # the width — this is the specific regression
    from jtask_gui.widgets.status_control import StatusControl

    cases = [
        {"status": "pending"},
        {"status": "pending", "start": "20260101T000000Z"},
        {"status": "pending", "wait": "20990101T000000Z"},       # waiting: 4 buttons
        {"status": "pending", "wait": "20990101T000000Z", "start": "20260101T000000Z"},
        {"status": "completed"},
        {"status": "deleted"},
    ]
    sc = StatusControl()
    for task in cases:
        sc.set_task(task)
        assert sc.minimumSizeHint().width() <= 200, (
            f"StatusControl min width {sc.minimumSizeHint().width()} in state "
            f"{sc.state} — it can't wrap and will widen the panel"
        )


def test_every_section_has_height_and_the_last_is_reachable(panel):
    from jtask_gui.widgets.dep_graph import DependencyGraph

    body = _body(panel)
    sections = {
        "annotations": panel._ann_summary,
        "udas": panel._uda_wrap,
        "dep_graph": panel._dep_graph,
    }
    for name, w in sections.items():
        assert w.height() > 0, f"{name} section collapsed to zero height"
        assert w.mapTo(body, w.rect().topLeft()).y() + w.height() <= body.height() + 1, (
            f"{name} section extends past the scroll body — unreachable"
        )

    # the UDA fields actually rendered (not just the label)
    assert panel._uda_widgets, "UDA section shows its label but rendered no fields"
    assert "assignee" in panel._uda_widgets

    # scroll to the bottom — the last section must be fully on-screen
    bar = panel.verticalScrollBar()
    bar.setValue(bar.maximum())
    for _ in range(4):
        panel.parent() and None
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
    dg = panel._dep_graph
    assert isinstance(dg, DependencyGraph)
    shown = dg.visibleRegion().boundingRect().height()
    assert shown >= dg.height() - 2, (
        f"dependency graph only {shown}/{dg.height()} px visible at max scroll"
    )
