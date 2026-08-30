# i18n + Calendar mission — Phase 0 audit

**Do not implement from this document.** It is the pre-implementation audit
requested in §1 of the mission spec: a string inventory, an inventory of
unconditional RTL / Jalali / Persian-digit assumptions, the translation-mechanism
recommendation, and a proposed milestone breakdown. Awaiting approval.

Scope note: this mission is **jtask-gui only**. `src/jtask/` is a separate
Persian-first *CLI* (`jtask …`) with ~200 more Persian strings of its own; it is
**out of scope** and stays Persian. Only the calendar/format primitives that the
GUI imports from the core — `jalali.py` (month/weekday name tables, formatting),
`rewrite.py` (date-token rewriting), `rtl.py` (digit mode, bidi isolate) — are
touched, and only additively.

---

## 1. String inventory (GUI)

Method: lines containing an Arabic-script codepoint, per module. ~**485 unique**
quoted Persian substrings; realistic distinct *messages* ≈ **350–420** after
accounting for f-string fragments split across lines and duplicates
(`"انصراف"` ×11, `"در انتظار"` ×10, `"پروژه"` ×10, `"شب"` ×10, …).

| Bucket | Modules | ~Persian lines |
|---|---|---|
| **Shell** | `main_window.py` (102), `widgets/sidebar.py` (26), `widgets/task_table.py` (18), `widgets/filter_bar.py` (7), `widgets/quick_add.py` (1) | ~155 |
| **Detail / editing** | `widgets/detail_panel.py` (31), `widgets/task_form.py` (20), `widgets/bulk_edit.py` (22), `widgets/recurrence_builder.py` (2), `widgets/chips.py` (1), `quickadd.py` (9) | ~85 |
| **M5 dialogs** | `widgets/confirm.py` (8), `widgets/error_dialog.py` (6), `widgets/op_status.py` (1) | ~15 |
| **M6 insight** | `widgets/history_view.py` (33), `widgets/stats_view.py` (23), `widgets/timesheet_view.py` (13), `widgets/timer_indicator.py` (2), `widgets/raw_data_view.py` (2) | ~73 |
| **M7 data** | `widgets/export_dialog.py` (15), `widgets/import_dialog.py` (13), `widgets/sync_dialog.py` (16) | ~44 |
| **M8 managers** | `widgets/config_manager.py` (19), `widgets/context_manager.py` (18), `widgets/uda_manager.py` (21), `widgets/report_manager.py` (22), `widgets/manager_dialog.py` (6) | ~86 |
| **M9 tools** | `widgets/tools_dialog.py` (15), `widgets/filter_builder.py` (26) | ~41 |
| **Reports / charts** | `widgets/reports_view.py` (15), `widgets/calendar_report.py` (4), `widgets/table_reports.py` (2), `widgets/charts/*` (15), `widgets/jalali_calendar.py` (indirect) | ~40 |
| **Settings / first run** | `settings_dialog.py` (17), `widgets/first_run.py` (12), `theme.py` (4), `models/column_spec.py` (19) | ~52 |
| **Misc** | `notifications.py` (6), `models/task_model.py` (1), `fmt.py` (1), `icons.py` (1), `workers.py` (1) | ~10 |

**Total: ~48 files, ~730 Persian-string lines.**

### 1a. Strings that double as identity keys (must be decoupled first)

These are the risky ones — a display label is also used as a dict key / passed
as a stable token, so translating the label silently breaks lookups:

| Where | Coupling |
|---|---|
| `sidebar.py` view specs `{"title": "امروز", …}` → consumed by `task_table._EMPTY_MESSAGES` keyed on `"امروز"`, `"این هفته"`, `"معوق"`, `"در انتظار"`, `"مسدودشده"`, `"تکمیل‌شده"`, `"اقدامات بعدی"` | display title == empty-state key == status-bar title |
| `theme.py` / `settings.py` — theme names `"شب"` / `"روز"` are the `THEMES` dict keys **and** the persisted QSettings value **and** compared by string in `main_window._apply_theme`, `other_theme`, `first_run` | display label == persisted identity |
| `main_window._DEFAULT_VIEW` / `_view_spec` `"title"` fields | title string reused as the status-bar label and (for reports) as an empty-state key |
| `reports_view._REPORTS` — `(key, label, glyph)` — key is already stable ✅, label needs extraction |

