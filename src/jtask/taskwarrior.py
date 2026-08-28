"""Thin subprocess wrapper around the ``task`` binary.

Taskwarrior stays the single source of truth: jtask reads with ``task export``
and writes with ``task add`` / ``task <filter> <verb>``.  It never touches
Taskwarrior's data store directly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache

from .errors import JtaskError

__all__ = [
    "binary",
    "run",
    "export",
    "add",
    "command",
    "passthrough",
    "date_uda_names",
]

# rc overrides applied to every non-interactive call.  Hooks stay ON so the
# user's Taskwarrior hooks keep firing.
_RC = [
    "rc.confirmation=off",
    "rc.recurrence.confirmation=off",
    "rc.bulk=0",
    "rc.color=off",
    "rc.verbose=nothing",
    "rc.hooks=on",
]


def binary() -> str:
    """Absolute path to the ``task`` binary, or raise a Persian error."""
    override = os.environ.get("JTASK_TASK_BIN")
    found = override or shutil.which("task")
    if not found:
        raise JtaskError(
            "برنامهٔ Taskwarrior («task») روی سیستم پیدا نشد.\n"
            "برای نصب:  sudo apt install taskwarrior   یا   brew install task"
        )
    return found


def run(
    args: list[str],
    *,
    capture: bool = True,
    check: bool = True,
    extra_rc: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke ``task`` with the given *args* (rc overrides prepended)."""
    cmd = [binary(), *_RC, *(extra_rc or []), *args]
    proc = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise JtaskError(f"اجرای Taskwarrior ناموفق بود:\n{detail}")
    return proc


def export(filter_args: list[str] | None = None) -> list[dict]:
    """Return the tasks matching *filter_args* as a list of dicts.

    Taskwarrior requires the filter to precede the ``export`` command.
    """
    proc = run([*(filter_args or []), "export"])
    text = proc.stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JtaskError(f"خروجی JSON تسک‌وریر قابل خواندن نبود: {exc}") from exc
    return data


def add(args: list[str]) -> str:
    """Run ``task add`` and return its stdout (contains the new task id)."""
    proc = run(["add", *args], extra_rc=["rc.verbose=new-id"])
    return proc.stdout.strip()


def command(
    filter_args: list[str], verb: str, verb_args: list[str] | None = None
) -> str:
    """Run ``task <filter> <verb> <verb_args>`` and return stdout."""
    proc = run([*filter_args, verb, *(verb_args or [])])
    return proc.stdout.strip()


def passthrough(args: list[str]) -> int:
    """Run ``task`` transparently (inherit stdio) and return the exit code."""
    cmd = [binary(), *args]
    return subprocess.run(cmd, check=False).returncode


@lru_cache(maxsize=1)
def date_uda_names() -> frozenset[str]:
    """Names of user-defined attributes whose type is ``date``."""
    try:
        proc = run(["_show"])
    except JtaskError:
        return frozenset()
    names = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("uda.") and line.endswith(".type=date"):
            names.add(line[len("uda.") : -len(".type=date")])
    return frozenset(names)
