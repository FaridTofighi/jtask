"""Qt-free quick-add line parser.

Turns a natural line like::

    تماس با آرش فردا +تماس pri:H project:کار

into a structured preview and the Gregorian-rewritten argument list ready for
``jtask.taskwarrior.add``.  Date handling is delegated entirely to
``jtask.rewrite`` / ``jtask.jalali``.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

import jdatetime

from jtask import jalali, rewrite
from jtask.rewrite import DATE_ATTRS

from .i18n import t

_PRIORITY_ALIASES = {"pri": "priority"}
_PRIORITY_KEY = {"H": "quickadd.priority.h", "M": "quickadd.priority.m", "L": "quickadd.priority.l"}


@dataclass
class ParsedQuickAdd:
    description: str = ""
    project: str | None = None
    tags: list[str] = field(default_factory=list)
    remove_tags: list[str] = field(default_factory=list)
    priority: str | None = None
    dates: dict[str, str] = field(default_factory=dict)   # attr -> Jalali display
    other: dict[str, str] = field(default_factory=dict)   # any other key:value
    errors: list[str] = field(default_factory=list)
    raw_args: list[str] = field(default_factory=list)     # Gregorian, for `task add`
    _due_gregorian: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.description) and not self.errors


def parse_quick_add(text: str, today: jdatetime.date | None = None) -> ParsedQuickAdd:
    result = ParsedQuickAdd()
    text = text.strip()
    if not text:
        return result

    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    desc_parts: list[str] = []
    for tok in tokens:
        if tok.startswith("+") and len(tok) > 1:
            result.tags.append(tok[1:])
        elif tok.startswith("-") and len(tok) > 1 and ":" not in tok:
            result.remove_tags.append(tok[1:])
        elif ":" in tok and not tok.startswith("http"):
            key, _, value = tok.partition(":")
            key = _PRIORITY_ALIASES.get(key, key)
            if key == "project":
                result.project = value
            elif key == "priority":
                result.priority = value.upper()
            elif key in DATE_ATTRS:
                try:
                    result.dates[key] = _display_date(value, today)
                except jalali.JalaliError as exc:
                    result.errors.append(str(exc))
            else:
                result.other[key] = value
        else:
            desc_parts.append(tok)

    # detect a bare Persian relative-date expression inside the description
    # (e.g. "... فردا", "... ۳ روز دیگر") and lift it into due:
    bare_due_expr: str | None = None
    if "due" not in result.dates:
        rel = _extract_relative(desc_parts, today)
        if rel is not None:
            date_obj, used_idx, span = rel
            result.dates["due"] = jalali.to_persian_digits(date_obj.strftime("%Y-%m-%d"))
            result._due_gregorian = date_obj.togregorian().strftime("%Y-%m-%d")
            desc_parts = [w for i, w in enumerate(desc_parts) if i not in used_idx]
            bare_due_expr = span

    result.description = " ".join(desc_parts)

    # build the argument list for `task add` (dates still Persian here; the
    # single rewrite_args() call below converts every date token at once)
    add_tokens = list(desc_parts)
    if bare_due_expr:
        add_tokens.append(f"due:{bare_due_expr}")
    if result.project:
        add_tokens.append(f"project:{result.project}")
    if result.priority:
        add_tokens.append(f"priority:{result.priority}")
    for tag in result.tags:
        add_tokens.append(f"+{tag}")
    for key, value in result.other.items():
        add_tokens.append(f"{key}:{value}")
    for key in result.dates:
        # re-extract the original value for this attr
        for tok in tokens:
            if tok.startswith(f"{key}:") or tok.startswith(
                f"{_PRIORITY_ALIASES.get(key, key)}:"
            ):
                add_tokens.append(tok)
                break
    try:
        result.raw_args = rewrite.rewrite_args(add_tokens, today=today)
    except Exception as exc:  # noqa: BLE001 - surface as a soft error
        result.errors.append(str(exc))
        result.raw_args = add_tokens

    return result


def _display_date(value: str, today: jdatetime.date | None) -> str:
    resolved = jalali.resolve(value, today=today)
    return jalali.to_persian_digits(resolved.strftime("%Y-%m-%d"))


def _extract_relative(
    words: list[str], today: jdatetime.date | None
) -> tuple[jdatetime.date, set[int], str] | None:
    """Find the longest contiguous run of *words* that is a Persian relative date."""
    n = len(words)
    for size in (4, 3, 2, 1):
        for start in range(n - size + 1):
            span = " ".join(words[start : start + size])
            try:
                resolved = jalali.parse_relative(span, today=today)
            except jalali.JalaliError:
                resolved = None
            if resolved is not None:
                return resolved, set(range(start, start + size)), span
    return None


def preview_text(parsed: ParsedQuickAdd) -> str:
    """A short Persian one-liner describing what will be created."""
    if not parsed.description:
        return t("quickadd.prompt")
    bits = [f"«{parsed.description}»"]
    if parsed.project:
        bits.append(t("quickadd.preview.project", project=parsed.project))
    if parsed.tags:
        joined = " ".join(f"#{x}" for x in parsed.tags)
        bits.append(t("quickadd.preview.tags") + joined)
    if parsed.priority:
        pl = (
            t(_PRIORITY_KEY[parsed.priority])
            if parsed.priority in _PRIORITY_KEY
            else parsed.priority
        )
        bits.append(t("quickadd.preview.priority") + pl)
    for attr, shown in parsed.dates.items():
        label = {
            "due": t("quickadd.preview.due"),
            "scheduled": t("quickadd.preview.scheduled"),
            "wait": t("quickadd.preview.wait"),
        }.get(attr, attr)
        bits.append(f"{label}: {shown}")
    if parsed.errors:
        bits.append(
            t("quickadd.preview.error_prefix")
            + t("quickadd.preview.error_sep").join(parsed.errors)
        )
    return "  •  ".join(bits)
