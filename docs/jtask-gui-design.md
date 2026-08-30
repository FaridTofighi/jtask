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

## Milestone 2 — Reports & Charts (delivered)

`src/jtask_gui/widgets/reports_view.py` replaces the M1 placeholder as central
stack index 1. A report picker rail (right, RTL) + a content area with a
per-report toolbar (period toggle, ghistory bar-mode toggle, PNG export).

| Report | Widget | Notes |
|---|---|---|
| Burndown | `charts/burndown_chart.py` | stacked bars done / started / open per Jalali day\|week\|month, `report_burndown(period)` |
| Ghistory | `charts/history_chart.py` (mode `ghistory`) | stacked bars added / completed / deleted |
| History | same widget (mode `history`) | grouped bars |
| Summary | `charts/summary_view.py` | per-project `QProgressBar` + open / overdue counts (not matplotlib) |
| Calendar | `calendar_report.py` | **reuses `JalaliMonthGrid`** with a task-density cell factory; click a day → that day's task list in the side panel; `«` `»` month nav |
| Projects / Tags | `table_reports.py` | sortable `QTableWidget`; double-click a row emits `filterRequested` → the main task list opens filtered |

- **matplotlib**: `charts/mpl_base.py` — `QtAgg` backend, bundled Vazirmatn
  registered with the font manager, `ThemedChart` restyles figure/axes/text
  from the palette on every theme switch, `export_png()`. Empty data → a Persian
  message on the axes, never a crash.
  **Persian text handling — corrected after M4 review** (see next section).
- **Filter-aware**: the main filter bar propagates to every report
  (`ReportsView.set_filter`); the calendar also re-queries per month.
- **Stale-response guard**: `ReportsView._gen` / `CalendarReport._gen` — a
  monotonic token captured per async load; a late worker result whose token is
  stale is dropped, so fast report/period/month switching can't leave an older
  response painted over a newer one. Regression test in `test_reports_view.py`.
- `jdatetime` month grid now renders Persian digits in the title and default
  cells.
- Custom `.taskrc` report discovery → sortable table: **deferred to M3**

### M2 fix pass

- **`jtask_gui/fmt.py`** is now the single number-formatting path for the whole
  GUI (`num`, `pct`, `digits`) — respects the active digit mode (synced to the
  global `jtask.rtl` state at startup and on settings change) and can wrap a
  token in bidi isolates. Every user-facing number routes through it: status
  count, task-model cells, Summary percentages, **matplotlib axis ticks** (a
  `FuncFormatter` in `charts/mpl_base.py`, so both axes on every chart), and the
  **Projects/Tags report cells**.
- The Projects/Tags tables were showing ASCII digits because
  `QTableWidgetItem` collapses `EditRole` onto `DisplayRole`; replaced with a
  `_NumItem` that displays the formatted string and sorts on a stored float.
- **`SegmentedControl`** (`widgets/segmented.py`) replaces the period and
  history-mode `QComboBox`es: a single-choice button row with an explicit
  checked/active style, so the current granularity (روزانه/هفتگی/ماهانه) and
  bar mode (انباشته/گروهی) are always visible, not hidden inside a closed combo.
- Light-theme reports view confirmed: figure/axes/chrome all repaint from the
  palette on theme switch (pixel-checked `#ffffff` content, `#f5f7fa` chrome).
  (needs parsing arbitrary report column specs; not blocking).

## Milestone 3 — Power / UX (delivered)

**Core** (`taskwarrior.py`, `reports.py`):
- `taskwarrior.report_specs()` — `report.<name>.*` parsed from `_show`.
- `taskwarrior.urgency_terms(uuid)` — the contribution table from `task info`
  (`{label, coefficient, weight, value}`).
- `reports.run_custom_report(name, filter)` — renders a `.taskrc` report as
  `{columns, labels, rows}`, Jalali dates, display modifiers stripped.

