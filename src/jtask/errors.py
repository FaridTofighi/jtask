"""Shared exception type for jtask.

All user-facing failures raise :class:`JtaskError` with a Persian message; the
CLI catches it and renders an RTL panel instead of a Python traceback.
"""

from __future__ import annotations


class JtaskError(Exception):
    """A user-facing error carrying a Persian message."""
