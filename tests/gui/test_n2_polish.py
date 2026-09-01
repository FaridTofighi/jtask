"""Mission n2 — density toggle, refined light palette, focus ring."""

from __future__ import annotations

import re

import pytest

from jtask_gui import theme


def _qss() -> str:
    return re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)


# --- density -----------------------------------------------------------

@pytest.fixture
def table(qtbot):
    from jtask_gui.models.task_model import TaskTableModel
    from jtask_gui.widgets.task_table import TaskTable

    m = TaskTableModel()
    m.set_tasks([{"id": i, "uuid": str(i), "description": f"t{i}", "status": "pending"}
                 for i in range(5)])
    tbl = TaskTable(m)
    qtbot.addWidget(tbl)
    return tbl


def test_density_changes_row_height(table):
    table.set_density("comfortable")
    tall = table.verticalHeader().defaultSectionSize()
    table.set_density("compact")
    short = table.verticalHeader().defaultSectionSize()
    assert short < tall
    # existing rows resize too, not just new ones
    assert table.rowHeight(0) == short


def test_density_setting_roundtrips(qapp):
    from PyQt6.QtCore import QSettings

    from jtask_gui.settings import Settings

    QSettings("jtask", "jtask-gui").clear()
    s = Settings()
    assert s.density == "comfortable"
    s.density = "compact"
    assert Settings().density == "compact"
    s.density = "nonsense"
    assert Settings().density == "comfortable"


def test_settings_dialog_is_scrollable_and_fits_the_screen(qapp):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QScrollArea

    from jtask_gui.settings import Settings
    from jtask_gui.settings_dialog import SettingsDialog

    QSettings("jtask", "jtask-gui").clear()
    d = SettingsDialog(Settings())
    assert d.findChild(QScrollArea) is not None          # content scrolls
    screen = QApplication.primaryScreen()
    if screen:
        assert d.height() <= screen.availableGeometry().height() * 0.85 + 1
    # the button box is NOT inside the scroll area (always visible)
    bb = d.findChild(QDialogButtonBox)
    assert not isinstance(bb.parent(), QScrollArea)
    assert d.findChild(QScrollArea).findChild(QDialogButtonBox) is None


def test_settings_dialog_exposes_density(qapp):
    from PyQt6.QtCore import QSettings

    from jtask_gui.settings import Settings
    from jtask_gui.settings_dialog import SettingsDialog

    QSettings("jtask", "jtask-gui").clear()
    d = SettingsDialog(Settings())
    assert d._density.count() == 2
    assert {d._density.itemData(i) for i in range(2)} == {"comfortable", "compact"}


# --- light palette / focus ------------------------------------------

def test_light_elevation_steps_are_real():
    """surface must sit clearly above bg / bg_alt — the old ladder was flat."""
    def _chan(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    def lum(h: str) -> float:
        r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)

    pal = theme.palette("light")
    assert lum(pal["surface"]) - lum(pal["bg"]) >= 0.06
    assert lum(pal["bg"]) - lum(pal["bg_alt"]) >= 0.005  # sidebar distinct


def _lum(h: str) -> float:
    def c(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def _cr(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_dark_theme_is_soft_not_near_black():
    """The window base is a charcoal, not pure black, and dividers are gentle
    against their surface (regions read by tone, not hard lines)."""
    pal = theme.palette("dark")
    assert _lum(pal["bg"]) >= 0.009          # lifted off #0e1014 (~0.005)
    assert _lum(pal["surface"]) - _lum(pal["bg"]) >= 0.008   # tonal separation
    assert _cr(pal["border"], pal["surface"]) <= 1.35        # soft border
    assert _cr(pal["row_line"], pal["surface"]) <= 1.2       # soft divider


def test_toolbutton_has_a_focus_rule():
    assert re.search(r"QToolButton:focus\s*\{[^}]*@focus@", _qss())


# --- priority dot --------------------------------------------------

def test_priority_column_shows_a_colour_dot():
    from PyQt6.QtCore import Qt

    from jtask_gui.models.task_model import TaskTableModel

    m = TaskTableModel()
    m.set_tasks([
        {"id": 1, "description": "a", "status": "pending", "priority": "H"},
        {"id": 2, "description": "b", "status": "pending", "priority": ""},
    ])
    col = m.visible_columns().index("priority")
    hi = m.data(m.index(0, col), Qt.ItemDataRole.DecorationRole)
    none = m.data(m.index(1, col), Qt.ItemDataRole.DecorationRole)
    assert hi is not None and not hi.isNull()
    assert none is None  # no dot when no priority