**GUI**:
| Feature | Where |
|---|---|
| Visual filter builder | `widgets/filter_builder.py` — project / +tags / -tags / status / priority / due-before / due-after (Jalali pickers) / raw extras. Shows the equivalent raw string with a copy button; emits Taskwarrior-ready tokens. Opened from a button on the filter bar. |
| Saved / pinned filters | `settings.py` (`save_filter`/`saved_filters`/`delete_filter`); a `★` button on the filter bar prompts for a name; sidebar **«فیلترهای ذخیره‌شده»** section lists them, click → apply. |
| Drag-and-drop | `TaskTable.startDrag` emits `application/x-jtask-uuids`. `Sidebar` project rows accept the drop → `task <uuids> modify project:X`. `CalendarReport` day cells accept the drop → `task <uuids> modify due:<greg>`. |
| Dependency graph | `widgets/dep_graph.py` — `QGraphicsView`: blockers (red) → this task (primary) → dependents (muted), curved edges; embedded in the detail panel, theme-aware. |
| Urgency breakdown | detail panel `«چرا؟»` toggle → `taskwarrior.urgency_terms` off-thread → each term with its Persian-digit contribution. |
| Custom `.taskrc` reports | `ReportsView.discover_custom_reports()` appends non-built-in report names to the rail; `widgets/generic_report.py` renders `run_custom_report` output as a sortable table. |

10 M3 GUI tests + 5 core tests; 172 total green.

## Milestone 4 — Platform (delivered)

- **Notifications** — `notifications.py`: `QSystemTrayIcon` + `NotificationManager`.
  Polls `report_next` off-thread, classifies overdue / due-today / due-soon,
  batches, de-dups per uuid, honours quiet hours (past-midnight wrap) and a
  configurable interval. Tray menu (show/hide, quick-add, quit); close-to-tray
  while notifications are on.
- **First-run wizard** — `first_run.py`: theme / Persian digits / Vazirmatn
  check / notifications opt-in, shown once (`settings.wizard_done`).
- **Settings** — full notification prefs; `widgets/fa_spinbox.py` renders
  Persian digits in the dialogs.
- **Desktop integration** — bundled `icon.svg` + rasterised PNGs,
  `app.setDesktopFileName("jtask-gui")` for `StartupWMClass` / Wayland app-id;
  `packaging/` has the `.desktop` file, a PyInstaller spec, `build-appimage.sh`
  and `install-desktop.sh`. `python -m jtask_gui` entry point.

## M4 review fix — Persian text on matplotlib charts

**The M2 note "matplotlib ≥ 3.6 shapes + bidi-reorders Persian natively, no
arabic-reshaper needed" was wrong** and is retracted here.

matplotlib shapes/reorders Arabic script **only when it was built against
libraqm** (`matplotlib.ft2font.__libraqm_version__` is non-empty). The PyPI
wheels on this dev machine were — hence the M2/M3 chart screenshots looked
correct here (verified by zooming into the shipped screenshot: the title reads
`نمودار سوختن (Burndown)`, correctly joined and ordered). On an install **without**
raqm (stripped wheel, old version, a PyInstaller bundle that drops the shared
lib) the *same code* renders raw Persian reversed and unjoined —
`نتخوس رادومن` — which is what the review screenshot showed.

**Unconditionally** reshaping (as the review first proposed) is also wrong: on a
raqm-present install matplotlib would then shape an already-reshaped string and
double-mangle it — producing exactly the same garble. Proven both ways with a
render comparison.

**Fix — capability-aware, matplotlib-only:**

- `charts/mpl_text.py::fa(text)` — applies the digit mode, then reshapes +
  bidi-reorders **only when `MPL_SHAPES_ARABIC` is false**; otherwise passes the
  string through for matplotlib to shape. Correct in both environments.
