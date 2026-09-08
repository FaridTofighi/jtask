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
| `add` | ✅ quick-add **and** full Add Task dialog (description / project / tags / priority / due·scheduled·wait·until Jalali pickers / recurrence / depends, with validation) (M5) | ✅ | — | Implemented |
| `modify` | ✅ detail panel save (diff), drag-drop project/due, **bulk edit dialog** (priority / project / tag +− / due / scheduled / wait, affected count, confirm) (M5) | ✅ | single-cell inline edit → later | Implemented |
| `done` | ✅ row action + bulk | ✅ | — | Implemented |
| `delete` | ✅ row action + bulk, **GUI confirm + exact count**, danger-styled (M5) | ✅ | — | Implemented |
| `start` / `stop` | ✅ row action + context menu + **status-bar timer indicator** (live elapsed, click to stop) (M6) | ✅ | — | Implemented |
| `annotate` | ✅ detail panel | ✅ | bulk annotate → later | Implemented |
| `denotate` | ✅ detail panel | ✅ | — | Implemented |
| `append` / `prepend` | ✅ context-menu action, prompts for text, bulk-capable with confirm (M5) | ✅ | — | Implemented |
| `duplicate` | ✅ context-menu action; single-task shows the new id/uuid (M5) | ✅ | — | Implemented |
| `log` | ✅ "ثبت کار انجام‌شده…" toolbar action — same full form as Add (recurrence hidden), runs `task log` (M5) | ✅ | back-dating `end` → later | Implemented |
| `undo` | ✅ toolbar + Ctrl+Z — **preview dialog** ("N operations would be reverted" + raw diff) then GUI confirm before applying (M5) | ✅ | — | Implemented |
| `purge` | ✅ context-menu action on deleted tasks — hard confirm (type «پاک‌سازی») + exact count, `taskwarrior.purge()` returns purged count (M5) | ✅ | — | Implemented |
| `edit` | ❌ (spawns `$EDITOR`) | ✅ | "Raw task editor" = export `.task` text → edit → re-import; else console | Console-only |
| `import` | ✅ Import dialog — file picker, shape detect (array vs JSON-lines), count + sample preview, same-UUID-updates warning, `task import` (M7) | ✅ | — | Implemented |
| `import-v2` | — | ✅ | legacy `*.data` migration path only — not a JSON importer; console-only by design | Console-only |
| `export` | ✅ Export dialog — scope (all / current filter / custom) × format (indented array / JSON lines), destination picker (Jalali-dated default), live count (M7); `taskwarrior.export_text()` | ✅ | — | Implemented |
| `synchronize` / `sync` | ✅ Sync Manager — detects config (`rc.sync.*`), server/kind shown, last-sync time (Jalali, persisted), async run with visible state, no concurrent runs, refresh after; unconfigured → points at Config Manager (M7). **Auto-sync**: opt-in toggle + interval (seconds, 60s floor) in the Sync Manager; one `AutoSyncManager` timer + shared guard; each interval result posts a clickable status-bar note (failure → opens the Sync Manager, never a blocking dialog) | ✅ | — | Implemented |
| `config` | ✅ Configuration Manager — every `rc.*` (searchable, grouped), current / default / overridden, edit + "reset to default" via `task config` (never `.taskrc` text) (M8) | ✅ | — | Implemented |
| `context` | ✅ Context Manager — list / create / edit / delete / activate, read+write filters shown; sidebar switch stays (M8). **The active context's read filter now scopes every jtask read** — `task export` ignores context, so `taskwarrior.export()` applies it itself (backups opt out) | ✅ | separate write-filter form is version-dependent (documented) | Implemented |
| `calc` | ✅ Calculator tab in «تشخیص و ابزارها» — wraps `task calc`; date results annotated with a Jalali rendering (M9) | ✅ | — | Implemented |
| `count` | ✅ used internally (status bar counts) | ✅ | — | Implemented |
| `stats` | ✅ "آمار" report — `task stats` parsed, Persian labels, Jalali dates, Persian digits, respects the active filter (M6) | ✅ | — | Implemented |
| `diagnostics` | ✅ Diagnostics tab — full `task diagnostics`, copy + save-to-file (M9) | ✅ | — | Implemented |
| `information` / `task <id>` | ✅ detail panel + **History tab** (modification log → Jalali/Persian, raw line kept) + **Raw Data tab** (stored JSON) (M6) | ✅ | — | Implemented |
| `version` | ✅ detected version in the status bar ("Taskwarrior 3.5.0") + Diagnostics tab (M9) | ✅ | — | Implemented |
| `help` | ✅ "راهنمای فرمان‌ها" tab — searchable table parsed from `task help`, **"فرستادن به کنسول"** on the selected row | ✅ | — | Implemented |
| `news` | ❌ | ✅ | (low value) console-only, documented | Console-only |
| `execute` | ❌ | ✅ | intentionally console-only (arbitrary shell) | Console-only |
| `calendar` | 🟡 CLI has it; GUI has its own Jalali calendar report (M2) | ✅ | GUI calendar is better; TW `calendar` stays console | Implemented |
| built-in reports (`next/list/all/waiting/blocked/blocking/ready/active/completed/recurring/overdue/minimal/newest/oldest/long/ls`) | ✅ Reports Manager lists every report with its columns / filter; sidebar quick-views map the common ones (M8) | ✅ | run-any-report-inline is via a custom report or the console | Implemented |
| `burndown.*` / `history.*` / `ghistory.*` | ✅ native charts (M2), computed from export | ✅ | period-granularity toggle done | Implemented |
| `summary` | ✅ native progress view (M2) | ✅ | — | Implemented |
| `timesheet` | ✅ "برگهٔ زمان" — sessions rebuilt from `Start set` / `Start deleted (duration:…)` log pairs, Jalali date-range picker, per-task / per-project / per-day totals, running-session marker, honest label; detects Timewarrior (M6) | ✅ | multi-day session split; per-task `information` calls capped at 300 | Implemented |
| `colors` / `logo` | — | ✅ | not applicable to a GUI | Not-applicable |
| `show` | ✅ folded into the Configuration Manager (current / default / overridden) (M8) | ✅ | — | Implemented |
| `_*` helper commands | ✅ used internally as shared lookups | ✅ | — | Implemented |

