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

## d2 — implementation log (complete)

Every `setContentsMargins` / `setSpacing` in the GUI now references
`jtask_gui.tokens` (imported as `tok`), and dialogs are a distinct raised
surface.

### d2a — shell + views + small widgets (commit `bf16c1d`)
15 non-dialog widget files converted: `SP_*` consts + the semantic tuples
`INSET_NONE / INSET_TIGHT (8) / INSET_PANEL (14) / INSET_DIALOG (16)`.
`calendar_report` day-cell dot `font-size 11→12` via `FS_XS`. Zero-value
margins stay literal `0, 0, 0, 0`. No elevation (the shell isn't "raised").
Shell / detail / reports pixel-unchanged.

### d2b — dialogs + elevation + colour tokens
- **Sweep:** 17 dialog / manager files converted. Dialog root margins
  `(18,16,18,14)` / `(16,14,16,12)` → `INSET_DIALOG` (uniform 16); a few
  `(14,12,14,12)` → `INSET_PANEL`.
- **Elevation (the one chosen approach — surface + border, not shadow):** new
  palette role `elevated` (dark `#1e222a`, a visible lift off the `#16181d`
  window; light `#ffffff`, neutral — leans on the OS window frame). `QDialog`
  and its plain container widgets paint `@elevated@`; inputs keep `@field@`
  (now reads as a recessed well) and buttons keep `@surface@` (reads as
  raised). `tokens.shadow()` helper stays defined for future free-floating
  overlays but nothing applies it yet. Documented follow-up: a deeper
  light-theme lift needs a base-tone shift.
- **Colour tokens:** `#fff` ×3 in `app.qss` → new `on_danger` role (white on
  the red danger/chip surfaces, both themes). The date-picker's inline
  `#d1242f` invalid border → a QSS state rule `QLineEdit[invalid="true"]
  { border-color: @overdue@ }` toggled via `_set_invalid()` + repolish. **No
  hardcoded colour remains anywhere** outside `theme.py` (new guard test).

### Tests
`test_qss_uses_tokens.py` gains `test_no_hardcoded_colours_in_template`.
Full suite **408 passing** (407 + 1), ruff + mypy clean. Dialog screenshots
(both themes): Add-Task, Sync, Settings, Delete-confirm, Manager, Export —
inputs/controls now layer correctly on the raised dialog surface.

_Next: d3 — dialog sizing guard test; first-run `QFormLayout`; validation-timing
helper (no validation on a pristine dialog); `#Danger:disabled` tint._

## d3 — implementation log (complete)

Dialog and form standards, and the guard tests that keep them.

### §2 — dialog sizing (confirmed non-bug, now guarded)
`tests/gui/test_d3_dialog_form_standards.py`: no dialog file calls
`self.setFixedHeight` / `setMinimumHeight` / `setFixedSize` / `setMinimumSize`
(none did — the audit's "empty space" was the screenshot script forcing an
oversized `resize()`), plus a runtime check that Sync / Settings / Error /
Confirm sit within 40 px of their content `sizeHint`.

### §3 — first-run wizard form layout
Rewritten onto a `QFormLayout` with right-aligned labels beside their controls,
exactly like the Settings dialog — was a stack of right-floating `#Section`
headers above each control. Test asserts the wizard contains a `QFormLayout`.

### §6.1 — no validation on a pristine form
`TaskFormDialog`: `_revalidate()` no longer runs at construction. Split into
`_problems()` (pure) · button enable/disable (live, a disabled submit is the
pristine signal) · `_show_problems()` (the red hint — shown **only** after a
submit attempt via `_try_accept`, or after the description field is left empty
after being touched). Tests: pristine form → hint hidden + OK disabled; after
`_try_accept` → hint shown. Grep guard: no widget calls
`self._(re)validate()` in `__init__`. Snapshot baseline loses the now-absent
`«شرح کار الزامی است.»` (deliberate).

### §6.2 — gated destructive button still reads as destructive
`QPushButton#Danger:disabled` — was fully neutral grey; now greyed fill with a
red edge and red label, so the phrase-gated Purge button still signals danger
while it waits for the confirmation word.

### Evidence
Full suite **415 passing** (408 + 8 new − 1 snapshot line), ruff + mypy clean.
Screenshots both themes: first-run (form layout), pristine Add-Task (no error),
Purge (red-edged disabled button).

_Next: d4 — toolbar grouping + flat overflow menu (Resolution 3), tooltip
audit (test), icon-consistency pass._

## d4 — implementation log (complete)

Row-two of the main toolbar, regrouped as it outgrew a single flat run.

### Grouping
`filter · | · group · | · create (add-full, log) · | · undo · | · data ▾ · | ·
view (theme, console) · | · config (settings, ⋯)` — separators between every
cluster (the guard test asserts ≥ 4).

### Flat overflow (Resolution 3)
The two rarely-used dialog entry points — **Manage Taskwarrior** and
**Diagnostics & tools** — moved behind a `⋯` `QToolButton` (InstantPopup, one
level, no submenu). Neither had a keyboard shortcut, so nothing regressed;
`_manage_action` / `_tools_action` keep their handlers and are reachable in one
extra click. Settings and the Console toggle stay directly on the bar (Settings
is frequent; the Console toggle needs its visible checked state).

### Tooltips
`action.settings.tip` (“Appearance · language · calendar · notifications”) and
`toolbar.more.tip` added — Settings previously had a tooltip identical to its
label. Guard test `test_d4_toolbar.py`: every toolbar control (actions, the two
menu buttons, every flat-menu entry) has a non-empty tooltip; Settings / Manage
/ Tools tooltips differ from their labels.

### Icons
The icon set is already uniform (`qtawesome` `mdi.*`, mostly `-outline`). One
mismatch fixed: `tools` was `mdi.help-circle-outline` → `mdi.wrench-outline`
(it opens Diagnostics, not help). New `more` → `mdi.dots-horizontal`.

### Evidence
Full suite **420 passing** (415 + 5), ruff + mypy clean. Snapshot regenerated
(the overflow menu makes the Manage / Tools labels render as menu text, + the
two new tooltip strings). Toolbar + flat `⋯` menu screenshots captured.

_Next: d5 — priority بحرانی→بالا + glossary + baselines; dep-graph node sizing;
bidi-safe paths._

## d5 — implementation log (complete)

### §5 — priority terminology (reverses an i5 choice)
`priority H` fa **«بحرانی» → «بالا»** across all five key families
(`priority.*`, `detail.*`, `fb.*`, `quickadd.*`, `col.*`); en stays "High".
"بحرانی/Critical" implied a fourth level Taskwarrior doesn't have.
`docs/i18n-glossary.md §1` + §8 updated; fa snapshot regenerated (one line).
Guard: `test_d5` asserts «بالا»/"High" everywhere and no "بحرانی"/"Critical"
in any priority value.

### §7 — dependency-graph node text
`_node()` now draws a `QGraphicsSimpleTextItem`, one line, `elidedText(…,
ElideRight, _W − 2·SP_8)` — the label can never spill past the rounded-rect
border. The full `#id  description` is the item's tooltip (hover). Node radius
tokenised (`R_MD`).

### §8 — bidi-safe LTR-structured strings in RTL
`bidi_isolate()` now wraps: the Sync Manager's server **path/URL**
(`_show_status`) and its last-sync timestamp, and the export "saved to {path}"
status toast. Guard checks the path sits between `U+2066…U+2069` in the
rendered line.

### Evidence
Full suite **424 passing** (420 + 4), ruff + mypy clean.

_Next: d6 — toast/snackbar for positive non-destructive feedback;
empty-state consistency pass._

## d6 — implementation log (complete)

### Toast (`widgets/toast.py`)
A non-blocking `QFrame#Toast` — one per main window, reused. `surface` fill +
`border` + `EmptyState`-sized text with a check glyph, floating bottom-centre
just above the status bar, opacity-fade in, auto-dismiss after 2.6 s.
`WA_TransparentForMouseEvents` + `NoFocus` — it never blocks input and never
asks a question. Wired at the one mutation funnel `_write()` (so every
successful non-destructive command confirms) plus `_save_filter` /
`_rename_filter`; the status-bar message stays as the persistent complement.
**Destructive actions keep their blocking `confirm()` dialog** (guard test).
Elevation is surface+border, not a shadow — a widget holds one `QGraphicsEffect`
and the fade needs the opacity one.

### Empty-state consistency
Every "no data" fallback now uses the one designed look (`#EmptyState` /
`#DepEmpty`), not a bare `#Muted` label: `summary_view` empty (was `#Muted`),
and `timesheet_view` gained a real centred `#EmptyState` label (was overloading
the summary line). Guard test greps for bare empty-state labels.

### Catalog
`msg.filter_saved` / `msg.filter_renamed` added (fa + en).

### Evidence
Full suite **430 passing** (424 + 6), ruff + mypy clean. Snapshot regenerated
(the timesheet empty label is now a persistent widget). Toast screenshot
captured.

_Next: d7 — `docs/design-system.md`, corrected natural-size screenshots of every
touched screen (both themes), final regression._

## d7 — implementation log (complete) — mission done

- **`docs/design-system.md`** written: the nine enforced conventions (tokens,
  colour/elevation, destructive colour, validation timing, toast, empty states,
  toolbar, RTL/bidi, terminology) each with its guard test. This is the
  reference future milestones follow.
- **Corrected screenshots** (`natural size`, both themes) captured for every
  screen the mission touched: shell, shell+detail, toolbar, toast, Add-Task
  (pristine), Purge, Sync Manager, Settings, Error, first-run, dependency
  graph. The audit's original set was distorted by a screenshot-script
  `resize()`; these are the accurate reference.
- **Regression:** full suite **431 passing**, ruff + mypy clean. The
  fa/Jalali visible-text snapshot changed only where a milestone deliberately
  changed wording or added a widget (documented per milestone); the
  no-hardcoded-string ceiling held throughout.

### Mission "d" summary

| milestone | commit | what |
|---|---|---|
| d1 | `ea33e25` | `tokens.py` + QSS tokenised + guard; dead `#H2` rule removed |
| d2a | `bf16c1d` | shell/view/widget layout → tokens |
| d2b | `fd239fd` | dialog layout → tokens; elevation (`elevated` role); colour tokens |
| d3 | `777b561` | dialog sizing guard; first-run `QFormLayout`; validation timing; danger-disabled |
| d4 | `5f04c8c` | toolbar grouping + flat `⋯` overflow + tooltip audit + icons |
| d5 | `885fa6b` | priority بحرانی→بالا; dep-graph node elision; bidi-safe paths |
| d6 | `afa4f58` | non-blocking toast; empty-state consistency |
| d7 | *(this)* | `docs/design-system.md`; corrected screenshots; regression |

Suite 407 → **431**. Deferred, as agreed: a deeper light-theme elevation
(base-tone shift); §9.2 cross-panel animation consistency (the detail panel is
still the only slide-in). The two "bugs" the audit surfaced — dialog empty
space, grey Purge button — were confirmed to be screenshot-script / correct
disabled-state artifacts, and are now guarded against regression anyway.

---

# Verifiability + deferred-gaps mission (2026-08-31)

Prompted by "many milestones seem not implemented". A full scan found the
opposite — **every milestone above is implemented, wired, and tested** — but two
real problems:

## Phase A — the suite could not run here

- **`pytest-qt` was absent** → ~250 GUI tests errored at setup
  (`fixture 'qapp' not found`); `test_m4.py::test_app_icon_loads` built a
  `QIcon` with no `QGuiApplication` and Qt `abort()`ed the whole run.
- Fixes: `tests/gui/conftest.py` now ships minimal `qapp` / `qtbot` stand-ins
  used **only when `pytest-qt` is missing** (so the suite is self-sufficient);
  `test_app_icon_loads` requests `qapp`; `pyproject.toml` pins
  `qt_api = "pyqt6"` (installing `pytest-qt` pulls in PySide6, whose older
  `libQt6Core` otherwise breaks `import PyQt6`); `docs/ENVIRONMENT.md` records
  the assumed stack (Taskwarrior ≥ 3.5, matplotlib + libraqm, PyQt6-only);
  `tests/test_environment.py` skips — not fails — below Taskwarrior 3.5 and
  records the active chart-text path.
- With the deps present: **`pytest -q` → 431 passed**, exactly matching the
  historical claim.
- **Restart crash fixed.** Confirming the language/calendar restart aborted with
  `RuntimeError: wrapped C/C++ object of type _Signals has been deleted` — a
  pooled worker outlived the event loop and touched a freed signal object.
  Three-part fix: (1) `workers.TaskRunnable.run` guards the whole emit path
  (reaching `self.signals.<name>` raises just like `.emit()` on a torn-down
  sip wrapper) and swallows `RuntimeError` — nothing is listening by then;
  (2) `workers.shutdown()`, wired to `app.aboutToQuit`, drains the pool and the
  event queue before exit; (3) `NotificationManager.stop()` sets a `_stopped`
  flag so a pending `QTimer.singleShot` first-poll can't schedule a worker
  after the drain. Regression: `tests/gui/test_shutdown.py`.
- **`qt.qpa.services … Could not register app ID: Connection already associated`
  fixed.** Two causes: (a) the identity (`setApplicationName` /
  `setOrganizationName` / `setDesktopFileName`) was set **after** the
  `QApplication` was constructed, so Qt re-registered the app-id with
  `xdg-desktop-portal` on an already-associated connection — now set once,
  before construction, at the top of `build_application`; `settings.py` only
  fills a gap and never re-sets; (b) the restart spawned a second overlapping
  process — replaced with a re-exec (`app.request_restart()` → flag + `quit()`,
  `main()` → `os.execv` after `app.exec()` returns; one process, one fresh
  D-Bus connection, no window flash). A Qt message handler
  (`_install_qt_message_handler`) routes Qt logs to the `jtask_gui.qt` logger
  and drops this specific benign line as a backstop across Qt versions.
- **English sidebar was stuck on the right.** Root cause: if the user switched
  language and closed the window *without* restarting, `closeEvent` saved the
  still-RTL dock layout into the *new* language's `win/state_<lang>` bucket, so
  the next launch restored the sidebar on the wrong edge. Two-part fix:
  `MainWindow` records `_built_language` and `closeEvent` saves the window state
  under that (not the freshly-picked one); and `_restore_state` now calls
  `_enforce_sidebar_side()` after `restoreState`, which re-docks the nav sidebar
  to the reading-start edge for the current language (right = RTL/fa,
  left = LTR/en) — self-healing any already-poisoned state. Regression:
  `test_i3_layout_direction.py` (stale-layout + close-after-switch cases).
- **Description text now follows its own direction.** Previously every
  description rendered RTL because the view forced it. Now the base direction
  comes from the text's first strong character: "Meeting with Arash" reads
  LTR/left-aligned, "جلسه با آرش" RTL/right-aligned, in both UI languages.
  `jtask.rtl.first_strong_dir` / `auto_isolate` (FIRST STRONG ISOLATE) +
  `_AUTO_DIR_KEYS` in the table model; `jtask_gui.bidi.bind_auto_direction`
  flips the description / annotation / quick-add line edits per keystroke.
  Tests: `tests/test_bidi_direction.py`, `tests/gui/test_auto_direction.py`,
  `test_task_model.py::test_description_direction_follows_content`.

## Phase B — the genuinely deferred sub-features, now built

| # | feature | where |
|---|---|---|
| B1 | Settings: `task` binary / `TASKDATA` / `TASKRC` overrides + column reset | `settings.py`, `settings_dialog.py`, `app._apply_taskwarrior_overrides` |
| B2 | `until` row in the bulk-edit dialog | `widgets/bulk_edit.py` |
| B3 | **collapsible group headers** in the task table | `models/group_proxy.py` (`GroupProxyModel`), `widgets/task_table.py` — flat path unchanged; the proxy is only bound while a group-by is active |
| B4 | dedicated **Annotations tab** + **bulk annotate** | `widgets/annotations_view.py` (4th detail tab), `task_table` context menu → `_annotate_bulk`; the edit form keeps a read-only summary |
| B5 | recurrence-template browser | `reports.recurring_templates()`, "از الگوی موجود…" in `widgets/task_form.py` |
| B6 | typed **UDA rows** in the filter builder | `widgets/filter_builder.py` — per-type control (string/enum/numeric+op/date+op) → `name[.mod]:value` tokens |
| B7 | **send-to-console** from the M9 command reference | `command_console.prefill()`, `tools_dialog` button → `main_window._send_to_console` |
| B8 | **Hook Manager** (5th Manager tab) | `taskwarrior.hooks()` / `hook_set_enabled()`, `widgets/hook_manager.py` — list + enable/disable + reveal; editing stays console/`$EDITOR` |
| B9 | light-theme base-tone shift (real elevation); motion policy documented | `theme.py` (`_RUZ.bg → #f3f5f9`), `docs/design-system.md` §2 + new §10 |

Each landed with tests in the matching `tests/gui/test_m*.py` / core file; the
fa/Jalali i18n snapshot was regenerated only for the intended new strings; the
no-hardcoded-string ceiling held. Suite **431 → 449 passed** (+1 skipped:
the Taskwarrior-version guard on this 3.4.1 box).

Still out of scope (console-only by design, unchanged): `execute`, `news`,
`colors`/`logo`, `task edit`, undo-of-a-specific-past-change, per-variable
config source path, a structured boolean filter builder. Not built:
cross-session persistence of collapsed-group state (retained within a session).

---

# Mission "m" — visible UI modernization

> **Process note (added retroactively, after the mission-d and mission-m
> audits).** Unlike every other body of work in this project (M1–M9, the i18n
> mission, mission d), mission "m" did **not** go through Phase 0 → proposed
> scope → explicit approval → per-milestone evidence. It was applied directly
> from informal conversational suggestions ("modernize the UI"), in a single
> squashed commit (`7240e69`) bundled with unrelated work, and added **zero
> guard tests of its own**. A confirmed regression it introduced (the per-cell
> selection border, `78e88de`) was found only by accident while chasing an
> unrelated bug, which prompted a full retroactive audit — findings below.
> **Going forward, no implementation work proceeds without proposal → explicit
> approval → implementation with evidence, regardless of how small the ask.**

Mission **d** standardized the design system but was deliberately invisible.
Mission **m** made a visible pass. **As originally applied** (`7240e69` +
`78e88de`) it did the following — but see the resolution table just below;
several of these were reverted after the audit:

- **Palette (`theme.py`).** Both palettes rebuilt as `bg < bg_alt < surface <
  elevated` elevation layers; **accent re-toned teal → blue** *(reverted to
  teal)*; new `border_soft` / `primary_soft` / `focus` roles *(kept)*.
- **`app.qss` rewrite.** Table: no zebra *(restored)*, `primary_soft` selection
  + a `border-left` per-cell bar *(reverted → `paintEvent` bar)*, `bg_alt`
  header *(kept)*. Toolbar bg `→ @bg@` *(reverted to `@bg_alt@`)*. Combo /
  menu-button arrows hidden *(reverted)*. `elevated` menus/tooltips/toast, new
  `#Primary:disabled` rule, focus rings *(kept)*.
- **Toolbar (`main_window.py`).** Dropped the three `QLabel:` prefixes *(kept —
  controls self-describe)*.
- **Task table (`task_model.py` / `column_spec.py`).** `status` blank for
  `pending` *(reverted)*; tag `#` prefix dropped *(reverted)*; `id`/`urgency`
  muted + `priority` colour-coded *(kept, now tested)*; `_halign` per-direction
  alignment *(kept — genuine fix)*; column widths *(kept)*.
- **Sidebar (`sidebar.py`).** Muted section captions + non-interactive
  saved-filter hint *(kept)*; active nav row full-bleed → soft tint and
  `#ReportsEntry` de-boxed *(pending review)*.

## Mission "m" — retroactive audit + resolution

Full line-by-line audit of the mission-m slice of `7240e69` + `78e88de`, held
to the mission-d evidence standard, followed by a per-item resolution
(accepted 2026-08-31, corrective pass `a420774` + this one). Suite after the
corrective pass: **479 passed / 1 skipped** (baseline 478 + the one new
`_foreground` test; the skip is `test_environment.py` on Taskwarrior 3.4.1 —
a Phase-A guard, unrelated). All prior-convention guard tests still pass.

**Legend:** *reverted* = restored to the mission-d baseline · *keep* =
genuine improvement, no change · *keep+test* = kept with new guard coverage ·
*pending* = awaiting a screenshot-based decision, not yet changed.

| Area | Change mission "m" made | Resolution | Evidence |
|---|---|---|---|
| `app.qss` inputs | `QComboBox::down-arrow { image: none }` — every combobox lost its dropdown arrow | **reverted** (`a420774`) | rule removed → d7 default arrow; `SettingsDialog` render |
| `app.qss` toolbuttons | `QToolButton::menu-indicator { image: none }` — menu tool-buttons lost the ▾ caret | **reverted** (`a420774`) | rule removed |
| `app.qss` table | `QTableView::item:selected { border-left: 2px solid @primary@ }` → per-cell boxed grid | **reverted** (`78e88de`) | `test_task_table_selection.py` (7) |
| `theme.py` palette | Accent **teal → blue** (`#6cc7dd`/`#0a6e8f` → `#6ea8fe`/`#3565d0`) | **reverted to teal** | `theme.py` `_SHAB`/`_RUZ` `primary`/`primary_hi`/`primary_fg`/`focus`; `primary_soft` recomputed as a teal wash; `test_theme.py` 6/6 (contrast + parity) |
| `theme.py` palette | New `border_soft` / `primary_soft` / `focus` roles | **kept** (they now derive from teal) | in both palettes; used in QSS |
| `app.qss` + `task_table.py` | Zebra striping dropped (`alternate-background-color` was already inert — `setAlternatingRowColors(False)` since the reviewed M1 remediation `7e6f59f`, **not** mission m — see note) | **restored** — `setAlternatingRowColors(True)` + new `row_alt` palette role | screenshot: zebra + selection accent bar together, both themes |
| `column_spec._status` | Returned `""` for `pending` | **reverted** — shows the real value (`Pending` / `در جریان`) | `column_spec.py`; screenshot |
| `column_spec._tags` | Dropped the `#` prefix (`#work` → `work`) | **reverted** — `#` restored (Taskwarrior convention, same principle as d5) | `column_spec.py`; screenshot |
| `app.qss` toolbar / status bar | bg `@bg_alt@` → `@bg@` (blended into the window) | **reverted** — `@bg_alt@` + a bottom rule; the toolbar is a distinct region again | `app.qss`; screenshot |
| `app.qss` buttons | `#Primary:pressed` / `#Danger:pressed` lost the distinct `@accent@` press colour, orphaning the `accent` role from the QSS | **reverted** — both restored to `@accent@`; `accent` is QSS-used again (+ `CHART_SERIES_ROLES`) | `app.qss` |
| `task_model._foreground` | `id`/`urgency` muted, `priority` colour-coded (H→`overdue`, M→`due_soon`, L/none→`text_muted`) | **kept + test** | `test_task_model.py::test_foreground_muting_and_priority_colours` |
| `task_model._halign` | Per-column alignment follows layout direction (was `AlignRight` for everything — wrong for LTR/English) | **kept** — genuine fix, closed an i3 gap | `test_task_model.py::test_description_direction_follows_content` |
| `main_window` toolbar | 3 `QLabel:` prefixes removed; `_group_combo.setMinimumWidth(150)` | **kept** | `test_d4_toolbar.py` 5/5; fields self-describe via placeholder |
| `column_spec.py` widths | id 60→56, description 320→340, project/tags 140→130, **priority 80→96** (fixes "Mediu…"), urgency 80→84, status 90→96 | **kept** | diff |
| `app.qss` elevation | Card surfaces `@bg@`→`@surface@`, dividers `@border@`→`@border_soft@`, menus/tooltips/toast `@surface@`→`@elevated@` | **kept** — consistent elevation layers | `test_qss_uses_tokens.py` 5/5 |
| `app.qss` buttons | **new** `QPushButton#Primary:disabled` rule — a disabled primary button now looks disabled | **kept** | d3's `test_pristine_add_task_form_has_no_error` still passes |
| `sidebar.py` | Section captions `text_muted` + `letter-spacing 105%`; saved-filter hint non-interactive + muted | **kept** | diff |
| `tests/gui/_i18n_util.py` | Snapshot normaliser masks absolute paths (`‹path›`) — Hook Manager driven (Phase B) | **kept** | `test_i18n_snapshot.py` passes; verified it only masks `~/.taskrc` in 2 catalog strings |
| `app.qss` sidebar | Active nav row `@primary@` full-bleed → `@primary_soft@` tint + bold text; **`#ReportsEntry` de-boxed** (lost its `surface` fill + border) | **pending** — screenshot submitted for review (M2 gave this entry deliberate extra weight; not reverted or kept pre-emptively) | `sb_{dark,light}_strip.png` — normal / quick-view-active / reports-active |
| — | **Mission m added zero guard tests.** `_halign` got incidental coverage from a bidi test only; `_foreground` and `_status` had none; `test_task_table_selection.py` exists only because `78e88de` fixed a regression found by chance. Now: `_foreground` covered (`test_foreground_muting_and_priority_colours`), `_status` reverted so no longer a concern. | **process finding** — for the record | — |

**Note on zebra striping.** The M1 design doc specified alternating rows, and
M1 initially shipped `setAlternatingRowColors(True)` (`c642f15`). The **reviewed
M1 visual/UX remediation pass** (`7e6f59f`) flipped it to `False` in favour of
per-row *state* colour washes (overdue / blocked / due-soon / waiting). So
zebra was off well before mission m — mission m only deleted the already-inert
`alternate-background-color` declaration. Per the accepted resolution it has
now been turned back **on** (with a dedicated subtle `row_alt` role); the model
state-washes still layer on top and the selection accent bar sits above both.

**Not touched by mission m (verified):** every Taskwarrior verb, the `_RC`
overrides, `taskwarrior.run()`, the detail-panel `_save()` diff-and-modify
path, all `report_*` / `shape_*`. The new `taskwarrior` functions in `7240e69`
(`hooks*`, `tag_count`/`rename_tag`/`remove_tag`) are Phase B / tag management,
each with tests.

**Not touched by mission m (verified):** every Taskwarrior-facing verb
(`add`/`modify`/`done`/`undo`/`purge`/`export`/`sync`/`config`/`context`), the
`_RC` overrides, `taskwarrior.run()`, the detail-panel `_save()` diff-and-modify
path, and every `report_*` / `shape_*` in `reports.py`. Mission m's own slice is
presentation-only; the new `taskwarrior` functions in `7240e69`
(`hooks*`, `tag_count`/`rename_tag`/`remove_tag`) belong to Phase B / tag
management and each carries tests (`test_config_surface.py`, `test_tag_ops.py`).

## Sidebar tag management

The sidebar Tags section is now a management surface, not just a filter list
(matching how project rows already accept drops):

- **Add** — drop selected task rows onto a tag → `task <uuids> modify +<tag>`
  (`Sidebar.tasksDroppedOnTag` → `main_window._add_tag_to`).
- **Rename / remove across every task** — right-click a tag →
  `taskwarrior.rename_tag(old,new)` / `remove_tag(tag)` (a scoped
  `status.not:deleted +<tag> modify …`), guarded by the standard `confirm()`
  dialog with the affected `tag_count`. Unused tag → a no-op toast.

Per-task tag editing (the detail-panel chip editor, quick-add `+tag`, the
bulk-edit add/remove rows) is unchanged. Core: `taskwarrior.tag_count` /
`rename_tag` / `remove_tag` (`tests/test_tag_ops.py`); GUI wiring in
`tests/gui/test_m3.py`.

## Sidebar project management

Right-click a project row (proposed → approved: "B + hard confirm"):

- **Rename project…** — `QInputDialog` for the new name → a standard
  `confirm()` with the affected count → `taskwarrior.rename_project(old,new)`.
  The **sub-hierarchy is preserved**: a task in `Work.Admin` lands in
  `Client.Admin`. Per-task `modify` so the dotted structure survives (a bulk
  `modify project:X` would flatten it).
- **Delete project and its sub-tasks…** — a **hard** `confirm()`:
  `destructive=True`, the exact affected count, *and* a type-the-project-name
  gate (`require_phrase=name`, same as `purge`) → `taskwarrior.delete_project`.
  A normal `task delete` — **reversible with `task undo`**, not `purge`.

Both scope to `( project.is:<name> or project:<name>. )` +
`status.not:deleted` — the exact form matters: a bare `project:Work` filter is a
prefix match and would also hit `Workshop`. An empty / unknown project → a
no-op toast. Core: `taskwarrior.project_task_count` / `delete_project` /
`rename_project` (`tests/test_project_ops.py`); GUI in `tests/gui/test_m3.py`
(`test_sidebar_project_context_menu_signals`,
`test_main_window_project_management_flow`).

### Project colour (proposed → approved: "curated palette + raw field; sidebar dot only")

- **Set colour… / Clear colour** on the same project context menu.
- **Store:** Taskwarrior's own `color.project.<name>` config, written via
  `task config` — so a raw `task` shell with colour on picks it up too. jtask
  reads it back with `taskwarrior.project_colors()` and clears the `_show`
  cache on write. Core helpers `set_project_color` / `clear_project_color`
  (empty value → clear); `tests/test_project_ops.py`.
- **Picker** (`widgets/project_color_dialog.py`): a grid of ~14 curated named
  TW colours **plus** a free-text "Taskwarrior colour" field for power users
  (`bright red`, `color5`, `rgb520`, `gray10`, `<fg> on <bg>` …). Clicking a
  swatch fills the field; a live preview dot; **Clear colour** unsets.
- **Render:** sidebar only — a filled swatch dot replaces the folder glyph on a
  coloured project row. `tw_color.to_hex()` is a best-effort parse of the
  common TW colour forms (named / `bright` / 256-cube / grayscale / `rgbRGB`);
  an unparseable string still stores, it just shows no dot
  (`tests/test_tw_color.py`). The task **table is deliberately not tinted** —
  keeping the colour a lightweight sidebar cue, not a second row-state channel
  competing with due/priority/blocked.
- GUI: `test_sidebar_project_colour_menu_and_dot`,
  `test_main_window_project_colour_flow` in `tests/gui/test_m3.py`.

## Row-selection rendering fix

Two reported defects in the selected-row appearance:

1. **Per-cell boxed grid.** The mission-m QSS put `border-left: 2px solid
   @primary@` on `QTableView::item:selected`, so *every* cell in the row drew
   that border → vertical divider lines between cells. Fixed: the selection
   rule is now `background-color` only. The single leading-edge accent bar is
   painted once per row in `TaskTable.paintEvent` (`_bar_x()` = left in LTR,
   right in RTL), so it can never render as a per-cell border. `TaskTable`
   gained `set_theme()` to keep the bar colour in sync (wired in
   `_apply_theme`).
2. **Selection extended past `Status` into blank cells.** Those were the three
   separate `annotations` / `recur` / `depends` indicator columns (empty
   headers, 36 px each) trailing the row. Merged into **one** `indicators`
   column placed right after `description` — the model composites the 1–3
   present marker icons into a single pixmap (`_decoration`). `status` is now
   the last visible column; the selection band ends exactly there.

`tests/gui/test_task_table_selection.py` (7): no `border` in the selection
QSS, accent bar on the correct edge per direction, `status` is last with no
empty-header trailing column, selection extent matches the visible-column
range with a default *and* a reduced column set. Suite 478 passed / 1 skipped.

## Active context now actually filters (2026-09-01)

**Bug:** switching context in the sidebar changed nothing visible. Root cause:
Taskwarrior's `task export` command **ignores the active context** (every
*report* honours `report.<name>.context`, but `export` is not a report and has
no such switch). jtask reads everything through `task export`, so context only
ever affected *new* tasks (via the write filter, which `task add` applies for
free).

