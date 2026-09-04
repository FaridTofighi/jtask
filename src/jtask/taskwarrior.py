"""Thin subprocess wrapper around the ``task`` binary.

Taskwarrior stays the single source of truth: jtask reads with ``task export``
and writes with ``task add`` / ``task <filter> <verb>``.  It never touches
Taskwarrior's data store directly.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from functools import lru_cache

from .errors import JtaskError, TaskCommandError

_log = logging.getLogger(__name__)

__all__ = [
    "binary",
    "run",
    "count",
    "export",
    "add",
    "command",
    "log",
    "duplicate",
    "purge",
    "undo_preview",
    "information",
    "stats",
    "export_text",
    "import_file",
    "sync_status",
    "synchronize",
    "hooks",
    "hooks_location",
    "hook_set_enabled",
    "tag_count",
    "rename_tag",
    "remove_tag",
    "project_task_count",
    "delete_project",
    "rename_project",
    "project_colors",
    "set_project_color",
    "clear_project_color",
    "config_names",
    "config_defaults",
    "config_set",
    "config_unset",
    "context_list",
    "context_define",
    "context_delete",
    "context_activate",
    "context_read_filter",
    "current_context",
    "uda_set",
    "uda_delete",
    "report_set",
    "version",
    "diagnostics",
    "calc",
    "command_reference",
    "passthrough",
    "date_uda_names",
]

# rc overrides applied to every non-interactive call.  Hooks stay ON so the
# user's Taskwarrior hooks keep firing.  NOTE: verbosity is *not* forced here —
# ``rc.verbose=nothing`` also silences Taskwarrior's error text ("No tasks
# specified.", "Task not found", …), which the GUI must be able to surface.
# Callers that only parse machine output (lookups, export) pass ``quiet=True``.
#
# ``rc.search.case.sensitive=no`` — a bare word / ``~`` pattern in a filter
# matches regardless of case (Taskwarrior's own default is ``yes``).  jtask's
# search field, and ``jtask <filter>``, are expected to be case-insensitive;
# an explicit case-sensitive match is still available via ``attr.is:`` etc.
_RC = [
    "rc.confirmation=off",
    "rc.recurrence.confirmation=off",
    "rc.bulk=0",
    "rc.color=off",
    "rc.hooks=on",
    "rc.search.case.sensitive=no",
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


@lru_cache(maxsize=1)
def context_read_filter() -> tuple[str, ...]:
    """The active context's ``read`` filter, tokenised — ``()`` when none.

    Taskwarrior's own ``task export`` command ignores the active context (unlike
    every report), so jtask applies the read filter itself on every read. The
    filter string (``context.<name>.read``) is split with :mod:`shlex` so quoted
    values survive.
    """
    name = current_context()
    if not name:
        return ()
    raw = _show_config().get(f"context.{name}.read", "").strip()
    if not raw:
        return ()
    try:
        return tuple(shlex.split(raw))
    except ValueError:
        return tuple(raw.split())


def _with_context(filter_args: list[str] | None, apply_context: bool) -> list[str]:
    base = list(filter_args or [])
    read = context_read_filter() if apply_context else ()
    if not read:
        return base
    return ["(", *read, ")", *base]


def export(
    filter_args: list[str] | None = None, *, apply_context: bool = True
) -> list[dict]:
    """Return the tasks matching *filter_args* as a list of dicts.

    Taskwarrior requires the filter to precede the ``export`` command. When a
    context is active its read filter is prepended unless *apply_context* is
    ``False`` (backups must stay complete regardless of context).
    """
    flt = _with_context(filter_args, apply_context)
    try:
        proc = run([*flt, "export"], quiet=True)
    except TaskCommandError:
        if flt == list(filter_args or []):
            raise
        _log.warning("context-scoped export failed; retrying without the context filter")
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


def export_text(
    filter_args: list[str] | None = None, *, array: bool = True, apply_context: bool = True
) -> str:
    """Raw ``task export`` JSON text — *array* toggles ``rc.json.array``.

    ``array=True`` → one indented JSON array (readable); ``array=False`` →
    newline-delimited JSON objects (the canonical ``task import`` shape).
    The active context's read filter is prepended unless *apply_context* is
    ``False`` (see :func:`export`).
    """
    rc = ["rc.json.array=on" if array else "rc.json.array=off"]
    flt = _with_context(filter_args, apply_context)
    return run([*flt, "export"], quiet=True, extra_rc=rc).stdout.strip()


_IMPORT_COUNT_RE = re.compile(r"Imported (\d+) tasks?")


def import_file(path: str) -> dict:
    """``task import <path>`` — returns ``{added, modified, total, stdout}``."""
    out = run(["import", path]).stdout
    added = len(re.findall(r"^\s*add\s+", out, re.MULTILINE))
    modified = len(re.findall(r"^\s*mod\s+", out, re.MULTILINE))
    m = _IMPORT_COUNT_RE.search(out)
    total = int(m.group(1)) if m else added + modified
    return {"added": added, "modified": modified, "total": total, "stdout": out.strip()}


_SYNC_KEYS = (
    ("rc.sync.server.url", "remote"),
    ("rc.sync.server.origin", "remote"),
    ("rc.sync.local.server_dir", "local"),
    ("rc.sync.local.server", "local"),
)


def sync_status() -> dict:
    """Whether Taskwarrior sync is configured, and where to.

    ``{"configured": bool, "kind": "remote"|"local"|None, "target": str}``.
    """
    for key, kind in _SYNC_KEYS:
        val = "".join(_lines(["_get", key])).strip()
        if val:
            return {"configured": True, "kind": kind, "target": val}
    return {"configured": False, "kind": None, "target": ""}


def synchronize() -> str:
    """``task sync`` — raises :class:`TaskCommandError` on failure."""
    return run(["synchronize"]).stdout.strip()


_HOOK_EVENTS = ("on-launch", "on-exit", "on-add", "on-modify")


def hooks_location() -> str:
    """Absolute path of Taskwarrior's hooks directory."""
    override = "".join(_lines(["_get", "rc.hooks.location"])).strip()
    if override:
        return os.path.expanduser(override)
    data = (
        "".join(_lines(["_get", "rc.data.location"])).strip()
        or os.environ.get("TASKDATA", "")
        or "~/.task"
    )
    return os.path.join(os.path.expanduser(data), "hooks")


