# jtask-gui — Design

## Context

`jtask` (this repo) is a Persian/Jalali shell over Taskwarrior. Its `src/jtask/`
package is already the framework-agnostic core the GUI needs: `jalali.py`
(Jalali↔Gregorian + Persian relative dates + Saturday-first calendar math),
`taskwarrior.py` (subprocess client), `rewrite.py` (bidirectional date-token
rewriting). None of it imports a UI framework.

`jtask-gui` adds a professional PyQt6 desktop application on top of that core.
Goal: expose the **entire** Taskwarrior feature set through a native,
fully right-to-left Persian UI where **every date is Jalali**, with
Taskwarrior's text/ASCII "graphical" reports (burndown, history, ghistory,
summary, calendar) reproduced as real interactive widgets.

The full spec is ~a dozen major subsystems and is delivered in milestones.
**This document specifies Milestone 1**; later milestones are listed at the end.

### Locked decisions

| Decision | Choice |
|---|---|
| Delivery | Milestones, each reviewed. This doc = M1. |
| Charting | matplotlib only, via `FigureCanvasQTAgg` (M2). Calendar = bespoke Qt grid. |
| Code location | Same repo, `src/jtask_gui/`; imports `jtask` core directly. |
| Font | Bundle Vazirmatn TTFs in `src/jtask_gui/resources/fonts/`, load via `QFontDatabase`. |
| Packaging | One `pyproject.toml`; `[project.optional-dependencies] gui`; `jtask-gui` entry point. |
| Threading | Every `task` subprocess call via `QThreadPool` + `QRunnable`. |
| RTL/text | `app.setLayoutDirection(Qt.RightToLeft)`; rely on Qt/HarfBuzz native shaping. No `arabic-reshaper`/`python-bidi` in the GUI. |

---

## Milestone 1 scope

App shell + full task management + the power-user console + two themes.
**No matplotlib charts** — the "Reports & Charts" area ships as a themed
"coming soon" placeholder so navigation is complete from day one.

### Core additions (framework-agnostic, in `src/jtask/`)

#### `reports.py`
Pure data-shaping functions. Each calls `taskwarrior.export()` / `task <report>`
and returns plain Python structures ready for a table or chart renderer — **no
Taskwarrior-report-string parsing in the GUI layer, no Jalali math in the GUI
layer**. Dates in outputs are Jalali strings (via `jalali`/`rewrite`), with raw
Gregorian kept alongside where a caller may need it.

Functions (all accept an optional Taskwarrior `filter: list[str]`):

- Task lists: `report_list`, `report_next`, `report_waiting`, `report_blocked`,
  `report_blocking`, `report_ready`, `report_active`, `report_completed`
  → `list[dict]` (task dicts with Jalali date fields + `*_gregorian`).
- `report_projects()` → `list[dict]`: `{project, open, waiting, overdue, completed, pct}`
  over the dotted hierarchy.
- `report_tags()` → `list[dict]`: `{tag, count}`.
- `report_summary()` → `list[dict]`: per-project `{project, total, done, pct, pending, overdue}`.
- `report_history(period)` / `report_ghistory(period)` — `period ∈ {daily, weekly, monthly}`
  → `{buckets: [{label_jalali, added, completed, deleted, net}]}`. Labels are
  Jalali (month names / `year-week` / `year-mm-dd`).
- `report_burndown(period)` → `{buckets: [{label_jalali, pending, started, done}]}`.
- `report_calendar(year_j, month_j)` → `{grid: <month_grid>, days: {(y,m,d): [task dicts]}}`
  keyed by Jalali date, built on `jalali.month_grid`.

All bucketing uses **Jalali** period boundaries (weeks start Saturday) computed
from `jalali`, not Taskwarrior's Gregorian buckets, so axes line up with the
rest of the app.

#### `taskwarrior.py` — shared autocomplete/lookup source (adjustment 4)
One place both `filter_bar.py` and `quick_add.py` (and the detail panel) read
from — no duplicated fetching:

- `list_projects() -> list[str]` — wraps `task _projects`.
- `list_tags() -> list[str]` — wraps `task _tags`.
- `uda_definitions() -> dict[str, dict]` — `{name: {type, label, values?}}` parsed
  from `task _show` (extends the existing `date_uda_names()` which becomes a
  thin filter over this).
- `list_contexts() -> list[str]` and `current_context() -> str | None` — `task context list` / `task _get rc.context`.
- `list_reports() -> list[str]` — `task _reports` (for M2 custom-report discovery; exposed now).

Each is memoised per process with an explicit `refresh_lookups()` to clear.

### GUI package (`src/jtask_gui/`)

```
src/jtask_gui/
├── __init__.py
├── __main__.py                # python -m jtask_gui
├── app.py                     # QApplication, RTL, font load, theme apply, show MainWindow
├── main_window.py             # QMainWindow shell + toolbar (incl. Undo) + status bar
├── workers.py                 # QThreadPool + TaskRunnable; signals: finished(obj)/failed(str)
├── settings.py                # QSettings wrapper (typed getters/setters)
├── theme.py                   # discover + load QSS themes, live switch, expose palette tokens
├── models/
│   ├── task_model.py          # QAbstractTableModel over list[dict] from reports.py
│   └── column_spec.py         # column definitions: key, header(fa), width, formatter, visible
├── widgets/
│   ├── sidebar.py             # nav tree: quick views, projects tree, tags, contexts, Reports&Charts
│   ├── task_table.py          # QTableView + sort/group/multiselect/bulk/hover-actions
│   ├── detail_panel.py        # slide-in; every attribute incl. dynamic UDAs
│   ├── jalali_calendar.py     # REUSABLE month-grid engine (adjustment 2)
│   ├── jalali_date_picker.py  # thin popover consumer of the grid engine
│   ├── quick_add.py           # single input + live parse preview
│   ├── filter_bar.py          # raw Taskwarrior filter + autocomplete
│   ├── command_console.py     # dockable raw `task …` console (§6.9 escape hatch)
│   ├── chips.py               # tag-chip editor with autocomplete
│   └── recurrence_builder.py  # friendly recur: builder -> Taskwarrior syntax
├── reports_placeholder.py     # themed "به‌زودی" empty state for Reports & Charts (adjustment 3)
└── resources/
    ├── fonts/Vazirmatn-{Regular,Medium,Bold}.ttf
    └── themes/{shab,ruz}.qss
```

#### `main_window.py` — shell & Undo (adjustment 1)
- `QMainWindow`. Central widget: `QSplitter` [ task table | detail panel (hidden until selection) ].
  Left dock (visually **right**, RTL): `sidebar.py`. Bottom dock: `command_console.py` (toggle).
- Top toolbar: quick-add (stretch), `filter_bar`, theme switcher, and a visible
  **«واگرد آخرین عملیات»** action (icon + text) plus `Ctrl+Z`, wired through
  `workers.py` to `taskwarrior.run(["undo"])` — same threaded write path as
  done/modify/delete. After it returns, the active view refreshes.
- Status bar: `«{visible}/{total} کار»`, background-op spinner, Taskwarrior
  binary/sync status.
- All writes: optimistic disable of the triggering control → `TaskRunnable` →
  on `finished` refresh the current report, on `failed` show a Persian
  `QMessageBox` (full detail to a rotating log file, never a raw traceback).

#### `workers.py`
```python
class TaskRunnable(QRunnable):
    # wraps a callable (usually a functools.partial over jtask.taskwarrior / reports)
    # signals via an inner QObject: finished(object), failed(str)
```
`submit(fn, on_ok, on_err=None)` helper on a module-level `QThreadPool`.
No `task` call anywhere else on the UI thread.

#### `models/task_model.py`
- `QAbstractTableModel` wrapping `list[dict]`.
- Columns from `column_spec.py`: id, description, project, tags, priority,
  due, scheduled, wait, urgency, status, + indicator columns (annotations,
  recurrence, dependency) rendered as icons.
- `Qt.TextAlignmentRole` → right; date cells already Jalali strings from
  `reports.py`; Persian-digit toggle honoured via a formatter.