**Decision needed (recommended answer in §3):** migrate these to stable ASCII
keys (`today`, `week`, `overdue`, `next`, `waiting`, `blocked`, `completed`;
`dark`, `light`) with a one-time QSettings migration for the theme value, and
resolve the label through the catalog at render time.

### 1b. Dynamic Persian → attribute maps (belong in the catalog/glossary)

`history_view._ATTR_FA` / `_STATUS_FA`, `detail_panel._STATUS_FA` /
`_PRIORITIES` / `_DATE_FIELDS`, `stats_view._LABEL_FA` / `_UNIT_FA`,
`uda_manager._TYPES`, `report_manager._FIELDS`, `filter_builder._STATUS` /
`_PRIORITY` / `_VTAGS`, `recurrence_builder._UNITS`, `reports_view._PERIODS` /
`_REPORTS`, `settings_dialog._NOTIFY_STATES`, `quickadd._PRIORITY_LABEL`,
`column_spec.COLUMNS` (header labels). All key off a stable Taskwarrior/enum
token already — only the label side needs the catalog.

### 1c. f-string interpolation

Pervasive: `f"{fmt.num(len(tasks))} کار · {title}"`,
`f"به پروژهٔ «{project}» منتقل شد"`, `f"این عملیات روی {fmt.num(count)} {noun} اعمال می‌شود."`
etc. ≈ 120 sites. Any mechanism must support positional/named placeholders and
must not fight `fmt.num()` (which itself depends on digit mode).

---

## 2. Unconditional RTL / Jalali / Persian-digit assumptions

### 2a. Layout direction (RTL hardcoded)