def hooks() -> list[dict]:
    """Installed hook scripts.

    ``[{name, path, event, enabled}]`` — *enabled* is the executable bit
    (Taskwarrior only runs executable files in the hooks directory). Editing a
    hook's body stays a console / ``$EDITOR`` job; this is a read + enable/
    disable surface.
    """
    location = hooks_location()
    if not os.path.isdir(location):
        return []
    out: list[dict] = []
    for name in sorted(os.listdir(location)):
        path = os.path.join(location, name)
        if not os.path.isfile(path):
            continue
        event = next((e for e in _HOOK_EVENTS if name.startswith(e)), "")
        out.append(
            {
                "name": name,
                "path": path,
                "event": event,
                "enabled": os.access(path, os.X_OK),
            }
        )
    return out


def hook_set_enabled(path: str, enabled: bool) -> None:
    """Toggle a hook script's executable bit (u+x / u-x, keeping other bits)."""
    import stat

    mode = os.stat(path).st_mode
    if enabled:
        mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    else:
        mode &= ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.chmod(path, mode)


def command(
    filter_args: list[str], verb: str, verb_args: list[str] | None = None
) -> str:
    """Run ``task <filter> <verb> <verb_args>`` and return stdout."""
    proc = run([*filter_args, verb, *(verb_args or [])])
    return proc.stdout.strip()


def log(args: list[str]) -> str:
    """``task log <args>`` — create an already-completed task."""
    return run(["log", *args], extra_rc=["rc.verbose=new-id"]).stdout.strip()


_MODIFIED_RE = re.compile(r"Modif\w+ (\d+) task")


def tag_count(tag: str) -> int:
    """How many non-deleted tasks carry *tag* (a plain name, no leading ``+``)."""
    tag = tag.lstrip("+")
    for line in _lines(["status.not:deleted", f"+{tag}", "count"]):
        if line.strip().isdigit():
            return int(line.strip())
    return 0


def rename_tag(old: str, new: str) -> int:
    """Rename tag *old* → *new* on every non-deleted task. Returns the count."""
    old, new = old.lstrip("+"), new.lstrip("+")
    if not old or not new or old == new or tag_count(old) == 0:
        return 0
    out = command(
        ["status.not:deleted", f"+{old}"], "modify", [f"-{old}", f"+{new}"]
    )
    m = _MODIFIED_RE.search(out)
    return int(m.group(1)) if m else 0