- **Never used in the Qt layer** (Qt always shapes natively — M1 rule).
- **Structurally enforced**: chart code may not call matplotlib's raw text API.
  `mpl_base.py` exposes `set_title_fa` / `set_xlabel_fa` / `set_ylabel_fa` /
  `set_xticklabels_fa` / `legend_fa` / `text_fa` (each routes through `fa()`),
  plus `category_tick_formatter`. `tests/gui/test_chart_text.py` greps every
  chart module and fails if `ax.set_title(` / `set_xlabel` / `legend(` /
  `ax.text(` etc. appear directly.
- Applied to burndown and history/ghistory (all modes, all periods): title,
  axis labels, x-tick labels, legend, empty-state text. The numeric y-tick
  `FuncFormatter` (digit mode) is unchanged.
- `export_png()` re-renders the same `Figure` object → identical text pipeline.
- The M3 dependency graph switched from `QGraphicsSimpleTextItem` to
  `QGraphicsTextItem` (full Qt text-document engine) so node labels are
  unambiguously shaped/bidied by Qt.

12 chart-text tests + updated dep-graph tests. Sweep for `drawText(` /
custom `QPainter` text across the whole GUI: only `dep_graph.py`, now on the
full text engine.

## Post-M4 fixes — four bugs

**Bug 1 — dependency-graph empty state overflowed the panel.** The "no
dependencies" state was a `QGraphicsTextItem` in the scene; with only that one
tiny item, `scene.itemsBoundingRect()` was ~200×20 and `fitInView()` (which
scales *both* ways) magnified it ~15× to fill the view. Fix: the empty state is
now a plain `QLabel` overlaid on the viewport and sized to it on
`resize`/`show`/relayout — never a scene item. Separately, `_fit()` now calls
`resetTransform()` whenever `fitInView` would magnify (`m11() > 1`), so a small
graph is shown at 1:1 instead of blown up.

**Bug 2 — saved filters could not be renamed/deleted.** Added a
`customContextMenu` on the sidebar's saved-filter rows: «تغییر نام» (→
`QInputDialog`, `Settings.rename_filter`) and «حذف» (→ `QMessageBox`
confirmation, `Settings.delete_filter`). Both persist immediately and repopulate
the sidebar.

**Bugs 3 & 4 — settings / onboarding not persisting.** Root cause investigation:

- QSettings persistence itself was **verified working** on the reference
  machine (`~/.config/jtask/jtask-gui.conf`, native format); a fresh `Settings`
  instance reads back exactly what a prior one wrote, for every setting.
- **The actual bug (Bug 3): the first-run wizard only recorded completion
  (`settings.wizard_done = True`) inside its `_finish()` slot, which runs only
  when the user clicks «شروع».** Closing the wizard any other way — window ✕,
  Esc, Alt-F4 — left the flag `False`, so it re-appeared on every launch. And a
  re-shown wizard, clicked through, re-writes `theme` / `persian_digits` /
  `notifications_enabled` from its own (simpler) controls, which is how it also
  surfaced as "settings show defaults" (Bug 4): the settings *dialog* reads and
  writes correctly — verified by test — but the wizard was silently
  overwriting a subset of the same keys on each restart.
- **Fixes**: `app.build_application` now sets `settings.wizard_done = True`
  unconditionally after `wiz.exec()` returns, however it closed. `settings.py`
  also calls `QCoreApplication.setOrganizationName/setApplicationName` at import
  time (belt-and-braces for any stray bare `QSettings()`), and the
  `wizard_done` / saved-filter setters now `sync()` on write so a hard kill
  can't lose them. `Settings` continues to use the explicit
  `QSettings("jtask", "jtask-gui")` pair, which is independent of the running
  app's name.

`tests/gui/test_persistence.py` now does a real "restart" check (write with one
`Settings`, read with a fresh one) for a dialog value, the wizard flag, window
geometry, columns and saved filters, plus a within-session dialog-reopen check.

---

# Feature-parity mission — Phase 0 (audit + plan, awaiting review)

Goal: bring jtask-gui to genuine native coverage of Taskwarrior's important
capabilities (not "covered because the console can run it"), with **zero
regression** to M1–M4 and the Raw Console kept **permanently** as the escape
hatch.

