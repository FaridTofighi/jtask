"""Design tokens — the enforced spacing / type / radius / elevation scale.

Single source of truth for every non-colour visual constant. Two consumers:

* **QSS** reads them as ``@sp_N@`` / ``@fs_*@`` / ``@r_*@`` placeholders, filled by
  :func:`jtask_gui.theme.render_qss` alongside the colour tokens.
* **Python layout code** imports the integer constants directly for
  ``setContentsMargins`` / ``setSpacing`` / widget geometry.

No raw pixel padding / margin / font-size / border-radius value may appear in
the QSS outside this token set — enforced by
``tests/gui/test_qss_uses_tokens.py``. The Python call sites are converted in
milestone d2.

The spacing scale is a curated 2-px-based ladder. Four component paddings that
pre-dated it were snapped to it in d1 (7→8 and 9→8 px on buttons / inputs /
quick-add / table rows, 3→4 px on the badge, 5→4 px on the tooltip; scrollbar
radius 5→6 px). Every shift is ≤2 px and is listed in ``docs/design-system.md``.
"""

from __future__ import annotations

# --- spacing scale (px) -------------------------------------------------
# Token name carries the value: ``sp_8`` is 8 px. Curated ladder — a new raw
# value elsewhere (13, 17, 9 …) fails the guard test. Bare ``0`` needs no token.
SPACE: tuple[int, ...] = (2, 4, 6, 8, 10, 12, 14, 16, 20, 24)

SP_2, SP_4, SP_6, SP_8, SP_10, SP_12, SP_14, SP_16, SP_20, SP_24 = SPACE

# --- corner radius (px) ------------------------------------------------
RADIUS: dict[str, int] = {"sm": 6, "md": 8, "pill": 9, "lg": 12}
R_SM, R_MD, R_PILL, R_LG = RADIUS["sm"], RADIUS["md"], RADIUS["pill"], RADIUS["lg"]

# --- type scale (px) -------------------------------------------------
# Values reflect what actually renders today. The app.qss header comment
# claimed H2 = 17 but a later duplicate rule made every #H2 render at 13 px;
# the dead 17-px rule was removed in d1 with no visual change.
FONT_SIZE: dict[str, int] = {
    "h1": 22,     # page / wizard heading
    "title": 16,  # emphatic result line (calc)
    "lg": 15,     # quick-add field, empty-state message
    "body": 14,   # default body text
    "h2": 13,     # panel / dialog sub-heading, confirm body, dep-graph empty
    "xs": 12,     # section captions, muted text, table headers, chips, status
}
FONT_WEIGHT: dict[str, int] = {"regular": 400, "bold": 700}
FS_H1, FS_TITLE, FS_LG, FS_BODY, FS_H2, FS_XS = (
    FONT_SIZE["h1"], FONT_SIZE["title"], FONT_SIZE["lg"],
    FONT_SIZE["body"], FONT_SIZE["h2"], FONT_SIZE["xs"],
)

# --- elevation ------------------------------------------------------
# A raised surface (dialog, popover, menu, card) is set apart from the base
# background by the ``surface`` colour role + a 1-px ``border`` edge and — for
# free-floating overlays only — a soft drop shadow applied in Python via
# :func:`shadow` (QSS cannot render shadows).
SHADOW_BLUR = 24
SHADOW_Y = 4
SHADOW_ALPHA = 90  # 0-255 on black


def shadow(widget) -> None:
    """Attach the standard soft elevation shadow to a floating widget."""
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(SHADOW_BLUR)
    eff.setOffset(0, SHADOW_Y)
    eff.setColor(QColor(0, 0, 0, SHADOW_ALPHA))
    widget.setGraphicsEffect(eff)


def qss_tokens() -> dict[str, str]:
    """The ``name -> "Npx"`` map merged into the QSS colour substitution."""
    out: dict[str, str] = {f"sp_{px}": f"{px}px" for px in SPACE}
    for name, px in RADIUS.items():
        out[f"r_{name}"] = f"{px}px"
    for name, px in FONT_SIZE.items():
        out[f"fs_{name}"] = f"{px}px"
    return out
