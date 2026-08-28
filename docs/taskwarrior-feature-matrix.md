# Taskwarrior ↔ jtask-gui feature matrix

Baseline: **Taskwarrior 3.5.0** (this machine; `task diagnostics` libshared 14.2.0).
Legend for *Native GUI*: ✅ full · 🟡 partial · ❌ none (console only) · — n/a.

"Console only" means the capability is reachable **only** by typing a raw
`task …` line into the Raw Command Console — it is not a substitute for native
coverage and the mission counts it as *not covered natively*.

Kept up to date as milestones land. Status column values: **Implemented /
Partial / Console-only / Not-applicable / Unsupported-by-installed-TW**.

---

## A. Commands (`task _commands`)

| Command | Native GUI today | Console | Gap → milestone | Status |
|---|---|---|---|---|
| `add` | ✅ quick-add + (planned) full add dialog | ✅ | full add dialog with all fields → **M5** | Partial |
| `modify` | ✅ detail panel save (diff), drag-drop project/due, bulk project/due | ✅ | bulk priority/tag/status/wait, inline edit → **M5** | Partial |
| `done` | ✅ row action + bulk | ✅ | — | Implemented |
| `delete` | ✅ row action + bulk (uses TW confirm) | ✅ | GUI-side confirm + count regardless of `rc.confirmation` → **M5** | Partial |
| `start` / `stop` | ✅ row action + context menu | ✅ | timer indicator, elapsed time → **M6** | Partial |
| `annotate` | ✅ detail panel | ✅ | bulk annotate → **M5** | Implemented |
| `denotate` | ✅ detail panel | ✅ | — | Implemented |
| `append` / `prepend` | ❌ (only via `modify`-style save) | ✅ | native append/prepend actions → **M5** | Console-only |
| `duplicate` | ❌ | ✅ | "Duplicate task" action, show new id/uuid → **M5** | Console-only |
| `log` | ❌ | ✅ | "Log completed task" dialog → **M5** | Console-only |
| `undo` | ✅ toolbar + Ctrl+Z (`rc.confirmation=off`) | ✅ | show "N operations will be reverted" preview + GUI confirm → **M5** | Partial |
| `purge` | ❌ | ✅ | native purge, hard confirm + exact count → **M5** | Console-only |
| `edit` | ❌ (spawns `$EDITOR`) | ✅ | "Raw task editor" = export `.task` text → edit → re-import; else console | Console-only |
| `import` / `import-v2` | ❌ | ✅ | Import dialog: file picker, format detect, preview, confirm → **M7** | Console-only |
| `export` | 🟡 core `taskwarrior.export` used internally; no user export | ✅ | Export dialog: JSON/TW-format, filter/all, destination → **M7** | Partial |
| `synchronize` / `sync` | ❌ | ✅ | Sync Manager: async, status, last-sync, retry, no concurrent runs → **M6** | Console-only |
| `config` | ❌ | ✅ | Configuration Manager (read current/default/overridden, write via `task config`) → **M8** | Console-only |
| `context` | 🟡 sidebar switch + `task context none/<name>` | ✅ | Context Manager: create/edit/delete, show filters → **M8** | Partial |
| `calc` | ❌ | ✅ | Calc panel wrapping `task calc` → **M9** | Console-only |
| `count` | ✅ used internally (status bar counts) | ✅ | — | Implemented |
| `stats` | ❌ | ✅ | Statistics view → **M6** | Console-only |
| `diagnostics` | ❌ | ✅ | Diagnostics view (readable, copyable, exportable) → **M9** | Console-only |
| `information` / `task <id>` | 🟡 detail panel shows attributes + urgency terms + audit | ✅ | History tab (parse modification log), Raw Data tab → **M6** | Partial |
| `version` | 🟡 shown in status bar ("Taskwarrior آماده") | ✅ | show detected version in Diagnostics + startup → **M9** | Partial |
| `help` | ❌ | ✅ | Command Browser/Help (from installed `task help`) → **M9** | Console-only |
| `news` | ❌ | ✅ | (low value) console-only, documented | Console-only |
| `execute` | ❌ | ✅ | intentionally console-only (arbitrary shell) | Console-only |
| `calendar` | 🟡 CLI has it; GUI has its own Jalali calendar report (M2) | ✅ | GUI calendar is better; TW `calendar` stays console | Implemented |
| built-in reports (`next/list/all/waiting/blocked/blocking/ready/active/completed/recurring/overdue/minimal/newest/oldest/long/ls`) | 🟡 sidebar quick-views map several; not all | ✅ | Reports Manager: run any report, configurable → **M8** | Partial |
| `burndown.*` / `history.*` / `ghistory.*` | ✅ native charts (M2), computed from export | ✅ | period-granularity toggle done | Implemented |
| `summary` | ✅ native progress view (M2) | ✅ | — | Implemented |
| `timesheet` | ❌ | ✅ | Timesheet view (from modification-log session parse) → **M6** | Console-only |
| `colors` / `logo` | — | ✅ | not applicable to a GUI | Not-applicable |
| `show` | ❌ (used internally via `_show`) | ✅ | folded into Configuration Manager → **M8** | Console-only |
| `_*` helper commands | ✅ used internally as shared lookups | ✅ | — | Implemented |

## B. Task attributes (`task _columns`)

