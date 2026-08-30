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

---

## M9 — implementation log (complete)

### Core (`taskwarrior.py`)

- `version()` (lru) — `task _version`, shown in the status bar and Diagnostics.
- `diagnostics()` — full `task diagnostics` text.
- `calc(expr)` — `task calc`, raises `TaskCommandError` on a bad expression.
- `command_reference()` (lru) — `[(invocation, description)]` parsed from
  `task help` (wrapped continuation lines re-joined).

### GUI

- **`widgets/tools_dialog.py`** — `ToolsDialog` (toolbar "؟" action) with three
  tabs: **تشخیص** (monospace `task diagnostics`, copy + save-to-file),
  **راهنمای فرمان‌ها** (searchable table from `task help`), **ماشین‌حساب**
  (wraps `task calc`; an ISO date result is annotated with its Jalali long form).
- **Status bar** now shows the detected version ("Taskwarrior 3.5.0").
- **`widgets/filter_builder.py`** extended: a "شناسه / UUID" field, an
  "الگوی شرح" regex field (wrapped in `/…/`), and a one-click **virtual-tag
  picker** (9 common tags: OVERDUE / DUE / READY / ACTIVE / BLOCKED / BLOCKING /
  WAITING / TAGGED / ANNOTATED). The raw-extras box is relabelled to say it
  takes `and`/`or`/`xor` and parentheses verbatim.

### Date-grammar regression sweep

`tests/test_date_grammar.py` (39 cases) exercises `rewrite.rewrite_args`
end-to-end: absolute Jalali (every separator + Persian digits), time-of-day,
Esfand-30 leap boundary, Persian relatives + offsets, date-math tails,
English-keyword pass-through, every `DATE_ATTRS` entry, every date modifier,
recurrence durations left untouched, description-with-colon, date UDAs
(convert only when declared), the Gregorian-mistake guard, and Jalali→Greg→Jalali
round-trip losslessness.

### M9 scope — complete

Diagnostics · Command reference · Calculator · filter-builder extensions ·
date-grammar sweep — all landed with tests + screenshots.

---

## Mission complete — M5–M9

See `docs/feature-parity-status.md` for the final report.

---

## i18n + selectable-calendar mission — Phase 0 (awaiting approval)

Full audit: `docs/i18n-phase0-audit.md`. Summary of the two decisions the mission
asked to document here:

### Translation mechanism — centralized catalog, not Qt `.ts`/`.qm`

**Decision:** a `jtask_gui/i18n.py` module with `t(key, **kw)` over TOML catalogs
(`i18n/fa.toml`, `i18n/en.toml`), **not** `QTranslator` + `.ts`/`.qm` +
`pylupdate6`/`lrelease`.

**Reasoning:** the audit found ~20 modules that build Persian label
lists/dicts **at import time** (`_STATUS`, `_PRIORITY`, `_VTAGS`, `_REPORTS`,
`_ATTR_FA`, `_STATUS_FA`, …). `self.tr()` needs a live `QObject` + installed
translator; `QCoreApplication.translate()` needs the translator installed before
the call — both unavailable at import. Every such constant would have to become a
function regardless, and once it is, the `.ts` layer buys nothing over a plain
catalog lookup. Add: ~120 f-string interpolation sites (vs. Qt's `%1`/`.arg()`),
zero existing Qt-i18n infrastructure, and the mission's own requirement that
`docs/i18n-glossary.md` be the single source of truth — a concept-keyed
Python/TOML catalog maps 1:1 to glossary rows and is diff-reviewable; generated
`.ts` XML is not. A central `i18n.py` also matches the codebase's existing
"one path" pattern (`fmt.py` for numbers, `taskwarrior.py` for TW access). The
`.ts`/Linguist tooling mainly pays off with non-developer translators, which is
not this project's situation; a catalog still scales to future languages
(`i18n/de.toml`).

### Language ⇄ Calendar are independent; both require restart

`Settings.language` (fa/en) drives UI text + **layout direction** + terminology +
font. `Settings.calendar` (jalali/gregorian) drives only date rendering/entry via
a `CalendarSystem` abstraction. Taskwarrior storage stays Gregorian/UTC. Changing
either setting **requires an app restart** (clear modal prompt) — live
retranslation across ~48 widget modules + relayout of a built tree + font swap is
high-surface, low-payoff; the existing digit-mode toggle stays live.

### Proposed milestones: i1 (glossary + catalog infra) · i2 (decouple identity
from labels) · i3 (layout direction follows language) · i4 (CalendarSystem
abstraction + shared Gregorian/Jalali grid) · i5 (English catalog + transliteration
+ digit/font defaults) · i6 (four-combination hardening + docs). Detail and
rationale in `docs/i18n-phase0-audit.md`.

