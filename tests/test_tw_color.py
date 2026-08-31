"""``jtask_gui.tw_color.to_hex`` — best-effort Taskwarrior colour → hex."""

from __future__ import annotations

import pytest

from jtask_gui.tw_color import CURATED, to_hex


@pytest.mark.parametrize(
    ("tw", "expected"),
    [
        ("red", "#cd0000"),
        ("blue", "#0000ee"),
        ("bright blue", "#5f8fff"),
        ("bright green", "#5fff5f"),
        ("color5", "#cd00cd"),
        ("gray10", "#6c6c6c"),
        ("rgb520", "#ff8700"),
        ("white on red", "#e5e5e5"),  # swatch = foreground
        ("RED", "#cd0000"),  # case-insensitive
    ],
)
def test_to_hex_known_forms(tw, expected):
    assert to_hex(tw) == expected


@pytest.mark.parametrize("tw", ["", "   ", "none", "default", "nonsense", "rgb999"])
def test_to_hex_unparseable_is_none(tw):
    assert to_hex(tw) is None


def test_curated_palette_all_render():
    assert len(CURATED) == 14
    assert all(to_hex(name) is not None for name in CURATED)