## Architecture as it stands (audit)

**Two packages, one repo:**

- `src/jtask/` — framework-agnostic core. `taskwarrior.py` is the *only* place
  that shells out to `task` (`run` / `command` / `add` / `export` /
  `passthrough` + cached `_show`/`_projects`/`_tags`/`_udas`/`_context`/
  `_reports` lookups + `report_specs` + `urgency_terms`). `reports.py` shapes
  `task export` JSON into GUI-ready structures. `jalali.py` / `rewrite.py` do
  the Jalali↔Gregorian layer. `errors.py` = `JtaskError`.
- `src/jtask_gui/` — PyQt6. `app.py` bootstraps (RTL, bundled Vazirmatn, theme,
  icon, wizard gate). `main_window.py` orchestrates. `workers.py` =
  `QThreadPool`+`TaskRunnable`, the single off-thread path with
  `finished/failed` signals. `fmt.py` = the single number/digit formatter.
  `theme.py` = one QSS template + palette per theme. `settings.py` = `QSettings`
  wrapper (persisted, restart-tested). `icons.py` = theme-aware qtawesome.

**Every `task`-executing call site** (audited): `main_window` (add / done /
delete / start / stop / modify / annotate / denotate / undo / context /
drag-drop modify), `command_console` (`taskwarrior.run` raw), `reports_view` +
`calendar_report` + `notifications` + `detail_panel` (read-only `reports.*`).
Nothing bypasses `taskwarrior.py`.

**UI surfaces today:** main window shell (RTL sidebar / task table / slide-in
detail panel / two-row toolbar / status bar / tray), quick-add, raw+visual
filter, Reports & Charts (burndown / history / ghistory / summary / Jalali
calendar / projects / tags / discovered custom reports), command console,
settings dialog, first-run wizard.

**Console-only capabilities right now** (the parity gap): `append`, `prepend`,
`duplicate`, `log`, `purge`, `edit`, `import`, user-facing `export`, `sync`,
`config`, full `context` management, `calc`, `stats`, `diagnostics`, `help`,
`timesheet`, per-field history, most built-in reports, UDA-definition
management, non-date filter modifiers / regex / boolean grammar in the builder.
Full list with target milestones: `docs/taskwarrior-feature-matrix.md`.

**Test baseline:** `QT_QPA_PLATFORM=offscreen pytest -q` → **205 passed**,
`ruff` + `mypy` clean. Deps all present (PyQt6 6.11, matplotlib 3.11 *with
libraqm*, jdatetime 6, arabic-reshaper, python-bidi, qtawesome, pytest-qt).
Taskwarrior **3.5.0**.

## Feasibility resolutions

Both open questions resolved in `docs/taskwarrior-feature-matrix.md` §Feasibility:

- **Per-field history** — *real data available*: `task <id> information` emits a
  `Date | Modification` change log (`Priority changed from 'M' to 'H'` etc.).
  History tab parses it; no fabricated diff.
- **Timesheet** — *feasible without Timewarrior* (which is **not installed**):
  the same modification log records `Start set` / `Start deleted (duration:…)`
  pairs = a retroactive per-session history from Taskwarrior's own data. Plus
  the live `start` for the current timer. Timewarrior is *detected*, not
  assumed, and used as an optional richer source if present.

## Proposed milestone breakdown (M5–M9) — for review before any code

Each milestone: its own review, its own screenshots (final-only, per view/theme),
full existing suite green + new tests, feature-matrix rows flipped to
Implemented/Partial with honest notes.

### M5 — Task-lifecycle command parity (no new "manager" screens)
`append` · `prepend` · `duplicate` (show new id/uuid, refresh) · `log` dialog ·
`purge` (hard confirm + exact count) · undo preview ("N operations will be
reverted") + GUI confirm · full **Add Task dialog** (all fields, reuses pickers/
recurrence/deps) · **bulk** priority / tag +/− / status / project / wait-due
changes with affected-count · GUI-enforced confirm layer that ignores the
user's `rc.confirmation`/`rc.bulk`. *Touches:* `taskwarrior.py` (a few verbs),
`main_window`, `task_table` context menu, new small dialogs. *Lowest risk,
highest parity-per-line.*

