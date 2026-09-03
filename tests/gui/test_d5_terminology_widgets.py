"""d5 — terminology + targeted widget fixes.

* priority H reads «بالا» / "High" everywhere (was «بحرانی» after i5 — "Critical"
  implies a 4th level Taskwarrior does not have).
* the Sync Manager's server path is bidi-isolated inside the RTL line (§8).
* dependency-graph node text is ellipsised, never spilling past the node
  border, with the full description on hover (§7).
"""

from __future__ import annotations

from jtask.rtl import _LRI, _PDI
from jtask_gui.i18n import en as en_cat
from jtask_gui.i18n import fa as fa_cat


def test_priority_high_wording():
    for prefix in ("", "detail.", "fb.", "quickadd.", "col."):
        assert fa_cat.CATALOG[f"{prefix}priority.h"] == "بالا"
        assert en_cat.CATALOG[f"{prefix}priority.h"] == "High"
    # and still internally consistent (one wording per language)
    for cat in (fa_cat.CATALOG, en_cat.CATALOG):
        for level in ("h", "m", "l"):
            vals = {
                cat[f"{p}priority.{level}"]
                for p in ("", "detail.", "fb.", "quickadd.", "col.")
            }
            assert len(vals) == 1


def test_no_critical_wording_anywhere():
    for cat in (fa_cat.CATALOG, en_cat.CATALOG):
        for k, v in cat.items():
            if "priority" in k:
                assert "بحرانی" not in v and "Critical" not in v, k


# «روزی» on its own reads as "sustenance" (رزق و روزی) in Persian, not "someday".
# The GTD Someday/Maybe concept is «یک‌روزی / شاید» everywhere (یک + ZWNJ + روزی).
_YEK_ROOZI = "یک‌روزی"


def test_someday_maybe_wording_is_yek_roozi():
    for key in ("board.gtd.someday", "review.step.someday"):
        assert fa_cat.CATALOG[key] == f"{_YEK_ROOZI} / شاید", key
        assert en_cat.CATALOG[key] == "Someday / Maybe", key
    # and the bare «روزی/شاید» form can't creep back into any fa value
    for k, v in fa_cat.CATALOG.items():
        if "شاید" in v:
            assert _YEK_ROOZI in v, k


def test_sync_path_is_bidi_isolated(qapp, qtbot, tw_env, monkeypatch):
    from jtask_gui.settings import Settings
    from jtask_gui.widgets import sync_dialog

    monkeypatch.setattr(
        sync_dialog.taskwarrior, "sync_status",
        lambda: {"configured": True, "kind": "local", "target": "/home/x/.task-sync/"},
    )
    dlg = sync_dialog.SyncManagerDialog(Settings())
    qtbot.addWidget(dlg)
    dlg._show_status(sync_dialog.taskwarrior.sync_status())
    text = dlg._detail.text()
    assert "/home/x/.task-sync/" in text
    assert _LRI in text and _PDI in text
    # the path itself sits between the isolates
    assert text.index(_LRI) < text.index("/home/x") < text.index(_PDI)


def test_dep_graph_text_is_elided_not_clipped(qapp, qtbot):
    from PyQt6.QtWidgets import QGraphicsSimpleTextItem

    from jtask_gui.widgets import dep_graph

    g = dep_graph.DependencyGraph("dark")
    qtbot.addWidget(g)
    mid = {"uuid": "m", "id": 2, "description": "Migrate the schema to v2 now",
           "status": "pending", "depends": ["u"]}
    up = {"uuid": "u", "id": 1, "description": "Provision the database cluster first",
          "status": "pending"}
    down = {"uuid": "d", "id": 3, "description": "Cut over production traffic carefully",
            "status": "pending", "depends": ["m"]}
    g.show_task(mid, [up, mid, down])

    texts = [
        it for it in g.scene().items() if isinstance(it, QGraphicsSimpleTextItem)
    ]
    # strip the bidi isolate controls the node text/tooltip are wrapped in
    def _bare(s: str) -> str:
        return s.translate({0x2066: None, 0x2067: None, 0x2068: None, 0x2069: None})

    assert texts
    for it in texts:
        # never wider than the node's inner box
        assert it.boundingRect().width() <= dep_graph._W - dep_graph._PAD
        assert it.toolTip()  # full description on hover
        if _bare(it.text()) != _bare(it.toolTip()):
            assert _bare(it.text()).endswith("…")
