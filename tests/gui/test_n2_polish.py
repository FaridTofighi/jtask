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


def test_toolbutton_has_a_focus_rule():
    assert re.search(r"QToolButton:focus\s*\{[^}]*@focus@", _qss())
