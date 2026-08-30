"""Shared exception type for jtask.

All user-facing failures raise :class:`JtaskError` with a Persian message; the
CLI catches it and renders an RTL panel instead of a Python traceback.
"""

from __future__ import annotations


class JtaskError(Exception):
    """A user-facing error carrying a Persian message."""


class TaskCommandError(JtaskError):
    """A ``task`` subprocess exited non-zero.

    Carries the pieces a UI needs to show the *real* failure: the command line,
    the exit code and stderr — never swallowed into a generic message.
    """

    def __init__(
        self, message: str, *, returncode: int, stderr: str, cmd: list[str]
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.cmd = cmd

    def details(self) -> str:
        """A copy-pasteable block: command, exit code, stderr."""
        return (
            f"$ {' '.join(self.cmd)}\n"
            f"exit code: {self.returncode}\n\n"
            f"{self.stderr or '(no stderr)'}"
        )
