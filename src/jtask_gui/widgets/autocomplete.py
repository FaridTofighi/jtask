"""Shared token-aware completer for the quick-add and filter bars.

Both widgets build their completer from the *same* source
(``jtask.taskwarrior.list_projects`` / ``list_tags`` / ``uda_definitions``) —
there is no project/tag fetching logic anywhere else.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCompleter

# Taskwarrior attributes that commonly begin a filter/annotation token.
FILTER_ATTRS = [
    "project:", "priority:", "status:", "due:", "due.before:", "due.after:",
    "scheduled:", "wait:", "until:", "entry:", "end:", "urgency:", "recur:",
    "depends:", "limit:",
]


class _TokenCompleter(QCompleter):
    """Completes only the last whitespace-delimited token of the line."""

    def splitPath(self, path: str) -> list[str]:
        return [path.split()[-1] if path.split() else ""]

    def pathFromIndex(self, index) -> str:  # noqa: N802
        completed = super().pathFromIndex(index)
        text = self.widget().text() if self.widget() else ""
        parts = text.split()
        if parts:
            parts[-1] = completed
            return " ".join(parts) + (" " if text.endswith(" ") else "")
        return completed


def build_vocabulary(
    projects: list[str],
    tags: list[str],
    uda_names: list[str] | None = None,
    include_attrs: bool = True,
) -> list[str]:
    vocab: list[str] = []
    if include_attrs:
        vocab += FILTER_ATTRS
        vocab += [f"{u}:" for u in (uda_names or [])]
    vocab += [f"project:{p}" for p in projects]
    vocab += [f"+{t}" for t in tags]
    vocab += [f"-{t}" for t in tags]
    return vocab


def make_token_completer(
    projects: list[str],
    tags: list[str],
    uda_names: list[str] | None = None,
    include_attrs: bool = True,
) -> QCompleter:
    completer = _TokenCompleter(
        build_vocabulary(projects, tags, uda_names, include_attrs)
    )
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    return completer
