"""Bug: an internal development-milestone label ("(به‌زودی در M8)") leaked
into a user-facing catalog string (``sync.not_configured.detail`` in
``fa.py``) — written while the Configuration Manager was still upcoming
(M7-era), never cleaned up once M8 actually shipped it.

A shipped feature should be referenced by name only ("مدیریت پیکربندی" /
"Configuration Manager"); an internal milestone/mission code (M5-M9, d1-d7,
i1-i6, n1-n3, N-A..N-E, gtd-*, bc-*, bs-*) must never be visible to the end
user, whether that milestone is done or still pending — the catalogs are the
one place this class of leak would surface, so this is a simple sweep over
every value in both, not a snapshot of the one instance found.
"""

from __future__ import annotations

import re

from jtask_gui.i18n import en as en_mod
from jtask_gui.i18n import fa as fa_mod

# Word-bounded so this doesn't fire on ordinary text that happens to contain
# the same letters+digit (e.g. "i18n", "column1") — \b requires a non-word
# character (or start/end of string) immediately around the match.
_MILESTONE_RE = re.compile(
    r"\b("
    r"M[1-9]"          # M1-M9
    r"|d[1-7]"         # d1-d7
    r"|i[1-6]"         # i1-i6 (design-system iN, not the i18n placeholder key)
    r"|n[1-3]"         # n1-n3
    r"|N-[A-E]"        # N-A .. N-E
    r"|gtd-[A-Za-z]"   # gtd-T, gtd-...
    r"|bc-[A-Za-z0-9]+"  # bc-1, bc-...
    r"|bs-[0-9]+"      # bs-1, bs-2
    r")\b"
)


def _leaks(catalog: dict[str, str]) -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in catalog.items()
        if _MILESTONE_RE.search(value)
    ]


def test_persian_catalog_has_no_milestone_code_leaks():
    leaks = _leaks(fa_mod.CATALOG)
    assert not leaks, f"internal milestone code(s) visible in fa.py: {leaks}"


def test_english_catalog_has_no_milestone_code_leaks():
    leaks = _leaks(en_mod.CATALOG)
    assert not leaks, f"internal milestone code(s) visible in en.py: {leaks}"