**Fix (core, approved "both CLI & GUI; backups stay complete"):**
`taskwarrior.context_read_filter()` returns the active context's `read` filter
(`context.<name>.read` from `_show`), `shlex`-tokenised, `lru_cache`d and
cleared by `refresh_lookups` + `context_activate`. `export()` / `export_text()`
gained `apply_context=True`: when a context is active the filter becomes
`( <read filter> ) <caller filter>`. A context-scoped export that errors on an
exotic filter retries once unscoped and logs — a read never hard-fails.

- **Opt-out:** `export_dialog.write_export` + its count calls pass
  `apply_context=False` — a backup file must stay complete regardless of
  context (matches `task export`'s own semantics; the dialog's filter field
  still scopes deliberately).
- **Reach:** `reports.py` calls `export()` throughout, so the task list, every
  GTD/report view, and the sidebar **Projects** / **Tags** lists all scope
  now — CLI included (matches how `task next` / `task projects` already behave).
  Project/tag *autocomplete* lists (`_projects` / `_tags`) stay unscoped.
- `_change_context` now routes through `taskwarrior.context_activate` (was a
  raw `run(["context", …])`), which also tolerates `task context none`'s
  exit-2 when nothing is active.

**Tests:** `tests/test_context_filtering.py` (6) — export scoping, caller-filter
AND, `apply_context=False` bypass, reports honour context, no-context no-op,
quoted-value tokenisation, cache-clear on switch;
`tests/gui/test_m3.py::test_main_window_context_switch_scopes_the_task_list`.
Suite **513 passed / 1 skipped**.