- Colour roles from the theme palette: overdue / due-soon / waiting (muted) /
  completed (dim + strike) / blocked.
- `setTasks(list)` does a proper `beginResetModel/endResetModel`. Sorting via
  `QSortFilterProxyModel`; grouping handled in `task_table.py` by swapping in a
  tree model wrapper (project / due-week (Jalali) / priority / tag).

#### `widgets/jalali_calendar.py` — reusable engine (adjustment 2)
```python
class JalaliMonthGrid(QWidget):
    """Saturday-first Jalali month grid. Knows ONLY how to lay out a month.

    monthChanged(year, month)         # emitted on navigation
    def set_month(year, month): ...
    def set_cell_factory(factory): ...  # factory(ctx: DayCellContext) -> QWidget
    """
```
- Uses `jalali.month_grid(year, month)` (already leap-year correct, Saturday-first)
  and `jalali.WEEKDAY_NAMES_SHORT` for the header row.
- Header: month name + year (Jalali) with ‹ › nav; a 7-col `QGridLayout` body.
- `DayCellContext` = `{year, month, day, is_today, is_current_month, weekday_index}`.
- The grid **never** decides what a click means or what a cell shows — the
  caller's factory builds each cell widget and connects its own signals.
- No date-picker behaviour (no "click closes / returns a date") lives here.

#### `widgets/jalali_date_picker.py`
- `QWidget` with a line edit (accepts typed Jalali / Persian-relative text,
  validated via `jalali.resolve`) + a button opening a popover containing a
  `JalaliMonthGrid` whose factory renders plain selectable day-number buttons.
- Optional time spinner (`QTimeEdit`) for datetime fields.
- Clicking a day (picker-level behaviour) sets the value, closes the popover,
  emits `dateChanged(jdate)`. Emits Gregorian on request for the write path.

#### `widgets/detail_panel.py`
Slide-in `QWidget` (animated width via `QPropertyAnimation`), scrollable form.
Every attribute of the selected task:
- description (multiline), project (`QComboBox` editable + autocomplete from
  `taskwarrior.list_projects()`, inline new-project accepted), tag chips
  (`chips.py` + `list_tags()`), priority (`H/M/L/none`), status.
- due / scheduled / wait / until — each a `JalaliDatePicker`.
- recurrence — `recurrence_builder.py` (every N days/weeks/months/years →
  `recur:` + required `due:`), with a raw-text override field.
- dependencies — searchable multi-select over open tasks; shows blocking/blocked
  badges. (Dependency **graph** view deferred to a later milestone.)
- annotations — list with Jalali timestamps; add / delete.
- UDAs — built dynamically from `taskwarrior.uda_definitions()`, control per
  declared type: string→line edit, numeric→spin, date→`JalaliDatePicker`,
  duration→line edit with hint.
- urgency — read-only value; "چرا؟" expander shows factor breakdown if
  `task _urgency` / export provides it, else hidden.
- audit — entry / modified / end in Jalali, read-only.
- Save → diff against original → single `task <uuid> modify <changed...>` through
  `workers.py` after `rewrite.rewrite_args`. Never writes unchanged fields.

#### `widgets/sidebar.py`
`QTreeWidget`-style nav:
- **نماهای سریع**: امروز، این هفته، معوق، اقدامات بعدی، در انتظار، مسدودشده،
  تکمیل‌شده. Each maps to a `reports.py` call / filter. Live counts (threaded).
- **پروژه‌ها**: tree from the dotted hierarchy (`report_projects()`), per-row
  open count + tiny progress bar (`pct`).
- **برچسب‌ها**: `report_tags()`, click → filter task list.
- **زمینه‌ها (Context)**: `list_contexts()`, radio-style; switching calls
  `task context <name>` threaded, then refreshes.
- **گزارش‌ها و نمودارها** (adjustment 3): selecting it swaps the content area
  for `reports_placeholder.py`.
- **فیلترهای ذخیره‌شده**: M1 = read `task _reports` and list them (open as raw
  table); saving/pinning user filters deferred to M2.