### M6 — Task insight: History · Raw Data · Statistics · Timesheet · timer
Detail panel gains tabs — **History** (modification-log parse, Jalali),
**Raw Data** (read-only `task <uuid> export` pretty-printed), keep
Details/Dependencies/Annotations as first-class tabs. New **Statistics** view
(from `task stats` + export breakdowns, charts reuse `mpl_base`/`fa()`).
New **Timesheet** view (session parse + current timer + totals). Task table +
detail show a **running-timer** indicator with elapsed time. *Touches:*
`detail_panel` (tabify), new `reports.task_history()` / `reports.timesheet()` in
core, new views.

### M7 — Data safety: Import / Export / Sync
**Export dialog** (JSON | Taskwarrior format, filter | all, destination, preview
count). **Import dialog** (file picker, format detect, preview + count,
validate, confirm, run via `task import`). **Sync Manager** (async, idle/
running/success/failed, last-sync time, retry, no concurrent runs, auto-refresh
after; detects whether sync is configured, else points at Config Manager).
*Touches:* `taskwarrior.py` (`sync` / `import` / `export` wrappers), new
toolbar/status controls, new dialogs.

### M8 — Configuration surface: Config · Context · UDA · Reports managers
All writes via `task config` only — never `.taskrc` text.
**Configuration Manager** (current / default / overridden per `rc.*`, grouped:
confirmation, dates, weekstart, default command, hooks, sync, verbosity,
aliases, colors). **Context Manager** (list/create/edit/delete/activate, show
read+write filters, active context shown prominently). **UDA Manager** (CRUD
definitions, type→widget map, validation). **Reports Manager** (run any
fixed/custom report; edit columns/labels/sort/filter/dateformat for *custom*
reports; **never overwrite** a user's existing definition without explicit
confirm). *Touches:* `taskwarrior.py` (`config` read/write helpers, richer
report-spec parse), several new manager views.

### M9 — Power tools + filter grammar + docs
**Diagnostics** view (`task diagnostics` / `information` / `version`, readable,
copyable, exportable). **Command Browser / Help** (from installed `task help`,
send-to-console). **Calc** panel (wraps `task calc`). **Filter builder**
extensions: regex, `and/or/xor`+parens (or clearly defer to the raw box),
id/uuid field, virtual-tag picker, UDA filters, more `.modifier`s. Date-grammar
**regression test sweep** (absolute / relative / today-tomorrow-yesterday /
math / before-after / due-scheduled-wait-until / recurrence anchors / date
UDAs). Final status report + matrix/compat docs finalised.

## Deferred / console-only by design (documented, not gaps)

`execute` (arbitrary shell), `news`, `logo`/`colors`, `task edit` (`$EDITOR`),
undo-of-a-specific-past-change, per-variable config *source path*. The Raw
Console stays **permanently** — future Taskwarrior versions, power-user syntax,
custom hooks/reports, and anything M5–M9 doesn't grow a control for.

**STOP — awaiting review of this milestone breakdown before implementation.**

---

## M5 — implementation log (in progress)

Approved 2026-08-28. Landing per-feature with screenshots + tests, not one batch.

### Cross-cutting infrastructure (done)

- **Real error surfacing (§23).** `jtask.errors.TaskCommandError` carries
  `returncode` / `stderr` / `cmd` + `.details()`. `taskwarrior.run()` raises it
  on any non-zero exit. Removed `rc.verbose=nothing` from the shared `_RC`
  overrides — it was silencing Taskwarrior's own error text; machine-output
  callers (`export`, `_lines`, `urgency_terms`) now pass `run(..., quiet=True)`.
  Workers deliver the **exception object** (signal is `pyqtSignal(object)`),
  never a flattened string.
