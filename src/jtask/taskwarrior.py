"""Thin subprocess wrapper around the ``task`` binary.

Taskwarrior stays the single source of truth: jtask reads with ``task export``
and writes with ``task add`` / ``task <filter> <verb>``.  It never touches
Taskwarrior's data store directly.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import lru_cache

from .errors import JtaskError, TaskCommandError

__all__ = [
    "binary",
    "run",
    "export",
    "add",
    "command",
    "log",
    "duplicate",
    "purge",
    "undo_preview",
    "information",
    "stats",
    "passthrough",
    "date_uda_names",
]

# rc overrides applied to every non-interactive call.  Hooks stay ON so the
# user's Taskwarrior hooks keep firing.  NOTE: verbosity is *not* forced here —
# ``rc.verbose=nothing`` also silences Taskwarrior's error text ("No tasks
# specified.", "Task not found", …), which the GUI must be able to surface.
# Callers that only parse machine output (lookups, export) pass ``quiet=True``.
_RC = [
    "rc.confirmation=off",
    "rc.recurrence.confirmation=off",
    "rc.bulk=0",
    "rc.color=off",
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
    quiet: bool = False,
    extra_rc: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke ``task`` with the given *args* (rc overrides prepended).

    *quiet* adds ``rc.verbose=nothing`` — use it only when the caller parses
    machine output and does not need Taskwarrior's human messages/errors.
    """
    verbose = ["rc.verbose=nothing"] if quiet else []
    cmd = [binary(), *_RC, *verbose, *(extra_rc or []), *args]
    proc = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise TaskCommandError(
            f"اجرای Taskwarrior ناموفق بود (کد {proc.returncode}).",
            returncode=proc.returncode,
            stderr=detail,
            # show the command without the noisy rc-override prefix
            cmd=["task", *args],
        )
    return proc


def export(filter_args: list[str] | None = None) -> list[dict]:
    """Return the tasks matching *filter_args* as a list of dicts.

    Taskwarrior requires the filter to precede the ``export`` command.
    """
    proc = run([*(filter_args or []), "export"], quiet=True)
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


def log(args: list[str]) -> str:
    """``task log <args>`` — create an already-completed task."""
    return run(["log", *args], extra_rc=["rc.verbose=new-id"]).stdout.strip()


def duplicate(filter_args: list[str], mods: list[str] | None = None) -> dict:
    """``task <filter> duplicate [mods]`` — return ``{stdout, id, uuid}``."""
    proc = run(
        [*filter_args, "duplicate", *(mods or [])],
        extra_rc=["rc.verbose=new-uuid"],
    )
    out = proc.stdout.strip()
    uuid = ""
    task_id = ""
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("Created task "):
            token = stripped[len("Created task ") :].rstrip(".")
            if "-" in token:
                uuid = token
            else:
                task_id = token
    return {"stdout": out, "id": task_id, "uuid": uuid}


_UNDO_PROMPT_RE = re.compile(
    r"\n*The undo command is not reversible\..*$", re.DOTALL
)
_UNDO_COUNT_RE = re.compile(r"following (\d+) operations? would be reverted")


_PURGED_RE = re.compile(r"Purged (\d+) task")


def purge(filter_args: list[str]) -> int:
    """``task <filter> purge`` — permanently drop deleted tasks. Returns count.

    Only tasks already in the ``deleted`` state are removed; Taskwarrior itself
    refuses the rest, so the caller must scope *filter_args* to deleted UUIDs.
    """
    out = run([*filter_args, "purge"]).stdout
    m = _PURGED_RE.search(out)
    return int(m.group(1)) if m else 0


def undo_preview() -> dict:
    """What ``task undo`` would revert, *without* applying anything.

    Runs with confirmation on and answers 'no', so state is untouched.
    Returns ``{"text": <preview>, "count": <int>, "empty": <bool>}``.
    """
    proc = subprocess.run(
        [binary(), *_RC, "rc.confirmation=on", "undo"],
        input="no\n",
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "").strip()
    text = _UNDO_PROMPT_RE.sub("", out).strip()
    m = _UNDO_COUNT_RE.search(text)
    empty = not m and (
        not text
        or "No operations to undo" in text
        or "No undo transactions" in text
        or "Nothing to undo" in text
        or "Could not undo" in text
    )
    count = int(m.group(1)) if m else (0 if empty else 1)
    return {"text": text, "count": count, "empty": empty}


def information(spec: str) -> str:
    """Raw ``task <spec> information`` text (id or uuid). Local-time rendered."""
    return run([spec, "information"], quiet=True).stdout


def stats(filter_args: list[str] | None = None) -> list[tuple[str, str]]:
    """``task <filter> stats`` as ordered ``(category, value)`` pairs."""
    out = run([*(filter_args or []), "stats"], quiet=True).stdout
    pairs: list[tuple[str, str]] = []
    started = False
    for line in out.splitlines():
        if re.match(r"^Category\s+Data\s*$", line):
            started = True
            continue
        if not started or not line.strip() or set(line.strip()) <= {"-", " "}:
            continue
        m = re.match(r"^(\S.*?)\s{2,}(.*)$", line)
        if m:
            pairs.append((m.group(1).strip(), m.group(2).strip()))
        else:
            pairs.append((line.strip(), ""))
    return pairs


def passthrough(args: list[str]) -> int:
    """Run ``task`` transparently (inherit stdio) and return the exit code."""
    cmd = [binary(), *args]
    return subprocess.run(cmd, check=False).returncode


def _lines(args: list[str]) -> list[str]:
    try:
        proc = run(args, quiet=True)
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
    names = set(_lines(["_reports"]))
    if not names:  # some builds return nothing for _reports
        names = {n for n, _ in report_specs().items()}
    return sorted(names)


@lru_cache(maxsize=1)
def report_specs() -> dict[str, dict[str, str]]:
    """``{name: {description, columns, labels, filter, sort}}`` from ``_show``."""
    specs: dict[str, dict[str, str]] = {}
    for key, value in _show_config().items():
        if not key.startswith("report."):
            continue
        _, name, attr = key.split(".", 2)
        specs.setdefault(name, {})[attr] = value
    return {n: s for n, s in specs.items() if "columns" in s}


def urgency_terms(uuid: str) -> list[dict[str, float | str]]:
    """Parsed contributing terms from ``task <uuid> info``.

    Each entry is ``{"label": str, "coefficient": float, "weight": float,
    "value": float}``; empty when Taskwarrior gives no breakdown.
    """
    try:
        proc = run([uuid, "info"], quiet=True)
    except JtaskError:
        return []
    terms: list[dict[str, float | str]] = []
    row = re.compile(r"^\s+(.+?)\s+(-?\d[\d.]*)\s+\*\s+(-?\d[\d.]*)\s+=\s+(-?\d[\d.]*)\s*$")
    for line in proc.stdout.splitlines():
        m = row.match(line)
        if m:
            terms.append({
                "label": m.group(1).strip(),
                "coefficient": float(m.group(2)),
                "weight": float(m.group(3)),
                "value": float(m.group(4)),
            })
    return terms


def refresh_lookups() -> None:
    """Drop all cached lookups (call after config or data changes)."""
    for fn in (
        _show_config, uda_definitions, list_projects, list_tags,
        list_contexts, list_reports, report_specs,
    ):
        clear = getattr(fn, "cache_clear", None)
        if callable(clear):
            clear()
