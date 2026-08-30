"""i2 / Resolution 3 — the pre-i2 Persian theme names (``شب`` / ``روز``) that a
saved ``.conf`` may still hold must be *migrated* to the stable keys
(``dark`` / ``light``), not silently reset to the default.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def store(qapp):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    yield
    QSettings("jtask", "jtask-gui").clear()


def _seed_raw(value: str) -> None:
    """Write the theme key exactly as a pre-i2 build would have."""
    from PyQt6.QtCore import QSettings

    s = QSettings("jtask", "jtask-gui")
    s.setValue("theme", value)
    s.sync()


@pytest.mark.parametrize(
    "legacy, canonical",
    [("شب", "dark"), ("روز", "light")],
)
def test_legacy_theme_name_is_migrated_not_reset(store, legacy, canonical):
    from jtask_gui.settings import Settings

    _seed_raw(legacy)

    s = Settings()
    assert s.theme == canonical, "legacy name should map to the stable key"

    # and it must be *persisted* in the new form — a second load reads the key
    from PyQt6.QtCore import QSettings

    raw = QSettings("jtask", "jtask-gui").value("theme", None, str)
    assert raw == canonical, "the migration must be written back, once"

    assert Settings().theme == canonical


def test_unknown_theme_value_falls_back_to_default(store):
    from jtask_gui.settings import Settings

    _seed_raw("chartreuse")
    assert Settings().theme == "dark"  # DEFAULT_THEME


def test_canonical_names_pass_through_untouched(store):
    from jtask_gui.settings import Settings

    for name in ("dark", "light"):
        _seed_raw(name)
        assert Settings().theme == name


def test_theme_labels_come_from_the_catalog(qapp):
    from jtask_gui.i18n import set_language, t

    set_language("fa")
    assert t("theme.dark") == "شب"
    assert t("theme.light") == "روز"