- **`widgets/error_dialog.py`.** Human message on top; `$ cmd` + exit code +
  stderr behind a "نمایش جزئیات فنی" disclosure (monospace, LTR, no-wrap);
  buttons «رونوشت جزئیات» (clipboard) and «باز کردن کنسول» (reveals + focuses
  the Raw Console). `main_window._error` accepts any object, shows details only
  for `TaskCommandError`.
- **`widgets/confirm.py` — GUI-enforced confirmation layer.** `confirm(...)`
  → bool. Shows exact affected **count** (Persian digits, custom noun),
  danger-styled button when `destructive`, and a type-the-phrase **hard
  confirmation** (`require_phrase`) for purge. Independent of the user's
  `rc.confirmation` / `rc.bulk` (jtask always forces both off so `task` never
  prompts) — this dialog is the only, constant gate.
- **`widgets/op_status.py`.** Status-bar indicator with
  idle / running / success / failed / cancelled; success + cancelled auto-fade,
  failed persists to the next op. Replaces the old plain busy label; wired
  through `_begin_busy` / `_end_busy` / `_write` / `_on_load_error`.

### Verbs

- **`undo` preview (broad — every undo, not only post-bulk).**
  `taskwarrior.undo_preview()` runs `task undo` with confirmation on + answers
  "no" (state untouched), returns `{text, count, empty}`. `_undo()` fetches the
  preview async, and for a non-empty result shows the confirm dialog with the
  operation count + raw revert diff as details before running the real
  `task undo`. Empty → status message, no dialog.

### Task-table context menu — lifecycle verbs (done)

`widgets/task_table.py` gained `selected_tasks()` (full dicts) and intent
signals: `duplicateRequested` / `appendRequested` / `prependRequested` /
`purgeRequested` / `bulkEditRequested`. Menu now:
انجام‌شده · حذف · تکثیر · ویرایش گروهی… · افزودن/پیش‌افزودن به شرح… ·
شروع/توقف زمان‌سنجی · پاک‌سازی برای همیشه… (only shown when any selected row is
`status:deleted`).

- **delete** now routes through `confirm(destructive, count)` before running.
- **duplicate** — 1 task → `taskwarrior.duplicate()` (parses `Created task
  <uuid|id>`) and the status bar shows the new identifier; N tasks →
  `command(uuids,"duplicate")`.
- **append / prepend** — `QInputDialog` for the text, `command(uuids, verb,
  [text])`; bulk (>1) gets a confirm.
- **purge** — `taskwarrior.purge(filter)` (returns "Purged N" count); hard
  confirm (`require_phrase="پاک‌سازی"`) + count; only deleted UUIDs passed.
- **bulk edit** — `widgets/bulk_edit.py` `BulkEditDialog`: priority
  (`SegmentedControl`: — / H / M / L / حذف), project (editable combo), add-tags
  / remove-tags line edits, and due / scheduled / wait rows (Jalali picker +
  "پاک‌کردن" checkbox). `mods()` emits **only touched fields**; dates come back
  Gregorian so the caller skips `rewrite_args`. `>1` task → confirm with the
  mod list + count.

### Full Add Task dialog + Log completed task (done)

`widgets/task_form.py` `TaskFormDialog(mode="add"|"log")` — one form for both.
Fields: description (required), project (editable combo), tags
(`TagChipEditor` + completions), priority (`SegmentedControl` — / H / M / L),
due / scheduled / wait / until (`JalaliDatePicker`, time on due+scheduled),
recurrence (`RecurrenceBuilder`, hidden in log mode), depends (`_DependsField`
= line edit + "افزودن…" picker over `report_next`). `_revalidate()` disables
OK + shows a hint when description is empty or recurrence is set with no due.
`args()` emits Gregorian-ready tokens → handed straight to `taskwarrior.add`
/ `taskwarrior.log` (no `rewrite_args`). Two toolbar actions on row 2:
«افزودن کار…» (Ctrl+Shift+N) and «ثبت کار انجام‌شده…».

