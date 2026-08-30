"""i5 — the English catalog is complete, uses Taskwarrior's vocabulary, and the
Jalali transliteration + per-language digit default are in place.
"""

from __future__ import annotations

import re

import pytest

from jtask_gui import calendar_system as cs
from jtask_gui.i18n import en as en_mod
from jtask_gui.i18n import fa as fa_mod

_ARABIC = re.compile(r"[؀-ۿ]")

# Entries whose English value is *meant* to contain Persian text.
_ALLOW_PERSIAN = {
    "settings.language.fa",      # the language's endonym
    "settings.persian_digits",   # "Persian digits (۰-۹)" — digit sample
    "firstrun.digits",           # "Show Persian digits (۰–۹)"
}


def test_english_catalog_covers_every_key():
    missing = set(fa_mod.CATALOG) - set(en_mod.CATALOG)
    assert not missing, f"en.py missing keys: {sorted(missing)}"


def test_english_catalog_has_no_stray_persian():
    stray = {
        k: v
        for k, v in en_mod.CATALOG.items()
        if k not in _ALLOW_PERSIAN and _ARABIC.search(v)
    }
    assert not stray, f"English values still contain Persian: {stray}"


@pytest.mark.parametrize(
    "key,expected",
    [
        ("word.due", "Due"),
        ("word.scheduled", "Scheduled"),
        ("word.wait", "Wait"),
        ("word.until", "Until"),
        ("word.priority", "Priority"),
        ("word.project", "Project"),
        ("word.tags", "Tags"),
        ("word.dependencies", "Dependencies"),
        ("word.context", "Context"),
        ("status.pending", "Pending"),
        ("status.waiting", "Waiting"),
        ("status.completed", "Completed"),
        ("status.deleted", "Deleted"),
        ("status.recurring", "Recurring"),
        ("detail.urgency", "Urgency"),
        ("view.next", "Next Actions"),
        ("view.waiting", "Waiting For"),
    ],
)
def test_english_uses_taskwarrior_vocabulary(key, expected):
    assert en_mod.CATALOG[key] == expected


def test_priority_wording_is_consistent_each_language():
    for cat in (fa_mod.CATALOG, en_mod.CATALOG):
        for level in ("h", "m", "l"):
            vals = {
                cat[f"{prefix}priority.{level}"]
                for prefix in ("", "detail.", "fb.", "quickadd.", "col.")
            }
            assert len(vals) == 1, f"priority.{level} wording split: {vals}"
    assert en_mod.CATALOG["priority.h"] == "High"
    assert en_mod.CATALOG["priority.m"] == "Medium"
    assert en_mod.CATALOG["priority.l"] == "Low"


def test_wait_label_is_unified():
    for cat in (fa_mod.CATALOG, en_mod.CATALOG):
        vals = {cat[k] for k in ("detail.date.wait", "col.wait", "quickadd.preview.wait")}
        assert len(vals) == 1
    assert en_mod.CATALOG["col.wait"] == "Wait"
    assert fa_mod.CATALOG["col.wait"] == "تاریخ انتظار"


def test_jalali_transliteration_matches_glossary():
    assert cs.JALALI_MONTHS_LATIN == [
        "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
        "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand",
    ]
    assert cs.JALALI_WEEKDAYS_LATIN == [
        "Shanbeh", "Yekshanbeh", "Doshanbeh", "Seshanbeh",
        "Chaharshanbeh", "Panjshanbeh", "Jomeh",
    ]
    # never the Gregorian weekday names
    assert "Saturday" not in cs.JALALI_WEEKDAYS_LATIN


def test_digit_mode_default_follows_language(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("HOME", str(tmp_path))
    from PyQt6.QtCore import QSettings

    from jtask_gui.settings import Settings

    QSettings("jtask", "jtask-gui").clear()
    try:
        s = Settings()
        s.language = "en"
        assert s.persian_digits is False  # English → ASCII by default

        s.language = "fa"
        assert s.persian_digits is True   # Persian → Persian by default

        # an explicit override wins and survives a language switch
        s.digit_mode_user_overridden = True
        s.persian_digits = False
        s.language = "fa"
        assert s.persian_digits is False
    finally:
        QSettings("jtask", "jtask-gui").clear()
