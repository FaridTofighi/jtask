"""Palette / QSS template stay in lockstep."""

import re

from jtask_gui import theme


def test_render_qss_has_no_unfilled_tokens():
    for name in theme.THEMES:
        rendered = theme.render_qss(name)
        assert "@" not in re.sub(r"/\*.*?\*/", "", rendered, flags=re.S)


def _tmpl_tokens() -> set[str]:
    body = re.sub(r"/\*.*?\*/", "", theme.template_text(), flags=re.S)
    return set(re.findall(r"@([a-z_]+)@", body))


def test_every_template_token_exists_in_every_palette():
    tokens = _tmpl_tokens()
    for name, pal in theme.THEMES.items():
        missing = tokens - set(pal)
        assert not missing, f"{name} missing {missing}"


# State colours are consumed by the Qt model rather than the QSS.
_MODEL_COLOURS = {"overdue", "due_soon", "waiting", "completed", "blocked"}


def test_state_colours_present_in_every_palette():
    for name, pal in theme.THEMES.items():
        assert _MODEL_COLOURS <= set(pal), f"{name} missing state colours"


def test_two_palettes_have_identical_key_sets():
    keys = [set(pal) for pal in theme.THEMES.values()]
    assert all(k == keys[0] for k in keys)