### M5 scope — complete

append · prepend · duplicate · log dialog · purge (hard confirm + count) ·
undo preview (broad) · full Add Task dialog · bulk priority / tag / project /
date · GUI-enforced confirmation layer · real error surfacing · visible async
op-state — all landed with tests + screenshots. Deferred by note: single-cell
inline table edit, bulk annotate, back-dating a logged task's `end`,
`until` in the bulk dialog.

---

## M6 — implementation log (in progress)

### Core parsing (framework-agnostic, TDD)

- **`src/jtask/history.py`** — `parse_information(text) → InformationReport`
  (`attributes`, `changes: list[ChangeEntry]`, `sessions: list[Session]`).
  The `Date | Modification` block is one timestamp per transaction (blank on
  continuation lines); every `ChangeEntry` keeps the exact `raw` line.
  `Session`s come from `Start set to '<ts>'` / `Start deleted (duration: <d>)`
  pairs; an unclosed `Start set` → `running`. `parse_duration` handles
  `'N days, H:MM:SS'`.
- **`src/jtask/timesheet.py`** — `build(filter, since, until) → Timesheet`:
  export tasks `modified.after:<since>` (+ `+ACTIVE`), parse each one's
  `information`, clip sessions to the window, group by task, roll up
  `by_project` / `by_day` / `total`. Per-task `information` calls capped at 300
  (`truncated` flag). Timewarrior is **not** required.
- **`taskwarrior.information(spec)` / `taskwarrior.stats(filter)`** helpers;
  `jalali.from_local(value, fmt)` for the local timestamps that `information`
  emits (`short` / `long` / `datetime` / `time` / `gregorian`).

### GUI

- **Detail panel is now a `QTabWidget`** (`_detail_host`): «ویرایش» (the existing
  form, untouched) / «تاریخچه» / «دادهٔ خام». `_show_detail` loads all three.
- **`widgets/history_view.py`** — `TaskHistoryView`: anchors line
  (ایجاد / آخرین ویرایش / پایان), then a day-grouped tree of changes rendered as
  Persian sentences (`describe()`), date-typed values shown Jalali, the raw
  Taskwarrior line on hover. Start/Stop get dedicated wording
  («زمان‌سنجی آغاز شد …» / «… متوقف شد — مدت …»).
