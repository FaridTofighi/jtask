"""Theme-aware matplotlib canvas base for the report charts.

matplotlib is a low-level text renderer: it only shapes/bidi-reorders Persian
when built against **libraqm** (see ``mpl_text``).  So chart code must NOT touch
matplotlib's raw text API (``ax.set_title``/``set_xlabel``/``legend``/…)
directly — it goes through the ``*_fa`` wrappers below, which route every string
through :func:`mpl_text.fa`.  A grep test enforces this.

Every chart is a redraw-on-demand ``FigureCanvasQTAgg``; that model fits
Taskwarrior's report semantics and makes PNG export trivial.
"""

from __future__ import annotations

from importlib import resources

import matplotlib
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from ...i18n import t

matplotlib.use("QtAgg")
import matplotlib.font_manager as fm  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from ... import fmt  # noqa: E402
from ...theme import palette  # noqa: E402
from .mpl_text import fa  # noqa: E402

_FONTS_REGISTERED = False
_FONT_FAMILY = "Vazirmatn"


# --------------------------------------------------------------------------
# text wrappers — the ONLY way chart code is allowed to put text on an Axes
# --------------------------------------------------------------------------

def _tick_text(value, _pos=None) -> str:
    """Numeric axis tick → shared digit formatter (Persian/ASCII per mode)."""
    return fmt.num(int(value) if float(value).is_integer() else round(value, 1))


TICK_FORMATTER = FuncFormatter(_tick_text)


def category_tick_formatter(labels: list[str]) -> FuncFormatter:
    """A tick formatter for a categorical/text x-axis: index → reshaped label."""
    prepared = [fa(x) for x in labels]

    def fmt_(value, _pos=None):
        i = int(round(value))
        return prepared[i] if 0 <= i < len(prepared) else ""

    return FuncFormatter(fmt_)


def set_title_fa(ax, text, **kw):
    return ax.set_title(fa(text), **kw)


def set_xlabel_fa(ax, text, **kw):
    return ax.set_xlabel(fa(text), **kw)


def set_ylabel_fa(ax, text, **kw):
    return ax.set_ylabel(fa(text), **kw)


def set_xticklabels_fa(ax, labels, **kw):
    return ax.set_xticklabels([fa(x) for x in labels], **kw)


def legend_fa(ax, labels, **kw):
    return ax.legend([fa(x) for x in labels], **kw)


def text_fa(ax, x, y, text, **kw):
    return ax.text(x, y, fa(text), **kw)


def register_fonts() -> str:
    """Register the bundled Vazirmatn faces with matplotlib once."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return _FONT_FAMILY
    fonts_dir = resources.files("jtask_gui") / "resources/fonts"
    for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-Medium.ttf", "Vazirmatn-Bold.ttf"):
        try:
            with resources.as_file(fonts_dir / name) as p:
                fm.fontManager.addfont(str(p))
        except (FileNotFoundError, OSError):
            pass
    families = {f.name for f in fm.fontManager.ttflist}
    _FONTS_REGISTERED = True
    return _FONT_FAMILY if _FONT_FAMILY in families else "DejaVu Sans"


class ThemedChart(QWidget):
    """A titled matplotlib canvas that restyles itself for the active theme.

    Subclasses implement :meth:`draw_chart(ax, data, pal)` and put text on the
    axes only via the module-level ``*_fa`` helpers.
    """

    def __init__(self, theme_name: str = "شب", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._family = register_fonts()
        self._theme = theme_name
        self._data = None

        self._figure = Figure(figsize=(6, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

    # --- API -------------------------------------------------------

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self.redraw()

    def set_data(self, data) -> None:
        self._data = data
        self.redraw()

    def export_png(self, path: str) -> None:
        # savefig re-renders the same Figure object we display, so the text
        # pipeline is identical — nothing to re-prepare here.
        self._figure.savefig(path, dpi=150, facecolor=self._figure.get_facecolor())

    def redraw(self) -> None:
        pal = palette(self._theme)
        self._figure.clear()
        self._figure.set_facecolor(pal["bg"])
        ax = self._figure.add_subplot(111)
        self._style_axes(ax, pal)
        if not self._has_data():
            text_fa(ax, 0.5, 0.5, t("chart.no_data"),
                    ha="center", va="center", color=pal["text_muted"],
                    fontsize=13, fontfamily=self._family)
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            self.draw_chart(ax, self._data, pal)
            ax.yaxis.set_major_formatter(TICK_FORMATTER)
        for lbl in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            lbl.set_fontfamily(self._family)
            lbl.set_color(pal["text_muted"])
        self._canvas.draw_idle()

    # --- helpers for subclasses --------------------------------

    def _has_data(self) -> bool:
        data = self._data
        if not data:
            return False
        if isinstance(data, dict) and "buckets" in data:
            return bool(data["buckets"])
        return bool(data)

    def _style_axes(self, ax, pal: dict) -> None:
        ax.set_facecolor(pal["bg"])
        for spine in ax.spines.values():
            spine.set_color(pal["border"])
        ax.tick_params(colors=pal["text_muted"], labelsize=9)
        ax.grid(True, axis="y", color=pal["row_line"], linewidth=0.8, alpha=0.7)
        ax.set_axisbelow(True)
        ax.yaxis.set_major_formatter(TICK_FORMATTER)
        ax.xaxis.set_major_formatter(TICK_FORMATTER)
        for lbl in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            lbl.set_fontfamily(self._family)

    def draw_chart(self, ax, data, pal: dict) -> None:  # pragma: no cover - abstract
        raise NotImplementedError