#### `reports_placeholder.py`
Centered themed panel: heading «گزارش‌ها و نمودارها»، a short Persian paragraph
listing what's coming (سوختن، تاریخچه، خلاصهٔ پروژه‌ها، تقویم جلالی), a «به‌زودی»
badge. Pure theme tokens, no hardcoded colour.

#### `widgets/command_console.py`
Dockable. Input line (monospace) → prepend nothing, run
`rewrite.rewrite_args(shlex.split(text))` then `taskwarrior.passthrough`-style
capture through `workers.py`; output pane shows stdout/stderr verbatim. History
with ↑/↓. This guarantees §1 "zero feature loss" in M1 already.

#### `theme.py` + QSS
- `shab.qss` (dark) / `ruz.qss` (light): full coverage — `QMainWindow`,
  `QTableView` (incl. header, selection, alternate rows), `QTreeWidget`,
  `QPushButton` (primary/secondary via `objectName`), chips, `QLineEdit`,
  `QComboBox`, `QScrollBar`, dock titlebars, tooltips, the detail panel,
  the placeholder.
- A `:root`-style token block is emulated by a small Python dict of palette
  values per theme (`theme.palette()`) that non-QSS consumers (model colour
  roles, matplotlib in M2) read, kept in sync with the QSS by convention +
  a test that every palette key is referenced in the QSS.
- Live switch: `app.setStyleSheet(...)` + repolish; model emits `dataChanged`
  for colour roles.

#### `settings.py`
`QSettings("jtask", "jtask-gui")`: theme, window geometry/state, column order +
visibility + widths, last filter per quick-view, `persian_digits` (default from
`jtask.config`), `due_soon_days` (default 3), console dock visibility.

### `pyproject.toml` changes
- `[project.optional-dependencies]`
  `gui = ["PyQt6>=6.6", "matplotlib>=3.8", "qtawesome>=1.3"]`
  `dev` gains `pytest-qt>=4.4`.
- `[project.scripts]` add `jtask-gui = "jtask_gui.app:main"`.
- `[tool.hatch.build.targets.wheel]` packages gains `src/jtask_gui`; force-include
  `src/jtask_gui/resources`.
- ruff: `src/jtask_gui/resources` excluded; Qt naming (`camelCase` overrides)
  handled with a per-file ignore for `N802`/`N815` where subclassing Qt.

### Tests

**`tests/test_reports.py`** (no Qt) — against isolated `TASKDATA`/`TASKRC`,
`jalali.LOCAL_TZ` pinned:
- each `report_*` returns the expected shape;
- Jalali bucket labels for history/ghistory/burndown at all three granularities;
- `report_projects` percentages and hierarchy;
- `report_calendar` keys tasks on the right Jalali day;
- empty-data cases return empty structures, not errors.

**`tests/gui/`** (`pytest-qt`, `QT_QPA_PLATFORM=offscreen`, `qapp` fixture):
- `test_jalali_calendar.py` — grid engine: Saturday-first layout, leading blanks,
  leap Esfand (1403 → 30 days, 1404 → 29), month nav wraps year, cell factory is
  invoked once per real day with the right `DayCellContext`.
- `test_quick_add.py` — parser: `"تماس با آرش فردا +تماس pri:H project:کار"` →
  live preview shows resolved Jalali date + tag + project + priority; commit
  creates the task in an isolated Taskwarrior and it appears via `report_next`.
- `test_filter_bar.py` — visual state / raw string round-trips; autocomplete
  pulls from the shared `taskwarrior.list_projects/list_tags`.
- `test_task_model.py` — column formatting (Jalali dates, Persian digits toggle),
  colour role for overdue vs due-soon vs completed, `setTasks` reset.
- `test_integration_flow.py` — add (quick-add) → appears in list → due shows
  correct Jalali date → mark done via row action → leaves list, appears in
  `completed` view. All through the real threaded worker path
  (`qtbot.waitSignal`).