- **`widgets/raw_data_view.py`** — `RawDataView`: the task's stored JSON
  (jtask's derived `*_gregorian` keys stripped), monospace LTR, copy button.
- **`widgets/stats_view.py`** — `StatsView` in the Reports rail as «آمار»:
  `task stats` as a two-column table, Persian category labels, ISO dates → Jalali,
  units/percent localised, respects the active filter.
- **`widgets/timesheet_view.py`** — `TimesheetView` in the Reports rail as
  «برگهٔ زمان»: Jalali از/تا range (defaults to the current Jalali week),
  task→sessions tree, running marker, جمع کل + per-project summary, honest
  "بازسازی‌شده از تاریخچهٔ Taskwarrior" note (mentions Timewarrior when present).
- **`widgets/timer_indicator.py`** — status-bar pill: `▶ <desc>  H:MM:SS` (or
  `▶ N کار فعال` when several), a 1 s `QTimer` ticks the elapsed time, click →
  `stopRequested(uuid)`. Fed from `export(["+ACTIVE"])` on every `refresh_all`.

_Next in M6: nothing outstanding for the milestone's stated scope — History /
Raw Data / Statistics / Timesheet / timer indicator all landed._

---

## M7 — implementation log (complete)

### Core (`taskwarrior.py`, TDD in `tests/test_data_io.py`)

- `export_text(filter, *, array=True)` — raw `task export` text; `array` toggles
  `rc.json.array` (indented array ↔ newline-delimited objects).
- `import_file(path)` → `{added, modified, total, stdout}` (counts `add` / `mod`
  lines + the "Imported N tasks" tally).
- `sync_status()` → `{configured, kind: remote|local|None, target}` from
  `rc.sync.server.url` / `.origin` / `rc.sync.local.server_dir` / `.server`.
- `synchronize()` → `task sync` stdout, raises `TaskCommandError` on failure.
- `import-v2` is **not** wrapped — it is the legacy `*.data` migration path,
  not a JSON importer.

### GUI — a «داده» toolbar menu (خروجی / ورود / همگام‌سازی)

- **`widgets/export_dialog.py`** — `ExportDialog(current_filter)`: scope
  (`SegmentedControl` all / current / custom) × format (indented array /
  JSON lines), destination picker (default `~/jtask-export-<jalali>.json`),
  live "N کار برای خروجی" count (generation-guarded). `write_export(spec)`
  writes the file and returns `{path, bytes, count, when}`.
- **`widgets/import_dialog.py`** — `ImportDialog`: file picker; `inspect_import()`
  (pure, tested) detects array vs JSON-lines vs invalid, returns count + sample;
  OK enabled only for a valid file; warns that same-UUID tasks are updated.
  `main_window._open_import` runs `taskwarrior.import_file` async and reports
  added / modified.
- **`widgets/sync_dialog.py`** — `SyncManagerDialog(settings)`: reads
  `sync_status()` async; unconfigured → explanation + pointer to the (M8)
  Config Manager, button disabled; configured → kind + target + last-sync
  (Jalali, from `Settings.last_sync`), a run button that disables itself while
  running (no concurrent runs), stores the timestamp and emits `synced` →
  `refresh_all` on success.

### M7 scope — complete

Export dialog · Import dialog · Sync Manager — all landed with tests +
screenshots. `Settings.last_sync` added (persisted).

---

## M8 — implementation log (complete)

### Core (`taskwarrior.py`, TDD in `tests/test_config_surface.py`)

All writes go through `task config` / `task context` — `.taskrc` text is never
touched.

- `config_names()` (lru) — `task _config`, ~245 known variables.
- `config_defaults()` (lru) — parses `task show` (no arg): a `<name>  <value>`
  row followed by `  Default value <d>` ⇒ *name* is overridden → `{name: d}`.
- `config_set(name, value)` / `config_unset(name)` — the latter tolerates
  "No entry named …" (exit 2) as a no-op.
- `context_list()` — `[{name, read, write, active}]`; parser is
  indentation-independent (jtask strips lines) and mirrors read→write when the
  write filter is blank.
- `context_define(name, read, write="")` / `context_delete` / `context_activate`.
- `uda_set(name, attr, value)` / `uda_delete(name)` (unsets every `uda.<name>.*`).
- `report_set(name, attr, value)`; `BUILTIN_REPORTS` frozenset.

### GUI — one «مدیریت Taskwarrior» dialog (toolbar action, 4 tabs)

- **`widgets/config_manager.py`** — searchable, group-filtered table
  (name / current / default), overridden rows bold + tooltip; double-click →
  `_EditDialog` with «ذخیره» / «بازگردانی به پیش‌فرض» (reset is confirmed).
- **`widgets/context_manager.py`** — table + add / edit / activate / deactivate
  / delete (delete confirmed); `_ContextDialog` notes the separate-write-filter
  version caveat.
- **`widgets/uda_manager.py`** — table + `_UdaDialog` (name / label / type
  [string·numeric·date·duration] / values / default); delete confirmed with a
  "data is kept" warning.
- **`widgets/report_manager.py`** — every report with type (داخلی/سفارشی);
  custom reports fully editable; editing a **built-in** offers a same-name
  override only after an explicit confirm — a user's own report is never
  silently clobbered.
- **`widgets/manager_dialog.py`** — `QTabWidget` host; each tab's `changed`
  bubbles up → `main_window.refresh_all`.

### M8 scope — complete

Configuration Manager · Context Manager · UDA Manager · Reports Manager — all
landed with tests + screenshots.