---

# Mission "n" — UI/UX modernization

Approved 2026-09-01 ("implement all P stages"). The review found the shell was
*competent but flat*: one-of-two-greys everywhere, no spatial hierarchy, an
invisible selection, a misplaced-emphasis status bar, and a long
undifferentiated glyph toolbar. Three stages, each its own commit with tests +
screenshots:

- **n1 — shell restructure (P0):** structure & clarity.
- **n2 — density & polish (P1):** density toggle, row content, refined light
  palette, focus ring, toolbar grouping.
- **n3 — modern features (P2):** command palette (Ctrl/Cmd-K), skeleton
  loaders, motion vocabulary.

## n1 — implementation log (complete)

**Framed content card.** The central widget is now a `QWidget#ContentFrame`
with a `SP_10` gutter of window `@bg@` around `_content`, so the task table /
reports read as an elevated card (`@surface@` + 1 px `@border@` + `@r_lg@`)
distinct from the chrome — previously the table butted flush against the
sidebar and toolbar with no separation. `tests/gui/test_main_window.py`
`_central_avail` subtracts the frame margin.

**Sidebar edge.** `QTreeWidget#Sidebar` gained `border-right: 1px solid
@border@` — the nav rail and the content are now visibly two surfaces, not one.

**Selection you can actually see.** `QTableView::item:selected` now fills with
`@selection@` (was the barely-there `@primary_soft@`); `@selection@` itself was
re-toned up in both palettes (`#22343d → #294a58` dark, `#cfe8ee → #bfe1ea`
light). The 3 px leading accent bar stays.

