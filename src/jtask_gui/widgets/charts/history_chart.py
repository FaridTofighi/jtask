"""History / Ghistory — tasks added / completed / deleted per Jalali period."""

from __future__ import annotations

from .mpl_base import ThemedChart


class HistoryChart(ThemedChart):
    """``mode`` is ``"ghistory"`` (stacked bars) or ``"history"`` (grouped bars)."""

    def __init__(self, theme_name: str = "شب", parent=None) -> None:
        super().__init__(theme_name, parent)
        self._mode = "ghistory"

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.redraw()

    def draw_chart(self, ax, data, pal: dict) -> None:
        buckets = data["buckets"]
        labels = [self._fa(b["label"].split("-")[-1] if "-" in b["label"] else b["label"])
                  for b in buckets]
        x = list(range(len(buckets)))
        added = [b["added"] for b in buckets]
        completed = [b["completed"] for b in buckets]
        deleted = [b["deleted"] for b in buckets]

        series = [
            ("افزوده", added, pal["primary"]),
            ("تکمیل‌شده", completed, pal["completed"]),
            ("حذف‌شده", deleted, pal["overdue"]),
        ]
        if self._mode == "history":
            width = 0.26
            for i, (name, values, colour) in enumerate(series):
                ax.bar([p + (i - 1) * width for p in x], values, width,
                       label=name, color=colour)
        else:  # ghistory: stacked
            bottom = [0] * len(buckets)
            for name, values, colour in series:
                ax.bar(x, values, bottom=bottom, label=name, color=colour)
                bottom = [b + v for b, v in zip(bottom, values, strict=True)]

        step = max(1, len(buckets) // 8)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step], rotation=45, ha="left",
                           fontfamily=self._family, fontsize=8)
        title = "گراف تاریخچه" if self._mode == "ghistory" else "تاریخچه"
        ax.set_title(title, fontfamily=self._family, color=pal["text"],
                     fontsize=13, pad=12)
        leg = ax.legend(loc="upper left", framealpha=0.0)
        for t in leg.get_texts():
            t.set_color(pal["text"])
            t.set_fontfamily(self._family)
