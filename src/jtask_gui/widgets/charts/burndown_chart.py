"""Burndown chart — pending / started / done over time (Taskwarrior semantics)."""

from __future__ import annotations

from .mpl_base import ThemedChart


class BurndownChart(ThemedChart):
    def draw_chart(self, ax, data, pal: dict) -> None:
        buckets = data["buckets"]
        labels = [self._axis_label(b["label"]) for b in buckets]
        x = range(len(buckets))
        pending = [b["pending"] for b in buckets]
        started = [b["started"] for b in buckets]
        done = [b["done"] for b in buckets]

        ax.bar(x, done, color=pal["completed"], label="انجام‌شده")
        ax.bar(x, started, bottom=done, color=pal["due_soon"], label="در حال انجام")
        ax.bar(x, pending, bottom=[d + s for d, s in zip(done, started, strict=True)],
               color=pal["primary"], label="باز")

        step = max(1, len(buckets) // 8)
        ax.set_xticks(list(x)[::step])
        ax.set_xticklabels(labels[::step], rotation=45, ha="left",
                           fontfamily=self._family, fontsize=8)
        ax.set_ylabel("تعداد کار", fontfamily=self._family, color=pal["text_muted"])
        ax.set_title("نمودار سوختن (Burndown)", fontfamily=self._family,
                     color=pal["text"], fontsize=13, pad=12)
        leg = ax.legend(loc="upper right", framealpha=0.0)
        for t in leg.get_texts():
            t.set_color(pal["text"])
            t.set_fontfamily(self._family)

    def _axis_label(self, raw: str) -> str:
        # daily "1403-07-10" -> "07-10" ; weekly "1403-w05" ; monthly "مهر 1403"
        parts = raw.split("-")
        if len(parts) == 3:
            return self._fa(f"{parts[1]}-{parts[2]}")
        return self._fa(raw)
