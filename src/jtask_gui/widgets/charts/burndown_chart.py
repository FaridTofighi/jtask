"""Burndown chart — pending / started / done over time (Taskwarrior semantics)."""

from __future__ import annotations

from .mpl_base import (
    ThemedChart,
    legend_fa,
    set_title_fa,
    set_xticklabels_fa,
    set_ylabel_fa,
)

_SERIES = ("انجام‌شده", "در حال انجام", "باز")


class BurndownChart(ThemedChart):
    def draw_chart(self, ax, data, pal: dict) -> None:
        buckets = data["buckets"]
        labels = [_axis_label(b["label"]) for b in buckets]
        x = range(len(buckets))
        pending = [b["pending"] for b in buckets]
        started = [b["started"] for b in buckets]
        done = [b["done"] for b in buckets]

        ax.bar(x, done, color=pal["completed"])
        ax.bar(x, started, bottom=done, color=pal["due_soon"])
        ax.bar(x, pending, bottom=[d + s for d, s in zip(done, started, strict=True)],
               color=pal["primary"])

        step = max(1, len(buckets) // 8)
        ax.set_xticks(list(x)[::step])
        set_xticklabels_fa(ax, labels[::step], rotation=45, ha="left",
                           fontfamily=self._family, fontsize=8)
        set_ylabel_fa(ax, "تعداد کار", fontfamily=self._family, color=pal["text_muted"])
        set_title_fa(ax, "نمودار سوختن (Burndown)", fontfamily=self._family,
                     color=pal["text"], fontsize=13, pad=12)
        leg = legend_fa(ax, _SERIES, loc="upper right", framealpha=0.0)
        for t in leg.get_texts():
            t.set_color(pal["text"])
            t.set_fontfamily(self._family)


def _axis_label(raw: str) -> str:
    # daily "1403-07-10" -> "07-10" ; weekly "1403-w05" ; monthly "مهر 1403"
    parts = raw.split("-")
    return f"{parts[1]}-{parts[2]}" if len(parts) == 3 else raw