### Verification (manual, after build)
```
QT_QPA_PLATFORM=offscreen pytest -q            # reports + gui suites green
jtask-gui                                       # launches RTL, Vazirmatn, dark theme
# add a task via quick-add with due:فردا; confirm Jalali in list + detail panel
# switch theme live; toggle Persian digits; open command console, run `_tags`
# select task -> detail panel slides in -> edit due via Jalali picker -> save
# toolbar Undo reverts it; sidebar counts refresh
# click "گزارش‌ها و نمودارها" -> themed "به‌زودی" placeholder
```

---

## Milestone 1 — delivered

Shipped in `src/jtask_gui/` + `src/jtask/reports.py` + the shared lookups in
`src/jtask/taskwarrior.py`. 118 tests pass (`pytest -q`), `ruff` clean, `mypy`
clean on the core.

Minor deviations from the plan above, all deliberate:

- **Themes**: instead of two independently hand-written `shab.qss` / `ruz.qss`,
  there is one `resources/themes/app.qss` template with `@token@` placeholders
  and a Python palette per theme (`theme.palette`). The palette is the single
  source of truth; a test asserts template tokens and palette keys stay in
  lockstep. Same end result (full per-widget coverage, live switch), less
  duplication.
- **mypy** runs on `src/jtask` only; the PyQt6 layer is covered by `pytest-qt`
  (the Qt6 stubs' pervasive `| None` returns make a strict GUI pass mostly
  noise). Recorded in `pyproject.toml`.
- **Grouping** in the task table is proxy-sort-based (group key sorts first);
  collapsible visual group headers are deferred to M2.
- **Settings dialog** is a compact subset (theme, Persian digits, due-soon
  threshold); binary/`TASKDATA`/`TASKRC` overrides and column reset move to M4.
- **Dependency picker** is a searchable `QInputDialog` over open tasks; the
  dependency *graph* view was already deferred (M3).

## M1 visual/UX remediation pass

A review found the M1 architecture sound but the visual execution at
default-Qt-prototype quality. This pass addressed it.

### Priority 0 — root cause (documented so it is not reintroduced)

**Symptom:** the task table filled only a small top corner of the central
area; ~90 % was blank.

**Root cause:** the detail panel was the second pane of the central
`QSplitter` and was "closed" by animating its `maximumWidth` to 0 while it
stayed `setVisible(True)`. A `QSplitter` still **reserves its stored size slot**
for a visible child even when that child is clamped to width 0 — so the slot
(≈550 px, from the persisted splitter sizes) became dead blank space the table
could not use.

**Fix / invariant:** a splitter pane must be `setVisible(False)` — not merely
zero-width — to free its space. The detail panel now:
- starts `setVisible(False)` with `splitter.setSizes([BIG, 0])` and
  `setCollapsible(1, True)`, `setCollapsible(0, False)`;
- on open: `setVisible(True)` then a `QVariantAnimation` drives
  `splitter.setSizes([total-w, w])` from 0 → 460;
- on close: animate w → 0, then `setVisible(False)` in the `finished` slot;
- the animation duration is 0 under the `offscreen` platform so headless tests
  and screenshots get the deterministic end state.

`tests/gui/test_main_window.py` locks this: the table's width/height must track
the central `contentsRect` within 3 px after show, after resize, and after the
detail panel opens and closes again.

### What else changed