**Row-state tint now renders.** `TaskTableModel._apply_theme` mixed the
overdue / due-soon / blocked / waiting wash against the window `@bg@`, but rows
paint on `@surface@` — so the wash was computed too dark and vanished. Now
mixed against `@surface@`, strengths nudged (overdue .20→.22, due_soon
.14→.16).

**Status bar.** The Taskwarrior version string was bright `@success@` green —
the most saturated thing on screen. `QLabel#StatusOk` is now `@text_muted@`;
`QLabel#StatusCount` (the task count) went `@fs_xs@ → @fs_body@` and is the
confident element. `@overdue@` red is still reserved for "task not found".

**Header.** `+ Add task` is now the one emphasised toolbar control —
`QToolButton#PrimaryAction` (accent fill, text beside icon). The filter field
gained a leading `search` (magnify) glyph. The quick-add live-preview label is
hidden at rest (it only means something while typing), removing the empty band
that made the two toolbar rows look mis-aligned.

**Tests:** `tests/gui/test_n1_shell.py` (6). Full suite **519 passed /
1 skipped**; ruff clean.

## n2 — implementation log (in progress)

**Dimmed light palette (revised).** First widened the `_RUZ` steps; then, on
feedback that pure-white `surface` was too bright, re-based the whole theme
darker — `bg #d9dee6` (mid cool-grey), `surface #eef1f5` (soft off-white, not
white), `elevated #f7f9fb`. Elevation ladder stays wide (surface ~0.15 lum
above bg, bg ~0.07 above the sidebar). `text_muted` → `#4c5666` to hold AA on
the greyer `bg_alt`. Structure / clarity unchanged; just less glare.
_Original n2 note:_ The old `_RUZ` ladder was ~4% luminance apart —
`surface` (white) barely lifted off `bg` (near-white) and borders had nothing
to sit against. Steps widened: `bg #f4f6fa → #eaeef4` (a cooler grey),
`bg_alt → #e2e7f0`, `border #dde2e9 → #ccd4e0`, plus matching moves on
`hover / row_line / row_alt / field / primary_soft / chip_*`. `text_muted`
darkened `#5b6472 → #556070` to stay clear of the AA line on the darker
`bg_alt`. WCAG-AA parity + contrast tests still green. Dark theme unchanged bar
the n1 `selection` re-tone.