def remove_tag(tag: str) -> int:
    """Strip *tag* from every non-deleted task. Returns the count."""
    tag = tag.lstrip("+")
    if not tag or tag_count(tag) == 0:
        return 0
    out = command(["status.not:deleted", f"+{tag}"], "modify", [f"-{tag}"])
    m = _MODIFIED_RE.search(out)
    return int(m.group(1)) if m else 0


# --- project management --------------------------------------------------
# Taskwarrior has no project entity — a project is an attribute. "The project
# and its sub-tasks" is every task in ``name`` or a dotted sub-project
# ``name.*``. A bare ``project:name`` filter is a *prefix* match (it would also
# catch ``Workshop`` for ``Work``), so the exact form below is used instead.

_DELETED_RE = re.compile(r"Deleted (\d+) task")


def _project_filter(name: str) -> list[str]:
    n = name.strip().rstrip(".")
    return ["status.not:deleted", "(", f"project.is:{n}", "or", f"project:{n}.", ")"]


def project_task_count(name: str) -> int:
    """Non-deleted tasks in project *name* or any sub-project ``name.*``."""
    if not name.strip():
        return 0
    for line in _lines([*_project_filter(name), "count"]):
        if line.strip().isdigit():
            return int(line.strip())
    return 0


def count(filter_args: list[str]) -> int:
    """``task <filter> count`` — matched tasks, 0 on any trouble."""
    for line in _lines([*filter_args, "count"]):
        if line.strip().isdigit():
            return int(line.strip())
    return 0


def delete_project(name: str) -> int:
    """Delete every non-deleted task in project *name* (+ sub-projects).

    A normal ``task delete`` — reversible with ``task undo``, not ``purge``.
    Returns the number of tasks deleted.
    """
    if project_task_count(name) == 0:
        return 0
    out = command(_project_filter(name), "delete")
    m = _DELETED_RE.search(out)
    return int(m.group(1)) if m else 0


def rename_project(old: str, new: str) -> int:
    """Move every non-deleted task from project *old* (+ sub-projects) to *new*,
    keeping the sub-structure: a task in ``old.Sub`` lands in ``new.Sub``.
    Returns the number of tasks moved.
    """
    old = old.strip().rstrip(".")
    new = new.strip().rstrip(".")
    if not old or not new or old == new:
        return 0
    moved = 0
    for task in export(_project_filter(old)):
        proj = task.get("project") or ""
        uuid = task.get("uuid")
        if not uuid:
            continue
        if proj == old:
            target = new
        elif proj.startswith(old + "."):
            target = new + proj[len(old):]
        else:
            continue
        command([uuid], "modify", [f"project:{target}"])
        moved += 1
    return moved


def project_colors() -> dict[str, str]:
    """``{project: <taskwarrior colour string>}`` from ``color.project.*``.

    jtask forces ``rc.color=off`` for its own reads, so these values only take
    effect because the GUI reads them here and renders a swatch — they still
    also apply in a raw ``task`` shell that has colour on.
    """
    out: dict[str, str] = {}
    for key, value in _show_config().items():
        if key.startswith("color.project.") and value:
            out[key[len("color.project.") :]] = value
    return out


def set_project_color(name: str, color: str) -> str:
    """``config color.project.<name> <color>`` — *color* is any Taskwarrior
    colour string (``blue`` / ``bright red`` / ``rgb520`` / …). Empty clears."""
    name = name.strip().rstrip(".")
    color = color.strip()
    if not name:
        return ""
    if not color:
        return clear_project_color(name)
    out = config_set(f"color.project.{name}", color)
    _show_config.cache_clear()
    return out


