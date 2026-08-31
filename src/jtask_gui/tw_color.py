"""Map a Taskwarrior colour string to a hex value for a sidebar swatch.

Taskwarrior colours are *named* (``red``, ``bright blue``, ``color5``,
``rgb520``, ``gray10`` …), not hex, so a curated set of named colours is offered
in the picker; the free-text field accepts anything and :func:`to_hex` does a
best-effort parse of the common forms for the swatch. An unparseable string
returns ``None`` (the row then shows no dot, but the value is still stored).
"""

from __future__ import annotations

# --- the 16 ANSI colours (xterm-ish) --------------------------------------
_ANSI16 = [
    "#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd",
    "#00cdcd", "#e5e5e5",  # 0-7  normal
    "#7f7f7f", "#ff5f5f", "#5fff5f", "#ffff5f", "#5f8fff", "#ff5fff",
    "#5fffff", "#ffffff",  # 8-15 bright
]
_BASE = {
    "black": 0, "red": 1, "green": 2, "yellow": 3, "blue": 4, "magenta": 5,
    "cyan": 6, "white": 7,
}

# --- curated picker palette (Taskwarrior colour name) -------------------
CURATED: list[str] = [
    "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright red", "bright green", "bright yellow", "bright blue",
    "bright magenta", "bright cyan", "gray10",
]


def _cube_hex(n: int) -> str:
    """xterm 256-colour cube / grayscale (indices 16-255) → hex."""
    if 16 <= n <= 231:
        n -= 16
        r, g, b = n // 36, (n // 6) % 6, n % 6
        vals = [0, 95, 135, 175, 215, 255]
        return f"#{vals[r]:02x}{vals[g]:02x}{vals[b]:02x}"
    if 232 <= n <= 255:
        v = 8 + (n - 232) * 10
        return f"#{v:02x}{v:02x}{v:02x}"
    if 0 <= n <= 15:
        return _ANSI16[n]
    return ""


def to_hex(tw_color: str) -> str | None:
    """Best-effort ``taskwarrior colour string`` → ``#rrggbb`` (or ``None``)."""
    if not tw_color:
        return None
    s = tw_color.strip().lower()
    # "<fg> on <bg>" — the swatch shows the foreground
    if " on " in s:
        s = s.split(" on ", 1)[0].strip()
    if not s or s in ("none", "default"):
        return None

    bright = False
    if s.startswith("bright "):
        bright, s = True, s[len("bright "):].strip()

    if s in _BASE:
        return _ANSI16[_BASE[s] + (8 if bright else 0)]

    if s.startswith("color") and s[5:].isdigit():
        return _cube_hex(int(s[5:])) or None

    if s.startswith("gray") and s[4:].isdigit():
        return _cube_hex(232 + min(23, int(s[4:]))) or None

    if s.startswith("rgb") and len(s) == 6 and s[3:].isdigit():
        r, g, b = (int(c) for c in s[3:])
        if max(r, g, b) <= 5:
            vals = [0, 95, 135, 175, 215, 255]
            return f"#{vals[r]:02x}{vals[g]:02x}{vals[b]:02x}"

    return None
