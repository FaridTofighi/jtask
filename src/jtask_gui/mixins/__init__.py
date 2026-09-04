"""``MainWindow`` mixins — cohesive slices of its behaviour, each split out of
``main_window.py`` into its own file (mission: MainWindow decomposition,
2026-09-05). See ``docs/jtask-gui-design.md`` for the full map of which
mixin owns which feature area, and for what deliberately stayed in
``MainWindow`` itself (construction/wiring, the write/refresh funnel, the
central data-flow methods) because it is genuinely the shell's own job.

Every mixin is a plain class (no Qt base) composed via multiple inheritance:
``class MainWindow(QMainWindow, TrayMixin, ThemeMixin, ...)``. Method bodies
moved unchanged — this refactor is behaviour-neutral by design.
"""

from __future__ import annotations
