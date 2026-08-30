"""English (en) UI string catalog.

i1: seeded from the Persian baseline so ``t()`` never returns a bare key while
the migration is in progress. Real English translations, drawn from
``docs/i18n-glossary.md``, replace these entries in milestone i5.
"""

from __future__ import annotations

from .fa import CATALOG as _FA

CATALOG: dict[str, str] = dict(_FA)

# i5 fills real translations here, e.g.:
#   CATALOG["btn.cancel"] = "Cancel"
