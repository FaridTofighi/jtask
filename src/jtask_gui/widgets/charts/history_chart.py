"""History / Ghistory — tasks added / completed / deleted per Jalali period."""

from __future__ import annotations

from ...i18n import t
from .mpl_base import (
    ThemedChart,
    legend_fa,
    set_title_fa,
    set_xticklabels_fa,
)

_NAME_KEYS = ("chart.history.added", "chart.history.completed", "chart.history.deleted")


class HistoryChart(ThemedChart):
    """``mode`` is ``"ghistory"`` (stacked bars) or ``"history"`` (grouped bars)."""

    def __init__(self, theme_name: str = "dark", parent=None) -> None:
        super().__init__(theme_name, parent)
        self._mode = "ghistory"

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.redraw()

    def draw_chart(self, ax, data, pal: dict) -> None:
        buckets = data["buckets"]
        labels = [
            b["label"].split("-")[-1] if "-" in b["label"] else b["label"]
            for b in buckets
        ]
        x = list(range(len(buckets)))
        values = (
            [b["added"] for b in buckets],
            [b["completed"] for b in buckets],
            [b["deleted"] for b in buckets],
        )
        colours = (pal["primary"], pal["completed"], pal["overdue"])

        if self._mode == "history":
            width = 0.26
            for i, (vals, colour) in enumerate(zip(values, colours, strict=True)):
                ax.bar([p + (i - 1) * width for p in x], vals, width, color=colour)
        else:  # ghistory: stacked
            bottom = [0] * len(buckets)
            for vals, colour in zip(values, colours, strict=True):
                ax.bar(x, vals, bottom=bottom, color=colour)
                bottom = [b + v for b, v in zip(bottom, vals, strict=True)]

        step = max(1, len(buckets) // 8)
        ax.set_xticks(x[::step])
        set_xticklabels_fa(ax, labels[::step], rotation=45, ha="left",
                           fontfamily=self._family, fontsize=8)
        title = (
            t("chart.history.title_stacked")
            if self._mode == "ghistory"
            else t("chart.history.title_grouped")
        )
        set_title_fa(ax, title, fontfamily=self._family, color=pal["text"],
                     fontsize=13, pad=12)
        leg = legend_fa(ax, [t(k) for k in _NAME_KEYS], loc="upper left", framealpha=0.0)
        for txt in leg.get_texts():
            txt.set_color(pal["text"])
            txt.set_fontfamily(self._family)