| Attribute | Native edit | Native display | Gap → milestone |
|---|---|---|---|
| description | ✅ detail + quick-add | ✅ table + detail | — |
| project (dotted) | ✅ combo + drag-drop | ✅ table + sidebar tree | inline edit → M5 |
| tags | ✅ chip editor | ✅ table | bulk tag add/remove → M5 |
| priority | ✅ combo | ✅ table | bulk → M5 |
| due / scheduled / wait / until | ✅ Jalali pickers | ✅ table (Jalali) | bulk date change → M5 |
| status | 🟡 via done/delete/start actions | ✅ table | — |
| recur / rtype / mask / imask | ✅ recurrence builder (M3) | 🟡 indicator icon | recurrence templates view → M8 |
| depends | ✅ picker + dep graph (M3) | ✅ indicator + graph | — |
| annotations | ✅ detail | 🟡 indicator icon | first-class History/Annotations tabs → M6 |
| urgency | ✅ read-only + "چرا؟" breakdown | ✅ table column | — |
| entry / modified / end | ✅ audit line (Jalali) | 🟡 | History tab → M6 |
| start | 🟡 via start/stop | ❌ no elapsed display | timer indicator → M6 |
| uuid / id / parent | ✅ shown | ✅ | Raw Data tab → M6 |
| template | ❌ | ❌ | rare; console-only, documented |
| UDAs (any) | ✅ dynamic widgets in detail (M1) | ✅ (if a column) | UDA **Manager** (CRUD the definitions) → M8; UDA **filters** → M9 |

## C. Filtering grammar

| Construct | Visual builder | Raw filter bar | Gap → milestone |
|---|---|---|---|
| `attr:value` (project, status, priority, …) | ✅ | ✅ | — |
| `+tag` / `-tag` | ✅ | ✅ | — |
| `attr.before:` / `.after:` (dates) | ✅ (Jalali pickers) | ✅ | more modifiers (`.is`, `.isnt`, `.has`, `.startswith`, `.over`, `.under`, `.none`, `.any`) → M9 |
| id / id-range / uuid | 🟡 (raw extras) | ✅ | dedicated field → M9 |
| `/regex/` | ❌ | ✅ | builder support → M9 |
| `and` / `or` / `xor` / parentheses | ❌ | ✅ | builder support (or clearly document the raw box handles it) → M9 |
| virtual tags (`+OVERDUE`, `+BLOCKED`, …) | 🟡 (quick views use them) | ✅ | picker → M9 |
| UDA filters | ❌ | ✅ | builder support → M9 |

The raw filter bar already accepts **any** Taskwarrior filter string verbatim
(with autocomplete), so no user is ever blocked — the gaps above are
convenience, not capability.

## D. Configuration & introspection

| Area | Native GUI | Gap → milestone |
|---|---|---|
| theme / Persian digits / due-soon threshold / notifications | ✅ settings dialog (persisted) | — |
| Taskwarrior `rc.*` settings (dateformat, weekstart, confirmation, recurrence, hooks, verbosity, aliases, sync.*, color.*, …) | ❌ | Configuration Manager (current / default / overridden, write via `task config`) → M8 |
| contexts | 🟡 switch only | Context Manager → M8 |
| UDA definitions | ❌ | UDA Manager → M8 |
| report definitions | 🟡 custom reports *discovered & rendered* read-only (M3) | Reports Manager (create/edit definitions, never clobber existing) → M8 |
| aliases | ❌ | list in Command Browser → M9 |
| hooks | ❌ | list (read-only) in Diagnostics → M9 |

---

## Feasibility resolutions (Phase 0)

### Per-field task History — **feasible, real data**

`task <id> information` ends with a `Date | Modification` section: a full
chronological log — `Priority changed from 'M' to 'H'`, `Tag 'alpha' deleted`,
`Start deleted (duration: 0:00:01)`, `Due set to '…'`, etc. The date prints once
per day-group. This is first-party data.

**Plan:** a **History tab** that parses this section into rows
`(timestamp, change)`, timestamps shown Jalali, with light Persian labels for
the common verbs (set / changed A→B / added / deleted). No fabricated diff —
every row is a line Taskwarrior actually emitted. Coarser `entry/modified/end`
timestamps are shown alongside as anchors. (M6.)

### Timesheet — **feasible without Timewarrior**

Plain `task export` keeps only the *current* `start` — no session log.
**However**, the `information` modification log records every
`Start set to '<ts>'` and `Start deleted (duration: <d>)` pair — i.e. a real,
retroactive per-session history in Taskwarrior's own data. Timewarrior is **not
installed** on this machine.

**Plan (M6):**
1. Primary source — parse `Start set` / `Start deleted (duration:…)` pairs from
   `task <filter> information` across the selected tasks/date-range → real
   sessions (task, start, end, duration).
2. Current timer — the live `start` attribute from `export`, with running
   elapsed time.
3. Totals — summed per task / project / day, all through `fmt.py`.
4. Timewarrior — **detected** at runtime (`shutil.which("timew")`); if present,
   offer it as a richer optional source. Not assumed, not required.
5. The view is labelled honestly ("جلسه‌های زمان‌سنجی از تاریخچهٔ Taskwarrior")
   — not presented as something it isn't.

### `task edit` — **console-first**

Spawns `$EDITOR` on a temp `.task` file. Wrapping it natively means either
launching an external editor (fragile) or a "raw task editor" = `task <id>
export` → editable text → `task import`. Low value vs. the detail panel + Raw
Data tab. **Decision:** stays console-only for M5; a "Raw task editor" is a
stretch item, not a milestone blocker.

### Configuration source/default — **feasible**

`task show <var>` prints the current value and, when it differs, a
`Default value <x>` line plus a global "differ from the default" notice. So the
Config Manager can show **current / default / overridden-flag** per variable.
True per-variable *source path* (which rc file / context) is not exposed; we
show "‎~/.taskrc" when overridden, "پیش‌فرض" otherwise, and document the limit.