## B. Task attributes (`task _columns`)

| Attribute | Native edit | Native display | Gap → milestone |
|---|---|---|---|
| description | ✅ detail + quick-add | ✅ table + detail | — |
| project (dotted) | ✅ combo + drag-drop + **bulk edit** (M5) + **sidebar project management** (right-click a project → rename it and its sub-projects, or delete it and all its sub-tasks — hard type-the-name confirm, reversible via Undo; set / change / clear a **colour** — writes Taskwarrior's own `color.project.<name>`, shown as a swatch dot in the sidebar) | ✅ table + sidebar tree | single-cell inline edit → later |
| tags | ✅ chip editor + **bulk add/remove** + **sidebar tag management** (drop tasks on a tag to add it; right-click a tag → rename / remove across every task) | ✅ table | — |
| priority | ✅ combo + **bulk** (M5) | ✅ table | — |
| due / scheduled / wait / until | ✅ Jalali pickers + **bulk date change / clear** (due·scheduled·wait·**until**) | ✅ table (Jalali) | — |
| status | 🟡 via done/delete/start actions | ✅ table | — |
| recur / rtype / mask / imask | ✅ recurrence builder + **template browser** (Add Task → "از الگوی موجود…") | 🟡 indicator icon | — |
| depends | ✅ picker + dep graph (M3) | ✅ indicator + graph | — |
| annotations | ✅ detail summary + **dedicated Annotations tab** + **bulk annotate** (context menu) + shown in History tab | 🟡 indicator icon | — |
| urgency | ✅ read-only + "چرا؟" breakdown | ✅ table column | — |
| entry / modified / end | ✅ audit line + **History tab** anchors (Jalali) (M6) | 🟡 | — |
| start | ✅ start/stop + **live timer indicator** with elapsed (M6) | ✅ status bar | — |
| uuid / id / parent | ✅ shown + **Raw Data tab** (M6) | ✅ | — |
| template | ❌ | ❌ | rare; console-only, documented |
| UDAs (any) | ✅ dynamic widgets in detail (M1) + **UDA Manager** CRUD (M8) + **typed UDA rows in the filter builder** | ✅ (if a column) | — |

## C. Filtering grammar

| Construct | Visual builder | Raw filter bar | Gap → milestone |
|---|---|---|---|
| `attr:value` (project, status, priority, …) | ✅ | ✅ | — |
| `+tag` / `-tag` | ✅ | ✅ | — |
| `attr.before:` / `.after:` (dates) | ✅ (Jalali pickers) | ✅ | `rewrite_args` already converts every date modifier (`.is` `.isnt` `.not` `.under` `.over` `.by` too — see `tests/test_date_grammar.py`); more builder rows → later |
| `/regex/` | ✅ "الگوی شرح" field in the builder (M9) | ✅ | — |
| `and` / `or` / `xor` / parentheses | 🟡 the builder's raw-extras box takes them verbatim, labelled as such (M9) | ✅ | a structured boolean builder is out of scope — documented |
| id / id-range / uuid | ✅ dedicated "شناسه / UUID" field in the builder (M9) | ✅ | — |
| virtual tags (`+OVERDUE`, `+BLOCKED`, …) | ✅ one-click picker in the builder (9 common tags) + quick views (M9) | ✅ | — |
| UDA filters | ✅ one typed row per UDA in the builder (string / enum / numeric+op / date+op) | ✅ | — |

The raw filter bar already accepts **any** Taskwarrior filter string verbatim
(with autocomplete), so no user is ever blocked — the gaps above are
convenience, not capability.

## D. Configuration & introspection

| Area | Native GUI | Gap → milestone |
|---|---|---|
| theme / Persian digits / due-soon threshold / notifications | ✅ settings dialog (persisted) | — |
| `task` binary path / `TASKDATA` / `TASKRC` overrides + column-layout reset | ✅ settings dialog "Taskwarrior" section (persisted, restart-applied via `os.environ`) | — |
| Taskwarrior `rc.*` settings (dateformat, weekstart, confirmation, recurrence, hooks, verbosity, sync.*, color.*, …) | ✅ Configuration Manager (M8) — current / default / overridden, write/reset via `task config` | — |
| contexts | ✅ Context Manager (M8) — full CRUD + activate + filters | — |
| UDA definitions | ✅ UDA Manager (M8) — CRUD (name / label / type / values / default); delete warns data is kept | — |
| report definitions | ✅ Reports Manager (M8) — all reports listed; custom reports editable (columns / labels / sort / filter / dateformat / description); built-ins read-only, overriding one needs explicit confirm | — |
| aliases | 🟡 visible in the Config Manager (`alias.*` rows) | dedicated list in Command Browser → M9 |
| hooks | ✅ **Hook Manager** (Manager dialog, 5th tab) — lists installed hooks with event + status, enable/disable (executable bit), reveal in folder; body editing stays `$EDITOR`/console | — |

---

## Intentional non-features (documented decisions, not gaps)

### Backup / Restore — **not a milestone item**

Taskwarrior has never had a first-class backup/restore command, and jtask does
not add one. The **Export** dialog (M7 — scope "all", either JSON shape, to a
file the user chooses) plus the **Import** dialog together give a complete
manual backup-and-restore path: export everything → keep the file → import it
into a fresh database (round-trip verified in `tests/test_data_io.py`). This is
deliberate; a dedicated "backup" button would only be a thin alias over Export
with the scope forced to "all".

### GUI-enforced confirmation layer (M5)

jtask always invokes `task` with `rc.confirmation=off rc.bulk=0` so Taskwarrior
never blocks on its own terminal prompt (which a GUI cannot answer). Every
destructive or bulk action instead routes through jtask's own confirmation
dialog (`widgets/confirm.py`) **before** any command runs — showing the exact
affected count, a danger-styled button for destructive ops, and a
type-the-word hard confirmation for `purge`. This gate is independent of the
user's `rc.confirmation` / `rc.bulk` values: it is always present and always
the same.

### Real error surfacing (M5, cross-cutting from here on)

Every Taskwarrior-facing action shows failures through `widgets/error_dialog.py`:
the human message on top, and the real `$ command`, exit code and stderr behind
a disclosure with copy-to-clipboard and a jump into the Raw Command Console.
`taskwarrior.run()` raises `TaskCommandError` (carrying returncode / stderr /
cmd) on any non-zero exit; background workers deliver the exception object
itself, never a flattened string. `rc.verbose=nothing` is **not** in the shared
rc-override set (it silences Taskwarrior's own error text) — read-only callers
that parse machine output opt in via `run(..., quiet=True)`.

### Visible async operation state (M5, cross-cutting)

The status bar carries an operation indicator with five states —
idle / running / success / failed / cancelled (`widgets/op_status.py`) — so
every heavy call has a visible lifecycle, not just a spinner that vanishes.

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