Approved 2026-08-30 with four resolutions (digit-mode override flag; i1
zero-visible-change snapshot gate; theme-name migration regression test;
grep-based new-hardcoded-string gate active from i1).

---

## i1 — implementation log (complete)

- **`jtask_gui/i18n/`** — `t(key, **kw)`, `set_language(lang)`, `lang()`,
  `is_rtl()`, `missing_keys()`. Catalogs are plain Python dict modules
  (`fa.py` / `en.py`) — flat dotted keys, diff-reviewable, no TOML/YAML parser,
  no `requires-python` bump. `en.py` seeded from `fa.py` (Resolution 4); i5
  fills real translations from `docs/i18n-glossary.md`. Missing key → returns
  the key + logs once (caught by the snapshot test, never crashes).
- **`Settings.language`** (`fa`/`en`, persisted) — `app.build_application`
  calls `set_language(settings.language)` before importing `main_window`.
  Changing it in Settings shows a "restart required" prompt.
- **`Settings.digit_mode_user_overridden`** (Resolution 1) — a *separate*
  persisted flag, set the first time the user changes digit mode in Settings;
  a later language switch never rewrites the digit mode once it is set. Never
  inferred from the current value.
- **~48 widget/dialog files migrated** to `t()` — direct literals, f-strings
  (→ `t("key", n=…)`), and constant label lists whose *keys are already stable*
  (`_STATUS`, `_PRIORITY`, `_VTAGS`, `_REPORTS`, `_ATTR_FA`→key map, …). Module-
  level `t()` at import is fine under restart-required.
- **Deferred to i2** (the label==identity coupling Phase 0 flagged): sidebar
  quick-view titles, `task_table._EMPTY_MESSAGES` keys, theme names
  `شب`/`روز` (+ QSettings migration). Held at their current count by the
  ceiling gate.
- **`docs/i18n-glossary.md`** — terminology source of truth (fa · en ·
  Taskwarrior-vocab note), plus the Jalali-in-English transliteration table and
  the list of wording clean-ups i5 must make.

### Gates (both green, both stay in the suite)

- **`tests/gui/test_i18n_snapshot.py`** (Resolution 2) — renders MainWindow +
  detail panel + Settings + Add/Bulk/Export/Manager/Tools dialogs, collects
  every visible Persian *wording* string (dates/counts/names masked), asserts
  byte-identical to a committed baseline. After the full migration: **0 added /
  0 removed** vs. the pre-migration capture, except the **2 intended new
  strings** for the Language selector.
- **`tests/test_no_new_hardcoded_strings.py`** (Resolution 4) — per-file
  Persian-literal count ceiling (`tests/_i18n_string_ceiling.json`, 13 files /
  ~35 literals, all i2-deferred). Counts may only go down.

Full suite: **334 → 336 passing** (2 new gate tests), ruff + mypy clean, no
regression in the default (fa / Jalali) configuration.

---

## i2 — implementation log (complete)

Decouple every remaining "display label doubles as an identity key". Still
fa-only visually — the snapshot gate stays **byte-identical**.

- **Theme names** `شب`/`روز` → stable keys `dark`/`light`. `theme.THEMES` re-keyed;
  `theme.canonical_theme(name)` maps any stored value (incl. the pre-i2 Persian
  names via `_LEGACY_THEME`) to a live key. `Settings.theme` getter **migrates**
  a legacy value and writes it back once; setter canonicalises on write. Display
  labels via the catalog (`theme.dark` / `theme.light`) in the Settings dialog
  (now `addItem(label, key)` + `currentData()`) and the first-run wizard.
  All `theme_name="شب"` defaults → `"dark"` (6 widgets); `icons._theme`;
  `main_window` theme-switch glyph + label.
- **Sidebar quick views** — `QUICK_VIEWS` first element is now a catalog key;
  each spec carries a stable `"key"` (`today`, `week`, …) plus a localized
  `"title"`. `main_window._DEFAULT_VIEW` / the filter-results spec follow.