def clear_project_color(name: str) -> str:
    """Remove a project's colour override (``config color.project.<name>``)."""
    name = name.strip().rstrip(".")
    if not name:
        return ""
    out = config_unset(f"color.project.{name}")
    _show_config.cache_clear()
    return out


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
# Taskwarrior 3.x's undo preview names the count explicitly ("The following 2
# operations would be reverted:"). Older Taskwarrior (verified against the
# real 2.6.2 binary — see docs/taskwarrior-compatibility.md) never says this;
# it prints a bare Prior/Current Values diff table straight to the
# confirmation prompt, with nothing to count — undo_preview() falls back to
# count=1 for that shape (accurate too: pre-3.x `undo` only ever reverts one
# transaction per invocation).
_UNDO_COUNT_RE = re.compile(r"following (\d+) operations? would be reverted")
# "Nothing pending" wording is not version-stable either. 3.x: "No operations
# to undo." / "Could not undo: other operations have occurred." 2.6.2 (real
# output): "There are no recorded transactions to undo." Matched
# case-insensitively so small wording drift in some other in-between version
# doesn't silently fall back to count=1 for an undo that would do nothing.
_UNDO_EMPTY_RE = re.compile(
    r"no operations to undo"
    r"|no undo transactions"
    r"|no recorded transactions"
    r"|nothing to undo"
    r"|could not undo",
    re.IGNORECASE,
)


_PURGED_RE = re.compile(r"Purged (\d+) task")


def purge(filter_args: list[str]) -> int:
    """``task <filter> purge`` — permanently drop deleted tasks. Returns count.

    Only tasks already in the ``deleted`` state are removed; Taskwarrior itself
    refuses the rest, so the caller must scope *filter_args* to deleted UUIDs.
    """
    out = run([*filter_args, "purge"]).stdout
    m = _PURGED_RE.search(out)
    return int(m.group(1)) if m else 0


def _parse_undo_preview(out: str) -> dict:
    """Pure text-parsing half of :func:`undo_preview` — kept separate so both
    known output shapes (current Taskwarrior's explicit count, and older
    Taskwarrior's bare diff table) can be exercised directly in tests without
    a matching binary installed."""
    text = _UNDO_PROMPT_RE.sub("", out.strip()).strip()
    m = _UNDO_COUNT_RE.search(text)
    empty = not m and (not text or bool(_UNDO_EMPTY_RE.search(text)))
    count = int(m.group(1)) if m else (0 if empty else 1)
    return {"text": text, "count": count, "empty": empty}


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
    return _parse_undo_preview(proc.stdout or "")


def information(spec: str) -> str:
    """Raw ``task <spec> information`` text (id or uuid). Local-time rendered."""
    return run([spec, "information"], quiet=True).stdout


@lru_cache(maxsize=1)
def version() -> str:
    """Installed Taskwarrior version string, e.g. ``3.5.0`` (``""`` if unknown)."""
    try:
        out = run(["_version"], quiet=True).stdout.strip()
        return out or run(["--version"], check=False).stdout.strip()
    except JtaskError:
        return ""


def diagnostics() -> str:
    """Full ``task diagnostics`` text."""
    return run(["diagnostics"], quiet=True).stdout.strip()


def calc(expression: str) -> str:
    """``task calc <expression>`` — raises :class:`TaskCommandError` on a bad expr."""
    return run(["calc", expression], quiet=True).stdout.strip()


@lru_cache(maxsize=1)
def command_reference() -> list[tuple[str, str]]:
    """``[(invocation, description)]`` parsed from ``task help``."""
    out = run(["help"], quiet=True).stdout
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        m = re.match(r"^\s{2,}(task\s+\S.*?)\s{2,}(\S.*)$", line)
        if m:
            rows.append((m.group(1).strip(), m.group(2).strip()))
        elif rows and re.match(r"^\s{20,}\S", line):  # wrapped description
            prev_inv, prev_desc = rows[-1]
            rows[-1] = (prev_inv, f"{prev_desc} {line.strip()}")
    return rows


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


# --------------------------------------------------------------------------
# M8 — configuration surface.  Every write goes through ``task config``; jtask
# never edits ``.taskrc`` text.  ``config`` prompts for confirmation, so these
# always pass ``rc.confirmation=off`` explicitly (it is already in ``_RC``, but
# make the intent visible).
# --------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@lru_cache(maxsize=1)
def config_names() -> list[str]:
    """Every config variable Taskwarrior knows about (``task _config``)."""
    return sorted(_lines(["_config"]))