**Focus ring.** `QToolButton:focus` now swaps its (already-reserved 1 px)
border to `@focus@`, matching `QPushButton` / inputs — every interactive
control shows focus consistently.

**Priority dot.** The `priority` column now leads with an 8 px colour dot
(High → `@overdue@`, Medium → `@due_soon@`, Low → `@text_muted@`) via
`DecorationRole` — the level is scannable without reading the label.

**Row density (live toggle).** `Settings.density` (`comfortable` | `compact`,
default comfortable) + a Settings-dialog combo. `TaskTable.set_density()` sets
the row height (40 → 30) live — no restart, applied on open and on settings
accept. `tests/gui/test_n2_polish.py` (6). Snapshot rebaselined for the new
Settings row (documented change).

## n3 — implementation log (complete)

**Command palette (Ctrl+K).** `widgets/command_palette.py` — a `Popup` dialog
with a search field + ranked list. `_score()` is a small fuzzy matcher:
contiguous substring hits rank by position and always beat a scattered
subsequence match. `MainWindow._collect_commands()` gathers three sources:

- every enabled `QAction` under the window (toolbar + menus), deduped by text,
  carrying its shortcut as a hint;
- every activatable sidebar row via the new `Sidebar.navigation_targets()`
  (quick views, reports, projects, tags, contexts) — routed through the
  extracted `Sidebar.activate_spec()` shared with normal clicks;