- **`task_table` empty states** — `_EMPTY_MESSAGES` (keyed on the Persian view
  title) replaced by `_EMPTY_KEYS` + `t(f"view.empty.{key}")`;
  `show_empty_state()` now takes the stable key, fed from `spec["key"]`.

### Gates

- **Snapshot** (`test_i18n_snapshot.py`): still **0 added / 0 removed** — the
  sidebar/theme labels render the exact same Persian.
- **String ceiling** (`test_no_new_hardcoded_strings.py`): regenerated —
  **1 file, 1 literal** (`theme.py` `_LEGACY_THEME`, which *must* hold the old
  Persian names). Every other user-facing string in the GUI now routes through
  `t()`.
- **Resolution 3** (`tests/gui/test_i2_theme_migration.py`, 7 cases): seed a raw
  QSettings `theme=شب` as a pre-i2 build would → `Settings().theme == "dark"`,
  persisted, second load stable; unknown value → default; canonical names pass
  through; labels come from the catalog.

Full suite: **336 → 341 passing**, ruff + mypy clean, no fa/Jalali regression.

---

## i3 — implementation log (complete)

Layout direction follows the **UI language only** — the calendar system never
touches it.

- **`app.build_application`** — `app.setLayoutDirection(RightToLeft if is_rtl()
  else LeftToRight)`, computed after `set_language(settings.language)`.
- **13 hardcoded `self.setLayoutDirection(RightToLeft)`** removed from the M5–M9
  dialogs (they were latent bugs — they forced RTL regardless of the app). The
  **4 `LeftToRight` overrides on monospace/code boxes** (diagnostics, stderr
  details, raw JSON) are kept — code stays LTR in both languages.
- **Sidebar dock** — `RightDockWidgetArea` (fa) / `LeftDockWidgetArea` (en).
- **Window "state" (dock layout) is namespaced by language** in QSettings
  (`win/state_<lang>`) so an fa (sidebar-right) layout is never restored into an
  en (sidebar-left) window; a pre-i3 store still loads for fa. Geometry
  (size/position) stays shared.
- **`icons._MIRRORED`** (just `undo`) is flipped 180° **only when
  `QApplication.layoutDirection()` is RTL** — un-mirrored in en.
- **Restart flow** — the Settings dialog now shows a
  «راه‌اندازی دوباره / بعداً» prompt on a language change and, on confirm,
  relaunches (`QProcess.startDetached` + `QApplication.quit`).
- **QSS** — Qt Style Sheets mirror `border-left/right`, `padding/margin-left/
  right` and border-radius corners by `layoutDirection()`, so `#Sidebar`
  `border-right`, `#DetailPanel` `border-left`, and the `#Segment[pos]` radii
  flip correctly in LTR with no change needed (verified by rendering — sidebar
  divider, detail-panel edge, and segmented-control corners all land right).

### Tests

`tests/gui/test_i3_layout_direction.py` (9): parametrized fa/en — sidebar dock
side, every migrated dialog inherits the app direction, monospace boxes stay
LTR in both, `undo` glyph mirrored only in RTL, and a grep guard that no widget
may hardcode `setLayoutDirection(RightToLeft)` again.

Full suite: **341 → 350 passing**, ruff + mypy clean. The i18n snapshot gate
(fa/Jalali) is unchanged. English still shows catalog keys until i5 —
structurally the UI is now a correct LTR layout (sidebar left, columns LTR,
dialogs LTR).

_Next: i4 — `CalendarSystem` abstraction (`Jalali` + `Gregorian`), one shared
`MonthGrid`, week-start per system, `Settings.calendar`._

## i4 — implementation log (complete)

The calendar system is now a **selectable setting, independent of language**.
Taskwarrior storage stays Gregorian/UTC; a `CalendarSystem` only decides how a
date is *shown* and how typed input becomes a Taskwarrior string.

### New module — `calendar_system.py`

