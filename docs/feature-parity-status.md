# jtask-gui — Full Taskwarrior Feature Parity: final status

**Mission:** bring jtask-gui to genuine *native* GUI coverage of Taskwarrior's
capabilities — not "parity via the raw console" — while keeping the Raw Command
Console permanently as the escape hatch and with zero regression to M1–M4.

**Baseline:** Taskwarrior 3.5.0 (libshared 14.2.0), Timewarrior not installed.

**Status: M5–M9 complete.**

| | tests | ruff | mypy |
|---|---|---|---|
| before the mission (end of M4) | 205 | clean | clean |
| after M9 | **334** | clean | clean |

Commits: `26e1c74` (M5+M6) · `ef8c519` (M7) · `473eb00` (M8) · M9 (this).

---

## What each milestone delivered

### M5 — task-lifecycle command parity + cross-cutting infrastructure
- **Real error surfacing** (`errors.TaskCommandError`, `widgets/error_dialog.py`):
  every failure shows the real `$ command`, exit code and stderr behind a
  disclosure, with copy + jump-to-console. `rc.verbose=nothing` removed from the
  shared overrides (it hid Taskwarrior's own error text); machine-output callers
  opt in with `run(..., quiet=True)`. Workers deliver the exception object.
- **GUI-enforced confirmation layer** (`widgets/confirm.py`): exact affected
  count, danger styling, type-the-word hard confirmation for `purge` — always
  present and identical regardless of the user's `rc.confirmation` / `rc.bulk`.
- **Visible async op-state** (`widgets/op_status.py`): idle / running / success /
  failed / cancelled in the status bar.
- **Verbs:** `undo` with a preview + count before applying (broad — every undo);
  `duplicate`, `append`, `prepend`, `purge` as context-menu actions;
  `delete` routed through the confirm layer.
- **`widgets/bulk_edit.py`:** priority / project / tag ± / due / scheduled /
  wait across a selection, emitting only touched fields.
- **`widgets/task_form.py`:** full Add Task dialog + Log completed task (one
  form), with validation; dates emitted Gregorian straight to `task add`/`log`.

### M6 — task insight
- **Core** (`jtask/history.py`, `jtask/timesheet.py`, TDD): parse
  `task <id> information` into attributes + a change log (every entry keeps the
  raw Taskwarrior line) + time-tracking sessions from `Start set` /
  `Start deleted (duration:…)` pairs. `jalali.from_local()` for the local
  timestamps that report emits.
- **Detail panel is now tabbed:** ویرایش / **تاریخچه** (Jalali/Persian change
  log, raw line on hover) / **دادهٔ خام** (stored JSON).
- **Statistics** («آمار») and **Timesheet** («برگهٔ زمان») added to the Reports
  rail — the timesheet is honestly labelled as a reconstruction and detects
  Timewarrior when present.
- **Status-bar timer indicator** with live elapsed time, click to stop.

### M7 — data safety
- **Core:** `export_text` (indented array ↔ JSON-lines), `import_file`
  (added/modified counts), `sync_status`, `synchronize`.
- **«داده» toolbar menu:** Export dialog (scope × format, Jalali-dated default,
  live count), Import dialog (shape detection + sample preview + same-UUID
  warning), Sync Manager (detects `rc.sync.*`, last-sync time persisted, no
  concurrent runs; unconfigured → points at the Config Manager).
- Export + Import are jtask's documented backup/restore path (round-trip tested).

### M8 — configuration surface
- **Core:** `config_names` / `config_defaults` (parses `task show`) /
  `config_set` / `config_unset`; `context_list` / `context_define` /
  `context_delete` / `context_activate`; `uda_set` / `uda_delete`; `report_set`.
  **Every write is a `task config` / `task context` call — `.taskrc` text is
  never touched.**
- **«مدیریت Taskwarrior» dialog** with four tabs: **Configuration Manager**
  (searchable, grouped, current / default / overridden, edit + reset),
  **Context Manager** (full CRUD + activate), **UDA Manager** (CRUD with
  type / values / default), **Reports Manager** (custom reports editable;
  overriding a built-in needs an explicit confirm).

### M9 — power tools + filter grammar + docs
- **Core:** `version`, `diagnostics`, `calc`, `command_reference`.
- **«تشخیص و ابزارها» dialog:** Diagnostics (copy + save), Command reference
  (searchable), Calculator (Jalali annotation for date results).
- **Status bar** shows the detected Taskwarrior version.
- **Filter builder** gained id/uuid, regex, and a virtual-tag picker.
- **`tests/test_date_grammar.py`** — a 39-case end-to-end sweep of the Jalali
  date grammar through `rewrite.rewrite_args`.

---

## Intentional non-features (documented, not gaps)

- **Backup / Restore** — Export (scope "all") + Import is the path; a dedicated
  button would be a thin alias.
- **`task edit`** — stays console-first (spawns `$EDITOR`); the detail panel +
  Raw Data tab cover the need.
- **`import-v2`** — the legacy `*.data` migration path, not a JSON importer.
- **`execute`, `news`, `colors`/`logo`** — console-only by design.
- **Structured undo of a past change** — `task undo` is last-transaction only.
- **Per-variable config source path** — Taskwarrior exposes only
  "overridden vs. default".
- **Historical time-tracking sessions as a first-class store** — reconstructed
  from the modification log; full session tracking is Timewarrior's job.
- A **structured boolean filter builder** (`and`/`or`/`xor` with nesting) — the
  builder's raw-extras box takes them verbatim.

## Smaller items — status

**Built in the 2026-08-31 verifiability + deferred-gaps mission:** `until` in
the bulk dialog · dedicated Annotations tab · bulk annotate · recurrence-
template browser · typed UDA rows in the filter builder · send-to-console from
the command reference · hook list / enable-disable editor · Settings
binary/`TASKDATA`/`TASKRC` overrides + column reset · collapsible task-table
group headers.

**Still deferred (low value, non-blocking):** single-cell inline table edit ·
back-dating a logged task's `end` · full in-app hook *body* editing (stays
`$EDITOR`/console) · cross-session persistence of collapsed-group state.

---

## The Raw Command Console

Stays **permanently**. It is the guaranteed path for: a future Taskwarrior
version's new commands, power-user filter syntax the builder doesn't model,
custom hooks/reports, and anything M5–M9 didn't grow a dedicated control for.
ANSI escapes in its output are stripped (`strip_ansi`).
