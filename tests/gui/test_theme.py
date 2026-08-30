"""Palette / QSS template stay in lockstep."""

import re

from jtask_gui import theme


def test_render_qss_has_no_unfilled_tokens():
    for name in theme.THEMES:
        rendered = theme.render_qss(name)
        assert "@" not in re.sub(r"/\*.*?\*/", "", rendered, flags=re.S)


def _tmpl_colour_tokens() -> set[str]:
    """Template placeholders that must resolve from the palette — i.e. every
    ``@name@`` that is not a dimension token from ``jtask_gui.tokens``."""
    from jtask_gui import tokens

    body = re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)
    all_tokens = set(re.findall(r"@([a-z0-9_]+)@", body))
    return all_tokens - set(tokens.qss_tokens())


def test_every_template_token_exists_in_every_palette():
    colour_tokens = _tmpl_colour_tokens()
    for name, pal in theme.THEMES.items():
        missing = colour_tokens - set(pal)
        assert not missing, f"{name} missing {missing}"


# State colours are consumed by the Qt model rather than the QSS.
_MODEL_COLOURS = {"overdue", "due_soon", "waiting", "completed", "blocked"}


def test_state_colours_present_in_every_palette():
    for name, pal in theme.THEMES.items():
        assert _MODEL_COLOURS <= set(pal), f"{name} missing state colours"


def test_two_palettes_have_identical_key_sets():
    keys = [set(pal) for pal in theme.THEMES.values()]
    assert all(k == keys[0] for k in keys)


def _luminance(hex_c: str) -> float:
    def chan(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_c.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_body_and_muted_text_meet_wcag_aa():
    for name, pal in theme.THEMES.items():
        assert _contrast(pal["text"], pal["bg"]) >= 4.5, name
        # secondary text: AA for large / UI text (>= 3:1), we aim higher
        assert _contrast(pal["text_muted"], pal["bg_alt"]) >= 4.0, name
        assert _contrast(pal["primary_fg"], pal["primary"]) >= 4.5, name


def test_state_colours_are_legible_on_background():
    for name, pal in theme.THEMES.items():
        for key in ("overdue", "due_soon"):
            assert _contrast(pal[key], pal["bg"]) >= 3.0, f"{name}:{key}"
