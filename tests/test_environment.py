"""Environment sanity checks.

These exist so a drifted dev machine produces a clear, actionable message
pointing at ``docs/ENVIRONMENT.md`` instead of a confusing failure buried in a
parser assertion (or a silent difference in the shipped screenshots).
"""

from __future__ import annotations

import pytest

from jtask import taskwarrior

_MIN_TASKWARRIOR = (3, 5, 0)


def _parse_version(text: str) -> tuple[int, ...]:
    parts = text.strip().split(".")
    return tuple(int(p) for p in parts[:3] if p.isdigit())


def test_taskwarrior_version_is_supported():
    raw = taskwarrior.version()
    ver = _parse_version(raw)
    assert ver, f"could not parse Taskwarrior version from {raw!r}"
    if ver < _MIN_TASKWARRIOR:
        pytest.skip(
            f"Taskwarrior {raw} < {'.'.join(map(str, _MIN_TASKWARRIOR))}; "
            "the feature matrix and screenshots assume >= 3.5.0 — "
            "see docs/ENVIRONMENT.md. Core behaviour is expected to still work."
        )


def test_matplotlib_arabic_shaping_path_is_known():
    """Always passes — records which chart-text path this environment uses."""
    from jtask_gui.widgets.charts import mpl_text

    # Whichever path is active, fa() must return joined, non-empty output for a
    # Persian string (the no-libraqm path reshapes; the libraqm path defers to
    # matplotlib but still normalises digits).
    out = mpl_text.fa("نمودار سوختن")
    assert out and isinstance(out, str)
    if not mpl_text.MPL_SHAPES_ARABIC:
        # reshaped + bidi-reordered here; screenshots assume the other path
        assert out != "نمودار سوختن"


def test_not_both_qt_bindings_imported():
    """PyQt5 and PyQt6 loaded into one interpreter is an import-order hazard."""
    import sys

    if "PyQt6.QtCore" in sys.modules and "PyQt5.QtCore" in sys.modules:
        pytest.fail(
            "both PyQt5 and PyQt6 are imported in this process — "
            "see docs/ENVIRONMENT.md (PyQt6 only)"
        )