@lru_cache(maxsize=1)
def config_defaults() -> dict[str, str]:
    """``{name: default}`` for variables whose value differs from the default.

    Parsed from ``task show`` (no argument): a ``<name>  <value>`` row followed
    by a ``  Default value <default>`` row means *name* is overridden.
    """
    defaults: dict[str, str] = {}
    last_name: str | None = None
    for raw in _lines(["show"]):
        line = _ANSI_RE.sub("", raw)
        if line.startswith("Default value"):
            if last_name is not None:
                defaults[last_name] = line[len("Default value") :].strip()
            last_name = None
            continue
        m = re.match(r"^(\S+)\s{2,}(.*)$", line)
        if m and not line.startswith("Config Variable"):
            last_name = m.group(1)
        else:
            last_name = None
    return defaults


def config_set(name: str, value: str) -> str:
    """``task config <name> <value>`` (empty *value* removes the override)."""
    args = ["config", name] + ([value] if value != "" else [])
    return run(args).stdout.strip()


def config_unset(name: str) -> str:
    """Remove a config override. A no-op (not an error) if it isn't set."""
    proc = run(["config", name], check=False)
    if proc.returncode != 0 and "No entry named" not in (proc.stdout + proc.stderr):
        raise TaskCommandError(
            f"حذف «{name}» ناموفق بود (کد {proc.returncode}).",
            returncode=proc.returncode,
            stderr=(proc.stderr or proc.stdout or "").strip(),
            cmd=["task", "config", name],
        )
    return proc.stdout.strip()


def context_list() -> list[dict]:
    """``[{name, read, write, active}]`` from ``task context list``."""
    active = current_context() or ""
    rows: dict[str, dict] = {}
    order: list[str] = []
    cur: str | None = None
    for raw in _lines(["context", "list"]):
        line = _ANSI_RE.sub("", raw).strip()
        if line.startswith("Name") or set(line) <= {"-", " "} or not line:
            continue
        # continuation line: "write <filter> <yes|no>"
        m = re.match(r"^(read|write)\s+(.*?)\s+(yes|no)$", line)
        if m and cur:
            rows[cur][m.group(1)] = m.group(2).strip()
            continue
        # first line: "<name> <read|write> <filter> <yes|no>"
        m = re.match(r"^(\S+)\s+(read|write)\s+(.*?)\s+(yes|no)$", line)
        if m:
            cur = m.group(1)
            if cur not in rows:
                rows[cur] = {"name": cur, "read": "", "write": ""}
                order.append(cur)
            rows[cur][m.group(2)] = m.group(3).strip()
    for name, entry in rows.items():
        entry["active"] = name == active
        if not entry["write"]:
            entry["write"] = entry["read"]
    return [rows[n] for n in order]


def context_define(name: str, read: str, write: str = "") -> None:
    """Define / redefine a context. A single *read* filter is applied to both
    unless a distinct *write* is given."""
    run(["context", "define", name, read])
    if write and write != read:
        try:
            run(["context", "define", name, "write", write])
        except JtaskError:
            pass  # older Taskwarrior without separate read/write filters


def context_delete(name: str) -> str:
    return run(["context", "delete", name]).stdout.strip()


def context_activate(name: str | None) -> str:
    # ``task context none`` exits 2 ("Context not unset.") when none is active —
    # a no-op, not an error.
    proc = run(["context", name or "none"], check=bool(name))
    _show_config.cache_clear()
    context_read_filter.cache_clear()
    return proc.stdout.strip()


def uda_set(name: str, attr: str, value: str) -> str:
    return config_set(f"uda.{name}.{attr}", value)


def uda_delete(name: str) -> None:
    for key in list(_show_config()):
        if key == f"uda.{name}" or key.startswith(f"uda.{name}."):
            config_unset(key)


def report_set(name: str, attr: str, value: str) -> str:
    return config_set(f"report.{name}.{attr}", value)


BUILTIN_REPORTS = frozenset({
    "active", "all", "blocked", "blocking", "completed", "list", "long", "ls",
    "minimal", "newest", "next", "oldest", "overdue", "ready", "recurring",
    "unblocked", "waiting",
})


def refresh_lookups() -> None:
    """Drop all cached lookups (call after config or data changes)."""
    for fn in (
        _show_config, uda_definitions, list_projects, list_tags,
        list_contexts, list_reports, report_specs, config_names, config_defaults,
        version, command_reference, context_read_filter,
    ):
        clear = getattr(fn, "cache_clear", None)
        if callable(clear):
            clear()
