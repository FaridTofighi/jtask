"""Tests for config persistence and theme resolution."""

import pytest

from jtask import config, themes
from jtask.errors import JtaskError


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("JTASK_CONFIG_DIR", str(tmp_path / "cfg"))
    yield


def test_load_returns_defaults_when_no_file():
    cfg = config.load()
    assert cfg["theme"] == "شب"
    assert cfg["persian_digits"] is True


def test_set_and_reload_persists():
    config.set_value("theme", "روز")
    assert config.load()["theme"] == "روز"


def test_set_unknown_key_rejected():
    with pytest.raises(JtaskError):
        config.set_value("bogus", "x")


def test_set_invalid_date_format_rejected():
    with pytest.raises(JtaskError):
        config.set_value("date_format", "medium")


def test_first_run_flag():
    assert config.is_first_run() is True
    config.mark_first_run_done()
    assert config.is_first_run() is False


def test_builtin_themes_are_listed():
    names = themes.list_themes()
    assert "شب" in names and "روز" in names


def test_load_builtin_theme_fields():
    t = themes.load_theme("روز")
    assert t.name == "روز"
    assert t.color("overdue").startswith("#")
    assert t.box is not None


def test_load_missing_theme_raises():
    with pytest.raises(JtaskError):
        themes.load_theme("ناموجود")


def test_user_theme_overrides_builtin(tmp_path):
    d = config.user_themes_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "mine.yaml").write_text(
        "name: شب\ncolors:\n  primary: '#123456'\n", encoding="utf-8"
    )
    t = themes.load_theme("شب")
    assert t.color("primary") == "#123456"


def test_resolve_applies_cli_overrides():
    config.set_value("theme", "شب")
    t = themes.resolve(theme_override="روز", digits_override=False)
    assert t.name == "روز"
    assert t.persian_digits is False
