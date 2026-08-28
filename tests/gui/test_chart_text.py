"""Persian text on matplotlib charts must go through the reshaping helper.

matplotlib only shapes Arabic script when built against libraqm; a raw Persian
string on a chart without it renders reversed and unjoined.  These tests lock in
the capability-aware helper and forbid chart code from touching matplotlib's raw
text API directly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_CHART_DIR = Path(__file__).parents[2] / "src" / "jtask_gui" / "widgets" / "charts"


# --- the helper ---------------------------------------------------

def test_fa_applies_digit_mode_and_is_idempotent_shape():
    from jtask.rtl import set_digit_mode
    from jtask_gui.widgets.charts import mpl_text

    set_digit_mode(True)
    assert mpl_text.fa("۱۴۰۳") == mpl_text.fa("1403")  # digit normalisation


def test_fa_reshapes_when_matplotlib_cannot(monkeypatch):
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display

    from jtask_gui.widgets.charts import mpl_text

    monkeypatch.setattr(mpl_text, "MPL_SHAPES_ARABIC", False)
    src = "نمودار سوختن (Burndown)"
    out = mpl_text.fa(src)
    assert out == get_display(mpl_text._reshaper.reshape(src))
    assert out != src                      # it actually changed
    assert out != get_display(reshape(get_display(reshape(src))))  # not double-processed


def test_fa_passes_through_when_matplotlib_shapes(monkeypatch):
    from jtask_gui.widgets.charts import mpl_text

    monkeypatch.setattr(mpl_text, "MPL_SHAPES_ARABIC", True)
    assert mpl_text.fa("نمودار سوختن") == "نمودار سوختن"


def test_mixed_script_string_handled(monkeypatch):
    from jtask_gui.widgets.charts import mpl_text

    monkeypatch.setattr(mpl_text, "MPL_SHAPES_ARABIC", False)
    out = mpl_text.fa("تاریخچه 1403-w05")
    assert "1403" in out or "۱۴۰۳" in out  # the Latin/number part survives


# --- structural enforcement (grep) -----------------------------

_FORBIDDEN = re.compile(
    r"\b(ax|self\._?ax|axes)\.(set_title|set_xlabel|set_ylabel|"
    r"set_xticklabels|set_yticklabels|legend|annotate)\s*\("
)
_RAW_TEXT = re.compile(r"\bax\.text\s*\(")


@pytest.mark.parametrize(
    "path", [p for p in _CHART_DIR.glob("*.py") if p.name not in {"mpl_base.py", "mpl_text.py"}]
)
def test_chart_module_uses_fa_wrappers_only(path):
    src = path.read_text(encoding="utf-8")
    bad = _FORBIDDEN.findall(src)
    assert not bad, (
        f"{path.name} calls matplotlib's raw text API {bad}; "
        f"use the *_fa wrappers from mpl_base instead"
    )
    assert not _RAW_TEXT.search(src), f"{path.name} calls ax.text() directly; use text_fa"


def test_mpl_base_exposes_the_wrappers():
    from jtask_gui.widgets.charts import mpl_base

    for name in ("set_title_fa", "set_xlabel_fa", "set_ylabel_fa",
                 "set_xticklabels_fa", "legend_fa", "text_fa"):
        assert hasattr(mpl_base, name)


# --- rendered output ------------------------------------------

def test_burndown_title_is_prepared_not_raw(qtbot, monkeypatch):
    from jtask_gui.widgets.charts import mpl_text
    from jtask_gui.widgets.charts.burndown_chart import BurndownChart

    monkeypatch.setattr(mpl_text, "MPL_SHAPES_ARABIC", False)
    chart = BurndownChart("شب")
    qtbot.addWidget(chart)
    chart.set_data({"period": "daily", "buckets": [
        {"label": "1403-07-01", "pending": 3, "started": 0, "done": 1},
        {"label": "1403-07-02", "pending": 2, "started": 1, "done": 2},
    ]})
    chart._canvas.draw()
    rendered = chart._figure.axes[0].get_title()
    assert rendered == mpl_text.fa("نمودار سوختن (Burndown)")
    assert rendered != "نمودار سوختن (Burndown)"  # would have shipped garbled


def test_history_legend_entries_are_prepared(qtbot, monkeypatch):
    from jtask_gui.widgets.charts import mpl_text
    from jtask_gui.widgets.charts.history_chart import HistoryChart

    monkeypatch.setattr(mpl_text, "MPL_SHAPES_ARABIC", False)
    chart = HistoryChart("شب")
    qtbot.addWidget(chart)
    chart.set_data({"period": "monthly", "buckets": [
        {"label": "مهر 1403", "added": 4, "completed": 2, "deleted": 0},
    ]})
    chart._canvas.draw()
    leg = chart._figure.axes[0].get_legend()
    texts = [t.get_text() for t in leg.get_texts()]
    assert texts == [mpl_text.fa(n) for n in ("افزوده", "تکمیل‌شده", "حذف‌شده")]
    assert "افزوده" not in texts  # raw form must not leak through


def test_png_export_uses_the_same_figure(qtbot, tmp_path, monkeypatch):
    from jtask_gui.widgets.charts import mpl_text
    from jtask_gui.widgets.charts.burndown_chart import BurndownChart

    monkeypatch.setattr(mpl_text, "MPL_SHAPES_ARABIC", False)
    chart = BurndownChart("روز")
    qtbot.addWidget(chart)
    chart.set_data({"period": "daily", "buckets": [
        {"label": "1403-07-01", "pending": 3, "started": 0, "done": 1},
    ]})
    chart._canvas.draw()
    title_on_screen = chart._figure.axes[0].get_title()
    out = tmp_path / "b.png"
    chart.export_png(str(out))
    # savefig renders the same Figure object -> title text is unchanged
    assert chart._figure.axes[0].get_title() == title_on_screen
    assert out.stat().st_size > 500
