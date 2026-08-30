"""Resolution 4 gate: once the i18n catalog exists (i1), no *new* hard-coded
Persian string literal may appear in a jtask-gui widget/dialog file.

Enforcement is a per-file count **ceiling**, recorded in
``tests/_i18n_string_ceiling.json``. Every source line that contains a
Persian-letter string literal counts. The number may only go **down** (as i2–i6
finish the migration); a new raw string pushes a file over its ceiling and
fails this test.

Regenerate deliberately (only when a file's count legitimately dropped, or a
brand-new file was added and reviewed):

    JTASK_WRITE_CEILING=1 pytest tests/test_no_new_hardcoded_strings.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src" / "jtask_gui"
_CEILING = Path(__file__).parent / "_i18n_string_ceiling.json"

# a string literal (single or double quoted) that contains a Persian letter
_LITERAL = re.compile(r"""(['"])(?:(?!\1).)*[ؠ-يٹ-ۓ](?:(?!\1).)*\1""")


def _counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in sorted(_SRC.rglob("*.py")):
        if "i18n" in path.parts:
            continue  # the catalog modules are *meant* to hold Persian
        rel = str(path.relative_to(_ROOT))
        n = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if _LITERAL.search(line):
                n += 1
        if n:
            out[rel] = n
    return out


def test_no_new_hardcoded_persian_strings():
    current = _counts()

    if os.environ.get("JTASK_WRITE_CEILING") == "1":
        _CEILING.write_text(
            json.dumps(dict(sorted(current.items())), ensure_ascii=False, indent=1)
            + "\n",
            encoding="utf-8",
        )
        pytest.skip(f"ceiling written: {sum(current.values())} literals across "
                    f"{len(current)} files")

    assert _CEILING.exists(), "run once with JTASK_WRITE_CEILING=1"
    ceiling = json.loads(_CEILING.read_text(encoding="utf-8"))

    regressions = {
        f: (current[f], ceiling.get(f, 0))
        for f in current
        if current[f] > ceiling.get(f, 0)
    }
    assert not regressions, (
        "new hard-coded Persian string(s) — route them through i18n.t():\n"
        + "\n".join(f"  {f}: {cur} > ceiling {ceil}" for f, (cur, ceil) in regressions.items())
    )