| Priority | Change |
|---|---|
| P1 | `app.qss` rewritten as a real design system: 4/8/12/16/24 spacing scale, a type scale (`#H1/#H2/#Section/#Muted`), explicit hover/focus/selection/disabled states for every widget class, 40 px row height, card-style table, styled scrollbars/menus/tooltips/docks. `theme.py` palettes reworked and contrast-checked (a test asserts WCAG-AA for body + secondary text and ≥3:1 for state colours in both themes). New `icons.py` — theme-aware `qtawesome` (mdi) icons on every sidebar row, every toolbar action (directional glyphs mirrored for RTL), and the row indicator columns via `DecorationRole`. Row **state colour-coding**: `BackgroundRole` washes each row (overdue 20 %, blocked 16 %, due-soon 14 %, waiting 10 %) plus coloured `due` text and strike-through/dim for completed. |
| P2 | Toolbar split into **two rows** — quick-add on its own full-width row, filter + controls below. Actions clustered with separators: filter · group-by (now a clearly labelled "گروه‌بندی بر اساس" dropdown) · undo · ‖ · theme toggle / settings / console (icon-only, tooltips). The confusing "پوسته:" combo became a single moon/sun **toggle** button. The filter field is the only expanding widget so it never truncates; it carries the full query as a tooltip and shows the start when unfocused, the caret end when focused. |
| P3 | Status bar rebuilt: a pure-Persian permanent count (`«۳ کار · اقدامات بعدی»`, Persian digits, zero Latin), a green/red `Taskwarrior آماده است` / `یافت نشد` label, and a separate transient busy line (`⟳ …`). `test_main_window.py` asserts the **exact** rendered count string and that it contains no Latin letters. |
| P4 | "گزارش‌ها و نمودارها" moved directly under the quick-views (was buried below tags/contexts), given the chart icon, bold + larger type, and separator gaps above and below. |
| QA | `setMinimumSize(940×620)`; sidebar moved to an explicit right dock (RTL); empty states for every quick view (designed Persian copy centred in the table); hover/focus/selection states via QSS; detail panel + console got the full QSS treatment; `HighDpiScaleFactorRoundingPolicy.PassThrough`; compact Jalali date pickers (in-field clear button, buttonless time spin) so the detail form fits 460 px without clipping. |

Screenshots after the pass: `docs/` is text-only, but the reviewer received the
dark/light list, detail panel, long-filter, empty-state, console and placeholder
captures.

### Row state precedence

`TaskTableModel._row_state` returns exactly one state per task; when a task
matches several, the first match in this order wins (and drives the row tint,
the `due`/description text colour, and the indicator-icon tint):

1. **completed** — terminal; nothing else matters.
2. **waiting** — the task is deliberately hidden until its `wait` date; not
   actionable now, so this outranks urgency.
3. **blocked** — has an unmet dependency. The useful signal is "unblock this",
   which outranks "it's late": a blocked overdue task shows as blocked.
4. **overdue** — `due` is in the past (pending only).
5. **due-soon** — `due` within the configured threshold (default 3 days).
6. *(none)* — normal styling.

Indicator columns (annotation / recurrence / dependency) are independent of the
row state and always show when the field is present; their icon is tinted with
the row state colour when the state is overdue / blocked / waiting, otherwise
muted.

### Signed / structured numbers in RTL

Any value that is a hyphen- or colon-separated token or a possibly-signed
number (urgency, dates, ids, audit timestamps) is wrapped with Unicode isolate
controls (`U+2066 … U+2069`) via `jtask.rtl.bidi_isolate` before it enters an
RTL layout, so the bidi algorithm treats it as one atomic left-to-right unit
and never floats a `-` or a separator to the wrong end (e.g. urgency `-20.0`
renders `-۲۰.۰`, not `۲۰.۰-`). This is the general form of the fix first applied
ad hoc to the status-bar count; `tests/gui/test_task_model.py` and
`tests/test_rtl.py` assert the exact rendered strings.

## Later milestones (not in M1)

- **M2 — Reports & Charts**: matplotlib `FigureCanvasQTAgg` renders for burndown
  (daily/weekly/monthly), history/ghistory, summary progress; full interactive
  **Jalali calendar report** reusing `JalaliMonthGrid` with a day-density cell
  factory + click-a-day task list; projects/tags rich tables; custom `.taskrc`
  report discovery → sortable table; per-chart PNG export.
- **M3 — Power/UX**: visual filter builder (with "show equivalent raw filter"),
  drag-and-drop (task→project, task→calendar day), saved/pinned user filters,
  dependency graph view, urgency factor breakdown polish.
- **M4 — Platform**: `QSystemTrayIcon` due/overdue notifications + quiet hours,
  PyInstaller/AppImage build, `.desktop` + icon + `StartupWMClass`, README
  screenshots/GIF, first-run setup wizard.
