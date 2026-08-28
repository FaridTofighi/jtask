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


def _lines(args: list[str]) -> list[str]:
    try:
        proc = run(args)
    except JtaskError:
        return []
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


@lru_cache(maxsize=1)
def _show_config() -> dict[str, str]:
    """Full ``task _show`` as a ``key=value`` dict."""
    out: dict[str, str] = {}
    for line in _lines(["_show"]):
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


@lru_cache(maxsize=1)
def uda_definitions() -> dict[str, dict[str, str]]:
    """Discovered UDAs as ``{name: {"type": ..., "label": ..., "values": ...}}``."""
    cfg = _show_config()
    udas: dict[str, dict[str, str]] = {}
    for key, value in cfg.items():
        if not key.startswith("uda."):
            continue
        rest = key[len("uda.") :]
        name, _, attr = rest.partition(".")
        if not attr:
            continue
        udas.setdefault(name, {})[attr] = value
    for name, spec in udas.items():
        spec.setdefault("type", "string")
        spec.setdefault("label", name)
    return udas


def date_uda_names() -> frozenset[str]:
    """Names of user-defined attributes whose type is ``date``."""
    return frozenset(n for n, s in uda_definitions().items() if s.get("type") == "date")


@lru_cache(maxsize=1)
def list_projects() -> list[str]:
    """All project names (pending via ``_projects`` plus any seen in export)."""
    projects = set(_lines(["_projects"]))
    try:
        for t in export(["status:completed"]):
            if t.get("project"):
                projects.add(t["project"])
    except JtaskError:
        pass
    return sorted(projects)


@lru_cache(maxsize=1)
def list_tags() -> list[str]:
    """User tag names, with Taskwarrior's virtual tags filtered out."""
    from .reports import VIRTUAL_TAGS

    return sorted(t for t in _lines(["_tags"]) if t not in VIRTUAL_TAGS)


@lru_cache(maxsize=1)
def list_contexts() -> list[str]:
    """Defined context names (empty when none are configured)."""
    names = []
    for line in _lines(["_context"]):
        if line and line != "none":
            names.append(line)
    return names


def current_context() -> str | None:
    lines = _lines(["_get", "rc.context"])
    return lines[0] if lines and lines[0] else None


@lru_cache(maxsize=1)
def list_reports() -> list[str]:
    """Names of report definitions (built-in + custom from .taskrc)."""
    return sorted(set(_lines(["_reports"])))


def refresh_lookups() -> None:
    """Drop all cached lookups (call after config or data changes)."""
    for fn in (
        _show_config, uda_definitions, list_projects, list_tags,
        list_contexts, list_reports,
    ):
        clear = getattr(fn, "cache_clear", None)
        if callable(clear):
            clear()
