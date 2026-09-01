# Taskwarrior version compatibility

**Baseline / assumed version: Taskwarrior 3.5.0** (the version installed on the
development machine; `task diagnostics` reports libshared 14.2.0).

Rules (from the mission's cross-cutting requirements):

- The GUI **never hard-codes** a specific version's behaviour. It reads real
  values (`task _get`, `task show`, `task _config`, `task _columns`,
  `task _commands`, `task diagnostics`) and adapts.
- `task --version` is detected at startup, shown in the status area and in the
  Diagnostics view.
- A feature that needs a capability the installed `task` lacks shows
  **"در این نسخهٔ Taskwarrior پشتیبانی نمی‌شود"** instead of firing a command
  that would error.

## Capability probes the GUI performs

| Capability | Probe | Fallback if absent |
|---|---|---|
| command exists | `X in task _commands` | hide/disable the feature's entry, note "unsupported" |
| `import-v2` | `import-v2 in _commands` | fall back to `import` |
| `timesheet` report | `timesheet in _commands` | build from modification-log parse anyway |
| sync configured | `task _get rc.sync.server.url` / `rc.sync.local.server` non-empty; `task diagnostics` sync section | Sync Manager shows "sync not configured", links to Config Manager |
| Timewarrior | `shutil.which("timew")` | Timesheet uses the Taskwarrior-only source |
| a `rc.*` var | `task _get rc.<name>` (empty string vs. missing) | treat missing as "default" |
| a column/attribute | `X in task _columns` | omit from column pickers |
| context read/write filters | `task _get rc.context.<name>.read` / `.write` (3.4+) or `rc.context.<name>` (older) | use whichever is present |

## Known version-specific behaviour (3.5.0)

- `task <id> information` includes the `Date | Modification` change log — used by
  the History tab and the Timesheet. If a future/older version drops or reshapes
  it, the History tab degrades to the `entry/modified/end` anchors only and says
  so.
- `task show <var>` emits a `Default value …` line for overridden settings and a
  trailing "variables differ from the default values" notice — used by the
  Configuration Manager to populate the *default* column. If absent, the default
  column shows "—".
- `task context list` and `task _get rc.context.<name>.read` expose per-context
  read/write filters (separate read/write filters are a 3.4+ feature).
- **`task export` ignores the active context.** Every *report* respects the
  context read filter (`report.<name>.context=1`), but `export` — a command,
  not a report — does not, and there is no rc switch to change that. Since jtask
  reads exclusively through `task export`, `taskwarrior.export()` /
  `export_text()` prepend `( <context read filter> )` themselves whenever a
  context is active (`context_read_filter()`, `shlex`-tokenised, cached).
  `apply_context=False` opts out — used only by the backup/export-to-file path,
  which must stay complete. Writes need no help: `task add` already applies the
  context *write* filter.
- `task context none` **exits 2** ("Context not unset.") when no context is
  active — `context_activate(None)` treats that as a no-op.
- `task calc` handles both date arithmetic and plain numeric arithmetic — the
  Calc panel passes the expression through untouched; Taskwarrior's grammar is
  the source of truth.
- `task edit` shells out to `$EDITOR`; not natively wrapped (see feature matrix).
- ANSI SGR header underlines appear in some report output (`context list`,
  `show`) **even with `rc.color=off`/`rc._forcecolor=off`** — already handled by
  `strip_ansi()` in the Raw Console and to be reused by every new text view.

## Things Taskwarrior genuinely cannot do from plain `task` (documented, not gaps)

- **Historical time-tracking sessions** as a first-class store — only the
  current `start` timestamp lives in the data; session history is reconstructed
  from the modification log (see feature matrix → Timesheet). Full session
  tracking is Timewarrior's job.
- **Per-variable config source path** (which file / context set it) — only
  "overridden vs. default" is observable.
- **Structured undo of a specific past change** — `task undo` is strictly
  last-transaction; the GUI cannot offer "undo this one change from 3 edits ago".
