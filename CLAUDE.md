# CLAUDE.md

Guidance for working in this repository.

## What this is

**jtask** is a transparent Persian/Jalali layer over [Taskwarrior](https://taskwarrior.org).
Taskwarrior has no Jalali calendar and no RTL UI; jtask adds both without hiding
any Taskwarrior feature. It **never writes Taskwarrior's data files** — it shells
out to the `task` binary (`task export` to read, `task add` / `task <filter>
<cmd>` to write). Taskwarrior's stored data stays **Gregorian/UTC and 100%
`task`-compatible**; only what the user sees and types is Jalali.

Two packages in `src/`:

| package | what | audience |
|---|---|---|
| `jtask` | the CLI (`jtask` console script) + all framework-agnostic core logic | **Persian-first, RTL. Out of scope for GUI missions** except the shared primitives below, touched additively. |
| `jtask_gui` | the PyQt6 desktop app (`jtask-gui`) | **Bilingual (fa/en) + selectable calendar (Jalali/Gregorian)**, all four combinations. |

## Environment / commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[gui,dev]"

.venv/bin/python -m pytest -q          # full suite (~431 tests, ~70s)
.venv/bin/python -m pytest -q tests/gui/test_m5.py::test_name   # one test
.venv/bin/ruff check src/ tests/       # lint (line-length 100; E,F,I,UP,B)
.venv/bin/ruff check --fix src/ tests/
.venv/bin/mypy                         # types — core only (see below)
```

- Python **3.13** in the venv (project targets ≥3.10). PyQt6 6.11 / Qt 6.11.
- `task` (Taskwarrior **3.5.0**) must be on `PATH`. Timewarrior is optional
  (detected at runtime; not required).
- GUI tests run headless via `QT_QPA_PLATFORM=offscreen` (set by
  `tests/gui/conftest.py`). Ad-hoc GUI scripts must set it too.
- **mypy checks `src/jtask` only.** The PyQt6 layer (`jtask_gui.*`) is
  `ignore_errors` — pytest-qt covers it (the Qt6 stubs' pervasive `| None`
  returns make a strict pass mostly noise).
- Commit/push only when asked. Each milestone lands in its own commit with
  tests + screenshots; end commit messages with the `Co-Authored-By` /
  `Claude-Session` trailers already used in history.

## Data flow

```
user args (Jalali) ─▶ jalali.to_gregorian_string / rewrite.rewrite_args ─▶ taskwarrior.run ─▶ task
task export (UTC)  ─▶ reports.py / rewrite.rewrite_export (per-field) ─▶ render (CLI) / models+widgets (GUI)
```

Every date the user sees is formatted from the raw Gregorian value; every date
the user types is converted to a `task`-ready string before the command runs.
Unrecognised tokens pass straight through to `task`.

## Core primitives (`src/jtask/`) — shared, change additively

| module | role | key surface |
|---|---|---|
| `jalali.py` | Jalali↔Gregorian, Persian relative-date parsing, calendar math (week starts **Saturday**), digit conversion | `parse_jalali`, `to_gregorian_string`, `from_taskwarrior(v, fmt)`, `from_local`, `parse_relative`, `month_grid`, `week_range`, `weekday_sat`; `MONTH_NAMES`, `WEEKDAY_NAMES`, `LOCAL_TZ`; regexes `_TW_TS_RE` (`^YYYYMMDDTHHMMSSZ$`), `_LOCAL_TS_RE`, `_DATE_RE` |
| `rewrite.py` | find + rewrite date-bearing tokens in argv / export JSON, both directions | `rewrite_args`, `rewrite_export`, `DATE_ATTRS` |
| `taskwarrior.py` | the **only** subprocess wrapper for `task` | `run(args, *, quiet=…)` (raises `TaskCommandError` on non-zero), `export`, `add`, `command(filter, verb, mods)`, `_lines`, `sync_status`, `synchronize`, `purge`, `duplicate`, `information`, `diagnostics`, `calc`. Always passes `_RC` = `rc.confirmation=off rc.recurrence.confirmation=off rc.bulk=0 rc.color=off rc.hooks=on`; adds `rc.verbose=nothing` when `quiet`. |
| `rtl.py` | reshaping + bidi + digit mode | `rtl(s)`, `bidi_isolate(s)` (`U+2066…U+2069`), `set_digit_mode` / `digit_mode`, `num`, `fa_digits` / `en_digits` |
| `reports.py` | framework-agnostic report shaping from `task export` JSON only (no ASCII parsing) | `report_next/waiting/blocked/ready/completed`, `report_projects/tags/summary/history/burndown/calendar`, `shape_*`. Output date fields are Jalali strings **plus** `<field>_gregorian`. |
| `config.py` | CLI config `~/.config/jtask/config.yaml` (`JTASK_CONFIG_DIR` overrides) | `load`, `save`, `config_dir` |
| `themes.py` | CLI theme YAMLs (`~/.config/jtask/themes/*.yaml`) — **separate** from the GUI theme | |

The CLI (`cli.py`): `main()` dispatches recognised verbs via `_DISPATCH`;
**anything else is `rewrite.rewrite_args` → `taskwarrior.passthrough`** so no
`task` feature is lost. GTD helpers (`waiting` / `someday` / `projects` /
`calendar` / `review`) are jtask-only views; the heavier ones (`project_summary`,
`weekly_review`) live in `gtd.py`.

## GUI architecture (`src/jtask_gui/`)

- `app.py` — QApplication bootstrap: load fonts → `set_language` → layout
  direction → theme QSS → `MainWindow`.
- `main_window.py` — the shell. `_write(fn, msg)` is the **single mutation
  funnel** (`_begin_busy` → `workers.submit` → status + toast + `refresh_all`).
  `_content` is a `QStackedWidget`: index 0 tasks, index 1 reports.
- `workers.py` — `submit(fn, on_ok, on_err)` runs `fn` on a `QThreadPool`;
  `_Signals.failed` carries the exception. `wait_for_done(ms)` for tests.
- `settings.py` — typed wrapper over `QSettings("jtask", "jtask-gui")`.
  `language` (fa/en), `calendar` (jalali/gregorian) — **restart required**,
  prompted. `persian_digits` follows the language until
  `digit_mode_user_overridden` is set — **live toggle**. Dock "state" is
  namespaced by language (`win/state_<lang>`).
- `i18n/` — dict catalog: `t(key, **kw)` (str.format), `set_language`,
  `is_rtl`. `fa.py` is the baseline; `en.py` is `dict(_FA)` + a full override.
  **NOT** Qt `QTranslator` (≈20 modules build label lists at import time).
- `calendar_system.py` — `CalendarSystem` ABC + `JalaliCalendarSystem`
  (wraps `jalali.py`; Latin transliteration of month/weekday names in en mode)
  + `GregorianCalendarSystem` (`rc.weekstart`-aware). `active()` is the one
  process-wide instance.
- `theme.py` — two palettes (`_SHAB` dark, `_RUZ` light), `render_qss(name)`
  fills `@colour@` + `@sp_*@/@fs_*@/@r_*@` tokens into `resources/themes/app.qss`.
- `tokens.py` — spacing / type / radius / inset / elevation constants
  (see `docs/design-system.md`).
- `models/` — `task_model.py` (Qt table model; re-formats `<key>_gregorian`
  via `active().format_utc`), `column_spec.py` (`COLUMNS`, built at import).
- `widgets/` — one file per dialog/view. `widgets/charts/` = matplotlib
  (`mpl_base.ThemedChart`, `mpl_text.fa` for shaped Persian).

## Hard invariants — do not break

1. **Never write Taskwarrior's data store directly.** Go through
   `taskwarrior.py`. Reads are `task export` JSON; the CLI must not parse
   `task`'s ASCII report output.
2. **Stored data stays Gregorian/UTC.** Jalali/Gregorian display and input
   parsing are presentation only.
3. **Week starts Saturday** for Jalali everywhere.
4. **Every user-facing GUI string goes through `i18n.t()`.** Raw Persian
   literals in `jtask_gui/**` fail `tests/test_no_new_hardcoded_strings.py`
   (per-file ceiling in `tests/_i18n_string_ceiling.json`).
5. **No raw px** for padding/margin/spacing/font-size/border-radius in
   `app.qss` — use `@sp_*@ / @fs_*@ / @r_*@` (`tests/gui/test_qss_uses_tokens.py`).
   No hex colour literal anywhere outside `theme.py`.
6. **GUI layout direction follows the UI language only** (fa→RTL, en→LTR),
   never the calendar. LTR-structured tokens (numbers, dates, paths, URLs,
   UUIDs) inside RTL text are wrapped in `bidi_isolate`.
7. **The Raw Command Console stays** — the permanent escape hatch for any
   `task` feature without a dedicated control.
8. Terminology: `docs/i18n-glossary.md` is the single source of truth; English
   uses Taskwarrior's own vocabulary; priority is بالا/متوسط/پایین =
   High/Medium/Low (Taskwarrior has only three levels).

## Tests as guards

The suite encodes conventions, not just behaviour. When one fails, check
whether you violated a rule before "fixing" the test:

| gate | file | regenerate |
|---|---|---|
| fa/Jalali visible text unchanged (byte-identical) | `tests/gui/test_i18n_snapshot.py` (baseline `_snapshots/fa_visible_strings.json`) | `JTASK_WRITE_SNAPSHOT=1 pytest tests/gui/test_i18n_snapshot.py` — only for a **deliberate, documented** wording/widget change |
| no new hardcoded Persian | `tests/test_no_new_hardcoded_strings.py` | `JTASK_WRITE_CEILING=1 pytest …` |
| QSS uses tokens, no dupe selector, no hex | `tests/gui/test_qss_uses_tokens.py` | — |
| palette parity + WCAG AA | `tests/gui/test_theme.py` | — |
| theme-name migration (شب/روز→dark/light) | `tests/gui/test_i2_theme_migration.py` | — |
| layout direction per language | `tests/gui/test_i3_layout_direction.py` | — |
| calendar system / 4 combos | `tests/gui/test_i4_calendar_system.py`, `test_i6_four_combinations.py` | — |
| English catalog coverage + terminology | `tests/gui/test_i5_english_catalog.py` | — |
| design-system rules (d3–d6) | `tests/gui/test_d{3,4,5,6}_*.py` | — |

GUI test fixtures that touch global state (`i18n.set_language`,
`set_digit_mode`, `calendar_system.set_calendar`, `QSettings`) **must
save/restore** — leaks cause spurious failures in unrelated tests.

## Docs (read before large changes)

- `docs/jtask-gui-design.md` — the running implementation log: M1–M9 feature
  parity, i1–i6 i18n/calendar, d1–d7 design system. Append a milestone log
  here.
- `docs/design-system.md` — the enforced spacing/type/elevation/validation/
  toolbar/bidi conventions + their guard tests.
- `docs/i18n-glossary.md` — terminology source of truth.
- `docs/taskwarrior-feature-matrix.md` / `feature-parity-status.md` — what's
  implemented vs. intentionally console-only.
- `docs/taskwarrior-compatibility.md` — `task` version notes.
