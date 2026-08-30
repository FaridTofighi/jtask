"""Central UI string catalog — the single ``t(key, **kw)`` path for jtask-gui.

Why a catalog and not Qt's ``QTranslator`` / ``.ts`` / ``.qm``: the Phase-0
audit (``docs/i18n-phase0-audit.md``) found ~20 modules that build user-facing
label lists at *import time*, before any ``QApplication`` / translator exists —
``tr()`` and ``QCoreApplication.translate()`` both need the translator installed
first. A concept-keyed catalog resolved through ``t()`` sidesteps that, maps 1:1
to ``docs/i18n-glossary.md``, and matches the codebase's existing "one path"
pattern (``fmt.py`` for numbers, ``taskwarrior.py`` for TW access).

Catalogs are plain Python dict modules (``fa.py`` / ``en.py``) — flat dotted
keys, diff-reviewable, importable without a TOML/YAML parser or a
``requires-python`` bump.

Changing language requires an app restart (see the design doc); so it is fine
for module-level constants to call ``t()`` at import — a fresh process re-reads
them under the new language.
"""

from __future__ import annotations

import logging

log = logging.getLogger("jtask_gui.i18n")

LANGUAGES = ("fa", "en")
_DEFAULT = "fa"

_lang = _DEFAULT
_catalog: dict[str, str] = {}
_missing: set[str] = set()


def _load(lang: str) -> dict[str, str]:
    if lang == "en":
        from .en import CATALOG
    else:
        from .fa import CATALOG
    return dict(CATALOG)


def set_language(lang: str) -> None:
    """Load the catalog for *lang* (``"fa"`` / ``"en"``). Call once at startup."""
    global _lang, _catalog
    _lang = lang if lang in LANGUAGES else _DEFAULT
    _catalog = _load(_lang)
    _missing.clear()


def lang() -> str:
    if not _catalog:
        set_language(_DEFAULT)
    return _lang


def is_rtl() -> bool:
    """Layout direction follows *language* only, never the calendar system."""
    return lang() == "fa"


def t(key: str, /, **kw: object) -> str:
    """Look up *key*; ``str.format`` the result with *kw* when given.

    A missing key returns the key itself and is logged once — so a gap is
    visible in the UI and caught by ``tests/gui/test_i18n_snapshot.py`` rather
    than crashing.
    """
    if not _catalog:
        set_language(_DEFAULT)
    template = _catalog.get(key)
    if template is None:
        if key not in _missing:
            _missing.add(key)
            log.warning("missing i18n key: %s (lang=%s)", key, _lang)
        return key
    return template.format(**kw) if kw else template


def missing_keys() -> set[str]:
    """Keys that were requested but not found since the last ``set_language``."""
    return set(_missing)


def all_keys() -> set[str]:
    if not _catalog:
        set_language(_DEFAULT)
    return set(_catalog)