- saved filters, with a stable category (the sidebar's own saved-filter rows
  are skipped so they aren't listed twice).

It complements the Raw Command Console (invariant #7), never replaces it: the
palette launches things that already have a control; the console stays the
raw-`task` escape hatch.

`tests/gui/test_n3_command_palette.py` (4). i18n keys added (fa + en). QSS
`QDialog#CommandPalette` / `#PaletteInput` / `#PaletteList`.

**Mission n status:** P0 (n1) + P1 (n2) + P2 (n3 command palette) shipped.
Deferred from P1/P2 as separate follow-ups if wanted: tag-pill delegate,
default-hiding the urgency column (breaks 4 model tests' column assumptions —
needs a test sweep), skeleton loaders, view cross-fade animation. Suite **529
passed / 1 skipped**.

## n — filter-field bug fixes (2026-09-01)

Two reported search bugs:

1. **Case-sensitive search.** Taskwarrior 3.4.1 defaults
   `rc.search.case.sensitive=1`, so a bare word in the filter field only
   matched the exact case. Added `rc.search.case.sensitive=no` to the shared
   `_RC` (approved: CLI + GUI) — `tests/test_integration.py::
   test_search_is_case_insensitive`, `docs/taskwarrior-compatibility.md`.

2. **Clearing the field didn't reset the view.** `FilterBar._on_text()` only
   updated the tooltip; the filter applied on Enter / the apply button and was
   cleared only by the dedicated ✕ toolbutton — so deleting the query text (or
   using the line-edit's own inline clear) left the last filter applied. Now
   emptying the field emits `filterChanged([])`, returning the list to the
   current view. Typing still applies on Enter. `tests/gui/test_filter_bar.py::
   test_emptying_the_field_resets_the_view`.

## n — edit-panel fixes (2026-09-01)

1. **The window forced itself past a 1024-wide screen.** `minimumSizeHint`
   was ~1012 px (nav dock `minWidth 240` + filter field `minWidth 320` + group
   combo `minWidth 150` + the panel's own minimum), so on a 1024 display —
   especially with the edit panel open — the trailing toolbar controls (and the
   panel's own edge) were clipped / pushed off-screen. Lowered: dock 240→190,
   filter 320→200, combo 150→120, `_DETAIL_WIDTH` 460→400. Floor is now
   ~962 px. `tests/gui/test_main_window.py::
   test_window_minimum_width_fits_a_standard_screen`.

2. **Esc didn't close the edit panel** — only the Close button did. Added a
   window-level `Esc` `QShortcut` → `_escape_pressed()`, which calls
   `_hide_detail()` only when `_detail_host` is visible (so it's inert
   otherwise and doesn't shadow dialog/menu/popup Esc, which are separate
   windows). `test_escape_closes_the_detail_panel`.

3. The panel now scrolls to the top on `load_task()` so the title + Close are
   visible when it opens on a new task.