- **`CalendarSystem`** ABC: `today`, `month_names`, `weekday_names_short`,
  `week_start_pyweekday` (Mon=0…Sun=6), `month_grid`, `label_ym`, `is_today`,
  `to_gregorian_date` / `from_gregorian_date`, `format_utc` / `format_local`
  (`style` = `short` / `long` / `datetime` / `time` / `gregorian`),
  `week_bounds(ref)` (concrete — first/last Gregorian date of the week per the
  system's start), `to_taskwarrior`.
- **`JalaliCalendarSystem`** — wraps `jtask.jalali`. Saturday week start. In an
  **English UI** the month/weekday names switch to the canonical Latin
  transliteration (`Farvardin`…`Esfand`, `Shanbeh`…`Jomeh`) from the glossary
  §7; digits stay ASCII. `format_*` output is byte-identical to the old
  `jalali.from_*` path in a Persian UI.
- **`GregorianCalendarSystem`** — near-passthrough. Week start from Taskwarrior's
  `rc.weekstart` (`_read_weekstart()`, default Monday). `to_taskwarrior` parses
  an absolute `Y-M-D[ H:M[:S]]` (any separator, either digit set) and passes
  everything else (`tomorrow`, `eom`, date-math) through to Taskwarrior.
- **`active()`** — one process-wide instance chosen from `Settings().calendar`
  (restart-required, like language). `set_calendar(id)` for the switch / tests.

### Shared grid + picker

- **`widgets/jalali_calendar.py`** (`JalaliMonthGrid`, alias `MonthGrid`) — now
  calendar-agnostic: takes an optional `calendar=`, delegates every calendar
  decision to it, picks nav-arrow glyphs by `layoutDirection()`. One engine for
  both systems, both the date-picker popup and the calendar report.
- **`widgets/jalali_date_picker.py`** (`JalaliDatePicker`) — stores a **Gregorian**
  `date`/`datetime` internally; renders via `active().format_local`; parses typed
  text via `active().to_taskwarrior` → `strptime` (unresolved relatives show a
  red border — use the popup). `set_value` still accepts a `jdatetime` for
  back-compat.

### Consumers routed through `active()`

`models/task_model.py` (date columns re-render from `<key>_gregorian` via
`format_utc`, ignoring reports.py's pre-formatted Jalali), `widgets/`
`history_view`, `stats_view`, `timesheet_view` (+ default range via
`week_bounds`), `detail_panel`, `tools_dialog`, `calendar_report`, and
`sidebar._this_week_filter` (week span via `week_bounds`).

`jtask/reports.py` got one **additive** change: `shape_calendar` /
`report_calendar` take `gregorian=` + `week_start=` — Gregorian year/month with
Gregorian-keyed day buckets when set, Jalali (unchanged) otherwise.

### Settings dialog

A **Calendar** combo (جلالی / میلادی) next to Language. Changing *either*
Language or Calendar now fires the restart prompt.

### Tests

`tests/gui/test_i4_calendar_system.py` (14): Jalali + Gregorian shape, Latin
names in English UI, date round-trips, `format_utc` parity with the core,
`to_taskwarrior` (absolute / relative / invalid), `week_bounds` per system,
`active()` follows `Settings().calendar`, calendar setting persists.

Full suite: **350 → 364 passing**, ruff + mypy clean. The i18n snapshot gate
gained the 3 intended Calendar-selector strings (تقویم / جلالی (شمسی) / میلادی)
and is otherwise unchanged — Persian + Jalali output is still byte-identical.

_Next: i5 — fill `en.py` from the glossary, digit/font defaults per language,
terminology + transliteration tests, wording clean-ups._

## i5 — implementation log (complete)

The **English catalog is real** and the digit default now follows the language.

### `en.py` — full override

Every key in `fa.py` (~430) has an English value, drawn from the glossary's
approved English column. Seeded from `fa.py` so a missed key degrades to Persian
(and is caught by a test), then `CATALOG.update({...})` overrides all of them.

- **Taskwarrior vocabulary, exactly** — Due / Scheduled / Wait / Until /
  Priority / Project / Tags / Annotation / Recurrence / Dependencies / Urgency /
  Context / UDA; statuses Pending / Waiting / Completed / Deleted / Recurring;
  virtual tags Overdue / Ready / Active / Blocked / Blocking / Tagged /
  Annotated; verbs Annotate / Denotate, Start / Stop timer, Purge.
- **GTD quick-views** use planning English: Today, This Week, Overdue,
  **Next Actions**, **Waiting For**, Blocked, Completed.

### Wording clean-ups (glossary §8, both languages)

- Priority unified: fa «بحرانی / متوسط / پایین», en High / Medium / Low — was
  split «زیاد/بحرانی … کم/پایین» between the detail panel and the Add/bulk
  dialogs.
- `wait` label unified to «تاریخ انتظار» / "Wait" (bare «انتظار» dropped from
  `detail.date.wait`, `col.wait`, `quickadd.preview.wait`).

These change the fa snapshot baseline (3 strings consolidated onto existing
ones) — intended, and the only fa visible-text change in i5.

### Digit mode default per language (Resolution 1)

`Settings.persian_digits` now returns the **language default** (en → ASCII,
fa → core-config default) *until* `digit_mode_user_overridden` is set — never
inferred from a stored value. The Settings dialog and the first-run wizard both
set the flag only when the checkbox deviates from that default.

Hard `jalali.to_persian_digits(...)` calls that bypassed the setting
(`history_view`, `timesheet_view`, `timer_indicator`, `quickadd`,
`calendar_system.label_ym`, `fmt.pct`'s `٪`) now route through `fmt.digits()` /
the digit-mode check, so an English UI shows ASCII digits and `%` end to end.

### Font (§7)

Vazirmatn ships a complete, well-drawn Latin set; English renders cleanly in it
(verified in the offscreen smoke run — columns, sidebar, priority/status all
legible). No second font is bundled; `app._load_fonts` is unchanged.

### Tests

`tests/gui/test_i5_english_catalog.py` (12): full key coverage, no-stray-Persian,
Taskwarrior-vocabulary spot checks, per-language priority + wait consistency,
Jalali transliteration table vs. the glossary, and the per-language digit
default incl. the override-wins case.

Full suite: **364 → 387 passing**, ruff + mypy clean.

_Next: i6 — four-combination (Language × Calendar) hardening, screenshots, docs._

## i6 — implementation log (complete) — mission done

All four **Language × Calendar** combinations verified end to end.

| Language | Calendar | Direction | Sidebar | Dates | Digits (default) |
|---|---|---|---|---|---|
| Persian | Jalali | RTL | right | `۱۴۰۵-۰۶-۱۳` | Persian |
| Persian | Gregorian | RTL | right | `۲۰۲۶-۰۹-۰۴` | Persian |
| English | Jalali | LTR | left | `1405-06-13` (Latin month names in pickers/calendar) | ASCII |
| English | Gregorian | LTR | left | `2026-09-04` | ASCII |

Taskwarrior storage stays Gregorian/UTC in every combination.

### Fixes found by the four-combination pass

- **`JalaliCalendarSystem.format_utc/format_local`** now run their result through
  `fmt.digits()` — `jtask.jalali` always emits Persian digits, so an English UI
  (or an explicit ASCII choice) was showing Persian digits in the detail panel
  and history. Now consistent with the task table.
- **Date-picker placeholder** is calendar-neutral: `t("datepicker.placeholder",
  example=…)` where the example is today in the active system
  (`CalendarSystem.example_input()`), so a Gregorian UI no longer shows a Jalali
  example.

### Tests

`tests/gui/test_i6_four_combinations.py` (16, parametrized over the 4 combos):
layout direction follows language only; window chrome is in the right language;
the Due column renders in the active calendar's year range; the shared
month-grid's month names are transliterated (en+Jalali) / native
(Gregorian) / Persian (fa+Jalali). The `combo` fixture saves and restores
language, direction, active calendar and digit mode so it can't leak.

Full suite: **387 → 403 passing**, ruff + mypy clean. The fa/Jalali visible-text
snapshot is unchanged bar the i5 consolidations.

### Where each setting lives

- `Settings.language` (`fa`/`en`) — interface text + layout direction. Restart
  required.
- `Settings.calendar` (`jalali`/`gregorian`) — date display + input parsing.
  Restart required.
- `Settings.persian_digits` — follows the language until the user picks
  explicitly (`digit_mode_user_overridden`); live toggle, no restart.
- Catalog: `src/jtask_gui/i18n/{fa,en}.py`, one flat dotted namespace, driven by
  `docs/i18n-glossary.md`. New user-facing strings go through `t()` — the
  `tests/test_no_new_hardcoded_strings.py` ceiling guards against regressions.
- Calendar logic: `src/jtask_gui/calendar_system.py` (`active()` is the one
  process-wide instance).

The Raw Command Console remains the escape hatch; its input still rewrites
Jalali date tokens regardless of the selected calendar.

---

# Mission "d" — Design-system standardization

After a full visual audit (design-token source + ~98 screenshots, both themes).
The colour system was already sound; spacing / typography / radius existed only
as a header comment, and had drifted across dialogs added in different
milestones. Two "bugs" from the audit were **screenshot-script artifacts, not
real defects** — dialogs forced to an oversized `resize()` looked empty; a
phrase-gated Purge button looked grey because it was correctly *disabled*.

Milestones **d1–d7** (approved 2026-08-31, 4 resolutions):
d1 token foundation · d2 Python layout sweep + elevation · d3 dialog/form
standards · d4 toolbar · d5 terminology + widget fixes (priority بحرانی→بالا,
dep-graph nodes, bidi paths) · d6 toast + empty-state consistency · d7 docs
(`docs/design-system.md`) + corrected screenshots + regression.

Cross-cutting: pure presentation, zero behavioural change, full suite green at
every milestone. Deliberate documented exceptions to "zero visual change":
the d1 ≤2 px spacing normalisations (below) and the d5 priority wording.

## d1 — implementation log (complete)

The spacing / type / radius scale is now **code, not a comment**, and enforced.

### `jtask_gui/tokens.py` (new) — the single source of truth
- **spacing** `SPACE = (2,4,6,8,10,12,14,16,20,24)` — a curated 2-px ladder;
  token name carries the value (`SP_8` = 8, `@sp_8@` in QSS).
- **radius** `RADIUS = {sm:6, md:8, pill:9, lg:12}`.
- **type** `FONT_SIZE = {h1:22, title:16, lg:15, body:14, h2:13, xs:12}` —
  values are **what actually renders today** (see `#H2` below).
- **elevation** — documented convention (`surface` fill + 1-px `border`; a soft
  drop shadow via `tokens.shadow(widget)` for free-floating overlays only,
  since QSS can't render shadows). *Defined* in d1; *applied* in d2.
- `qss_tokens()` returns the `@name@ → "Npx"` map.

### `theme.render_qss()` — extended
Substitutes `{**tokens.qss_tokens(), **palette(name)}`, so `@sp_*@` / `@fs_*@` /
`@r_*@` fill alongside the colour tokens. `template_text()` unchanged.

### `app.qss` — fully tokenised
Every `padding` / `margin` / `spacing` / `font-size` / `border-radius` now reads
a token. Only `0` / `1px` / `2px` (border + hairline widths) remain as bare
lengths.

**Dead-rule removal (Resolution 1):** `QLabel#H2` was declared twice — `17px`
at the top and `13px` in the M6 block. Qt's cascade means the later rule always
won, so **every `#H2` has rendered at 13 px since M6**; the 17-px rule was dead
code. Removing it changes nothing on screen. The type scale records `h2 = 13`.

**Spacing normalisations (documented exception, all ≤2 px, internal padding
only):** button / input / quick-add / table-row vertical padding `7→8` and
`9→8`; table-header vertical `10→12`; menu-item `7px 22px → 8px 24px`; badge
`3→4`; tooltip `5px 9px → 4px 8px`; History/Stats/Manager cell padding `3→4`,
`5→4`; a few `border-radius` `5→6` / `7→8`. Net effect: dialogs grow 2–14 px in
height (Settings +14, from ~7 input rows × +1 px padding each). Before/after
screenshots below; the shell is pixel-identical bar 1-day data drift.

### Guard — `tests/gui/test_qss_uses_tokens.py` (new, 5 tests)
Fails if a raw px value appears in a scale property, if a full selector is
declared twice (the dead-rule class of bug), if a declared token is unused, or
if a rendered value lands off-scale. Modelled on `test_chart_text.py`.

### Chart-palette drift fixed
`jtask_gui.theme.DEFAULT_CHART_PALETTE` (unused by any GUI chart — they colour
series by palette role) is replaced by `CHART_SERIES_ROLES` naming that mapping.
The CLI keeps its own `jtask.themes.DEFAULT_CHART_PALETTE` for plotext.

### Incidental test-infra fix
`tests/gui/_i18n_util.normalize_for_snapshot` masked weekday names shortest-first,
so `«شنبه»` (Saturday) inside `«یک‌شنبه»` left a `یک‌` fragment — the snapshot
flaked whenever the run day ≠ capture day. Now longest-first; baseline
regenerated (1 line, collapses a duplicate mask — no app change).

### Evidence
Full suite **407 passing** (403 + 4 new), ruff + mypy clean. Snapshot &
hardcoded-string ceilings green. Natural-size screenshots both themes: shell,
shell+detail, toolbar, Sync / Settings / Error / first-run / Purge / Add-Task.

_Next: d2 — Python layout sweep (~118 call sites / ~32 files) + elevation
application; split d2a/d2b with per-half evidence (Resolution 2)._