| Site | Current | Needs to become |
|---|---|---|
| `app.py:74` `app.setLayoutDirection(RightToLeft)` | unconditional | `RightToLeft if lang=="fa" else LeftToRight` |
| `main_window.py:283` sidebar dock → `RightDockWidgetArea` | unconditional | `Right` for fa, `Left` for en |
| **15 dialogs** each call `self.setLayoutDirection(RightToLeft)` in `__init__` (`confirm`, `error_dialog`, `export_dialog`, `import_dialog`, `sync_dialog`, `task_form`, `bulk_edit`, `config_manager._EditDialog`, `context_manager._ContextDialog`, `uda_manager._UdaDialog`, `report_manager._ReportDialog`, `manager_dialog`, `tools_dialog`, …) | unconditional RTL | **remove the call** — inherit the app direction. (These are latent bugs today too: they'd force RTL even if the app were LTR.) |
| `error_dialog.py:86`, `confirm.py:83`, `tools_dialog.py:38`, `raw_data_view.py:42` — force **LTR** on a monospace box (stderr / JSON / diagnostics / command list) | correct | **keep** — code/data stays LTR in both languages |

### 2b. Icon mirroring

`icons.py` `_MIRRORED = {"undo"}` → `opts["rotated"] = 180` unconditionally.
Only one glyph. Needs: mirror **only when** `layoutDirection == RightToLeft`.
Re-audit the full icon set for others that should flip in RTL and *only* RTL
(`undo`, possibly `import`/`export` arrows — currently they don't flip).

### 2c. Calendar / Jalali hardcoding

Everything date-related calls `jtask.jalali.*` directly:

| Call | Sites |
|---|---|
| `jalali.from_taskwarrior(ts, fmt)` | `detail_panel` (×2) |
| `jalali.from_local(ts, fmt)` | `history_view` (×4), `stats_view`, `timesheet_view`, `sync_dialog`, `tools_dialog` |
| `jalali.resolve` / `parse_relative` / `parse_jalali` | `quickadd` (×2), `jalali_date_picker` (×3) |
| `jalali.week_range` | `sidebar`, `timesheet_view` |
| `jalali.month_grid` / `MONTH_NAMES` / `WEEKDAY_NAMES_SHORT` | `jalali_calendar` (the grid engine), `calendar_report` |
| `jalali.to_gregorian_string` (via `JalaliDatePicker.gregorian_string`) | every date field |

Widgets hardcoding Jalali by name: `jalali_calendar.py`, `jalali_date_picker.py`
(the grid engine + picker), `calendar_report.py`, plus the 8 consumers above.
Week-start = Saturday is baked into `JalaliMonthGrid` and `jalali.weekday_sat`.

### 2d. Persian digits applied *outside* the digit-mode setting

`fmt.digits()` correctly honours `digit_mode()`. But these bypass it and force
Persian digits unconditionally:

- `quickadd.py:85,124` — `jalali.to_persian_digits(date.strftime(...))`
- `history_view.py:60,61,169` — elapsed/clock strings
- `timesheet_view.py:33,37` — `_hm()` / `_clock()`
- `timer_indicator.py:22,65` — elapsed + active-count
- `jalali_date_picker.py:122` — the line-edit display value
- `jalali_calendar.py:158` (via `fmt.digits` — OK actually) / `calendar_report.py:174` (via `fmt.digits` — OK)
- `models/task_model.py:157` — a fallback branch
- `fa_spinbox.py:17,26` — `normalize_digits` on *input* (fine, keep — it accepts both)

→ ~10 sites must route through `fmt.digits()` / the active digit mode instead.

### 2e. Bidi isolate (low priority)

`fmt.num(isolate=True)` and `task_model` / `detail_panel` wrap signed
numbers/dates in U+2066…U+2069. Harmless in LTR (still valid), just redundant.
Leave as-is; revisit only if it causes visible artifacts in LTR.

### 2f. Fonts

`app.py` loads **only** Vazirmatn (3 weights) and sets it as the app font.
Vazirmatn's Latin glyphs are serviceable but not best-in-class for an
English-primary UI (§7). Needs a check and, if it doesn't hold up,
a bundled Latin face (Inter is the natural pick) selected by language.

---

## 3. Translation mechanism — recommendation

**Recommendation: a centralized string-catalog module (`jtask_gui/i18n.py`),
NOT Qt's `QTranslator` / `.ts` / `.qm` pipeline.**

The mission's opening recommendation was Qt's standard mechanism "unless the
current embedding makes it impractical." The audit says it is impractical here:

| Factor | Finding |
|---|---|
| **Module-level string constants** | ~20 modules build Persian label lists/dicts at **import time** (`_STATUS`, `_PRIORITY`, `_VTAGS`, `_REPORTS`, `_NOTIFY_STATES`, `_ATTR_FA`, …). `self.tr()` needs a `QObject` + installed translator; `QCoreApplication.translate()` needs the translator installed *before the call*. Both fail at import. Every one would have to become a function — at which point a catalog `t("key")` is simpler and the `.ts` layer adds nothing. |
| **f-string interpolation (~120 sites)** | Qt wants `self.tr("%1 tasks").arg(n)`. Mechanical rewrite of 120 sites to `.arg()` chains, many wrapping `fmt.num()`. A catalog `t("tasks.count", n=…)` with `str.format` is a smaller, safer change. |
| **Zero existing Qt-i18n infra** | No `tr()` calls, no `.ts`/`.qm`, no `pylupdate6`/`lrelease` in `pyproject.toml` or CI. Starting from nothing either way. |
| **Glossary-as-source-of-truth (§2)** | `docs/i18n-glossary.md` must drive the catalog. A Python/TOML catalog keyed by concept maps 1:1 to glossary rows and is diff-reviewable. `.ts` XML with generated contexts does not. |
| **Terminology maps (§1b)** are already catalogs | `_ATTR_FA` etc. *are* mini string catalogs today; consolidating them into one module is the natural refactor. |
| **Consistency with existing architecture** | The app already centralizes formatting (`fmt.py`) and Taskwarrior access (`taskwarrior.py`). A central `i18n.py` fits the same "one path" pattern. |
| **Future languages** | A catalog scales fine — add `catalog/de.toml`. The `.ts`/`lrelease` tooling is only a real win when non-developer translators use Qt Linguist, which is not this project's situation. |

### Proposed shape

```python
# jtask_gui/i18n.py
def set_language(lang: str) -> None            # "fa" | "en"; loads the catalog
def t(key: str, **kw) -> str                  # t("dialog.cancel"); t("status.count", n=fmt.num(3), title=…)
def lang() -> str
def is_rtl() -> bool                           # lang() == "fa"
```

- Catalogs: `jtask_gui/i18n/fa.toml`, `jtask_gui/i18n/en.toml` (TOML — comments,
  nesting, trivial to diff; loaded once at `set_language`).
- Missing key → return the key itself + log a warning (visible in tests).
- Module-level constants become module-level **functions** or hold **keys**
  resolved at widget-construction time (widgets are rebuilt on restart anyway —
  see §4).
- `tests/gui/test_i18n_glossary.py` diffs `en.toml` against `docs/i18n-glossary.md`.

*(This decision + reasoning is also recorded in `docs/jtask-gui-design.md`.)*

---

## 4. Live switch vs. restart

**Recommendation: require an app restart on Language *or* Calendar change, with
a clear modal prompt.** Live-switching would require re-running the equivalent of
`retranslateUi()` across ~48 widget files plus re-`setLayoutDirection` on an
already-laid-out tree plus font swap plus rebuilding every module-level label
list — high surface, low payoff. The digit-mode toggle already applies live and
stays live; only Language/Calendar force a restart.

Prompt: "Changing the language or calendar takes effect after restarting jtask.
Restart now?" → [Restart] / [Later]. On [Restart], persist + relaunch.

---

## 5. Proposed milestone breakdown

Each milestone: full existing suite stays green in the default (fa/Jalali)
config, new tests added, screenshots, matrix/docs updated — same cadence as M5–M9.

| # | Title | Contents |
|---|---|---|
| **i1** | **Glossary + catalog infrastructure** | Write `docs/i18n-glossary.md` (every term: fa label · en label · Taskwarrior-vocabulary note). Build `jtask_gui/i18n.py` + `i18n/fa.toml` (extracted from today's strings — behaviour-neutral) + `i18n/en.toml`. Add `Settings.language` (persisted, default `fa`). No visible change yet: fa catalog reproduces current strings exactly. Glossary-drift test. |
| **i2** | **Decouple identity from labels** | Migrate sidebar view-specs, `_EMPTY_MESSAGES`, `_DEFAULT_VIEW`, theme names (`شب`/`روز` → `dark`/`light` with a QSettings migration), and the §1b/§1c constant maps to stable keys + catalog lookups. Still fa-only visually. Pure refactor, heavily test-covered. |
| **i3** | **Layout direction follows language** | `Settings.language` drives `app.setLayoutDirection`; remove the 15 hardcoded `setLayoutDirection(RightToLeft)` calls; sidebar dock L/R by language; `icons._MIRRORED` conditional + full icon re-audit; restart-prompt flow. QSS / scrollbar / drag-handle / dock re-verify in LTR. Rendering smoke test in both directions. English still shows catalog keys (en.toml not filled yet) — that's expected and visible only when language=en. |
| **i4** | **Calendar-system abstraction** | `CalendarSystem` protocol; `JalaliCalendarSystem` (wraps existing) + `GregorianCalendarSystem` (mostly passthrough). Generalize `JalaliMonthGrid` → `MonthGrid(calendar_system)` sharing one grid engine; Gregorian date picker as a sibling. Week-start from the active system (Sat / Mon-or-`rc.weekstart`). Route the 8 `jalali.*` consumers + quick-add relative parsing + chart axis labels through the active system. `Settings.calendar` (persisted, default `jalali`). Tests for all 4 date-render paths. |
| **i5** | **English catalog + terminology sweep** | Fill `i18n/en.toml` from the glossary for every extracted key. Latin transliteration table for Jalali-in-English (Shanbeh… / Farvardin…) stored with `JalaliCalendarSystem`, used by grid + pickers + chart axes. Digit-mode default per language (§6). Font check + optional Inter bundle (§7). Terminology test vs. glossary. |
| **i6** | **Four-combination hardening + docs** | Rendering/smoke test matrix for all 4 Language×Calendar combos (layout dir, sidebar side, no fa/Jalali leakage). Final screenshots (task list + detail panel ×4). Update `taskwarrior-feature-matrix.md` note, `jtask-gui-design.md`, `feature-parity-status.md`. Acceptance-checklist pass. |

Rationale for the ordering: infra (i1) → de-risk the hidden coupling (i2) →
layout (i3) and calendar (i4) are independent and could even swap order → then
the actual English words (i5) land on a stable base → i6 proves the matrix.

i1+i2 are low-risk and could be one milestone if you prefer fewer checkpoints;
kept separate here because i2 touches persisted settings (theme-name migration)
and deserves its own review.

---

## STOP — awaiting approval of the mechanism decision and the i1–i6 breakdown before implementation.
