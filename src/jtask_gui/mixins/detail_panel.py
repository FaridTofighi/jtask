"""Detail panel slide-in/out animation and show/hide.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

_DETAIL_WIDTH = 400


class DetailPanelMixin:
    def _detail_width(self) -> int:
        sizes = self._split.sizes()
        return sizes[1] if len(sizes) > 1 else 0

    def _apply_detail_width(self, width) -> None:
        width = int(width)
        total = max(self._split.width(), 1)
        self._split.setSizes([max(1, total - width), width])

    def _animate_detail(self, target: int) -> None:
        self._detail_anim.stop()
        self._detail_anim.setStartValue(self._detail_width())
        self._detail_anim.setEndValue(target)
        self._detail_anim.start()

    def _detail_anim_done(self) -> None:
        end = int(self._detail_anim.endValue() or 0)
        self._apply_detail_width(end)
        if end == 0:
            self._detail_host.setVisible(False)

    def _show_detail(self, task: dict) -> None:
        self._detail.load_task(task)
        self._annotations_view.load_task(task)
        self._history_view.load_task(task)
        self._raw_view.load_task(task)
        self._detail_host.setVisible(True)
        self._animate_detail(_DETAIL_WIDTH)

    def _hide_detail(self) -> None:
        self._animate_detail(0)

    def _escape_pressed(self) -> None:
        """Esc closes the edit panel when it is open (and nothing else has
        claimed the key)."""
        if self._detail_host.isVisible():
            self._hide_detail()

