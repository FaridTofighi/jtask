"""The QSS template must express spacing / type / radius through design tokens.

``app.qss`` is a template with ``@sp_N@`` / ``@fs_*@`` / ``@r_*@`` placeholders
filled from :mod:`jtask_gui.tokens`. A raw pixel value in a
padding / margin / spacing / font-size / border-radius declaration means someone
bypassed the scale — this test fails so the next milestone (or a future feature)
can't quietly reintroduce magic numbers. Modelled on
``tests/gui/test_chart_text.py`` (grep-style enforcement).

``0``, ``1px`` and ``2px`` (border and hairline widths) are the only bare
lengths allowed in those declarations.
"""

from __future__ import annotations

import re

from jtask_gui import theme, tokens

# properties whose values must come from the spacing / type / radius scale
_SCALE_PROPS = (
    "padding", "padding-top", "padding-bottom", "padding-left", "padding-right",
    "margin", "margin-top", "margin-bottom", "margin-left", "margin-right",
    "spacing", "font-size", "border-radius",
    "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
)
_ALLOWED_BARE = {"0", "1px", "2px"}
_TOKEN = re.compile(r"^@[a-z0-9_]+@$")
_PX = re.compile(r"\d+px")


def _declarations(qss: str) -> list[tuple[str, str]]:
    qss = re.sub(r"/\*.*?\*/", "", qss, flags=re.S)
    out = []
    for decl in qss.split(";"):
        if ":" in decl:
            prop, _, value = decl.partition(":")
            out.append((prop.strip().split()[-1] if prop.strip() else "", value.strip()))
    return out


def test_scale_properties_use_only_tokens_or_hairlines():
    offenders = []
    for prop, value in _declarations(theme.template_text()):
        if prop not in _SCALE_PROPS:
            continue
        for part in value.split():
            if _TOKEN.match(part) or part in _ALLOWED_BARE:
                continue
            if _PX.search(part):
                offenders.append(f"{prop}: {value}")
                break
    assert not offenders, "raw pixel values in scale properties:\n  " + "\n  ".join(offenders)


def test_no_dead_duplicate_selector_rules():
    """No identical full selector defined twice (the dead 17px #H2 rule — a
    second bare ``QLabel#H2 { ... }`` block — was removed in d1). A later
    duplicate silently wins and the earlier declaration is dead code."""
    body = re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)
    selectors = [
        s.strip()
        for s in re.findall(r"([^{}]+)\{", body)
        if s.strip() and "@" not in s
    ]
    # comma-separated groups count as one rule each
    flat: list[str] = []
    for group in selectors:
        flat.extend(part.strip() for part in group.split(","))
    dupes = {s for s in flat if flat.count(s) > 1}
    assert not dupes, f"identical selector defined twice (earlier is dead): {dupes}"


def test_every_dimension_token_is_used():
    """No orphan tokens: everything tokens.qss_tokens() offers is referenced."""
    body = re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)
    used = set(re.findall(r"@([a-z0-9_]+)@", body))
    unused = set(tokens.qss_tokens()) - used
    assert not unused, f"declared but unused dimension tokens: {sorted(unused)}"


def test_rendered_dimension_values_are_on_scale():
    allowed = {v for v in tokens.qss_tokens().values()} | _ALLOWED_BARE
    for name in theme.THEMES:
        for prop, value in _declarations(theme.render_qss(name)):
            if prop not in _SCALE_PROPS:
                continue
            for part in value.split():
                if _PX.search(part):
                    assert part in allowed, f"{name}: {prop}: {part} off-scale"
