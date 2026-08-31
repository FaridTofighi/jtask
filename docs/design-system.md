# jtask-gui — design system

The enforced visual conventions. Established in mission **d** (d1–d7); every
future feature follows these rather than re-deriving them. Colours live in
`src/jtask_gui/theme.py`; everything else in `src/jtask_gui/tokens.py`.

---

## 1. Tokens — `jtask_gui/tokens.py`

Single source of truth for every non-colour visual constant. Two consumers:

* **QSS** (`resources/themes/app.qss`) reads `@sp_N@` / `@fs_*@` / `@r_*@`
  placeholders, filled by `theme.render_qss()` alongside the colour tokens.
* **Python layout code** imports the integer constants (`SP_8`, `R_MD`,
  `FS_H2`, `INSET_DIALOG`, …).

### Spacing scale (px)
`SPACE = (2, 4, 6, 8, 10, 12, 14, 16, 20, 24)` — the token name carries the
value: `SP_8` is 8 px, `@sp_8@` in QSS. A new raw value (9, 13, 17 …) fails
`tests/gui/test_qss_uses_tokens.py`. Only `0`, `1px`, `2px` (border / hairline
widths) are allowed as bare lengths in a padding / margin / spacing /
border-radius declaration.

**Semantic insets** (l, t, r, b) — use instead of ad-hoc tuples:

| token | value | use |
|---|---|---|
| `INSET_NONE` | `(0,0,0,0)` | a layout nested inside an already-padded one |
| `INSET_TIGHT` | `(8,8,8,8)` | dense cards, day cells, popovers |
| `INSET_PANEL` | `(14,14,14,14)` | slide-in panels, side rails |
| `INSET_DIALOG` | `(16,16,16,16)` | every `QDialog` root layout |

### Type scale (px) — `FONT_SIZE`
`h1 22 · title 16 · lg 15 · body 14 · h2 13 · xs 12`, weights 400 / 700. Values
are **what actually renders** — the old header comment claimed `H2 = 17` but a
duplicate rule had every `#H2` at 13 since M6; the dead rule was removed in d1.
No raw `font-size` px in the QSS; a duplicate full selector fails the guard.

### Radius (px) — `RADIUS`
`sm 6 · md 8 · pill 9 · lg 12`. `r_md` is the default control radius; `r_lg`
for large surfaces (table, chip, toast); `r_pill` for badges / the timer chip.

---

## 2. Colour & elevation — `theme.py`

Two palettes (`_SHAB` dark, `_RUZ` light), identical key sets, WCAG-AA checked
(`tests/gui/test_theme.py`). **No hex literal anywhere outside `theme.py`**
(`test_no_hardcoded_colours_in_template` + a repo-wide grep). White-on-danger
text is the `on_danger` role; charts colour their series by role
(`CHART_SERIES_ROLES`), never a flat list.

### Elevation — one approach: **raised surface + 1-px edge** (not shadows)
A dialog / popover / card is set apart from the window background by the
`elevated` colour role (dark `#1e222a`, a visible lift off `#16181d`; light
`#ffffff`) plus a `border` edge. Within a raised surface, **inputs recede**
(`field` fill) and **buttons lift** (`surface` fill) so they still read as
controls. `tokens.shadow(widget)` exists for a genuine free-floating overlay
but nothing needs it yet. *Known follow-up:* a deeper light-theme lift needs a
base-tone shift (light `bg` → an off-white), deferred.

---

## 3. Destructive-action colour

Any irreversible-action confirm button (`delete`, `purge`, `undo`) is
`QPushButton#Danger` — `overdue` (red) fill, white label. When it is gated
(the phrase field on Purge) it is **disabled but still red-edged**
(`#Danger:disabled` → greyed fill, red border + label) so it never looks like a
neutral button. A non-destructive primary action is `#Primary`. The
non-blocking toast (§5) is for *positive* feedback only and never replaces a
confirm dialog.

---

## 4. Validation timing

**No validation error appears on a pristine, untouched form.** A disabled
submit button is the pristine signal; a required field states its requirement
in its placeholder. The red hint (`#FormHint`) appears only after:

* a submit attempt (`_try_accept` — validates, shows problems, accepts only if
  none), or
* a required field is focused and then left empty.

No form calls `self._revalidate()` / `_validate()` in `__init__`
(`test_d3_dialog_form_standards.py` grep guard).

---

## 5. Non-blocking feedback — the toast

`widgets/toast.py` — `QFrame#Toast`, one per main window. `surface` + `border`,
opacity fade, auto-dismiss ~2.6 s, bottom-centre above the status bar,
`WA_TransparentForMouseEvents` + `NoFocus`. Raised for every successful
**non-destructive** command (via the single `_write()` funnel) and for
save/rename-filter. The status-bar message stays as the persistent complement.
Destructive actions keep their blocking `confirm()`.

---

## 6. Empty states

One designed look: a centred, word-wrapped `QLabel#EmptyState` (`#DepEmpty` for
the dependency graph, sized smaller). Never a bare `#Muted` label.
Chart "no data" is the equivalent centred text on the matplotlib canvas.
`test_d6_toast_empty_states.py` greps for bare empty-state labels.

---

## 7. Toolbar

Row two is grouped into clusters separated by `QToolBar` separators:
`filter · group · create (add-full, log) · undo · data ▾ · view (theme,
console) · config (settings, ⋯)`. The rarely-used dialog entry points
(**Manage Taskwarrior**, **Diagnostics & tools**) sit behind a single flat
`⋯` `QToolButton` menu — one level, one extra click, no submenu (Resolution 3).
**Every** toolbar control has a descriptive tooltip that is not merely its
label (`test_d4_toolbar.py`). Icons are `qtawesome` `mdi.*`, outline style.

---

## 8. RTL / bidi

Layout direction follows the **UI language** only (fa → RTL, en → LTR), never
the calendar. Any LTR-structured token rendered inside RTL text — signed
numbers, dates, **file paths, URLs, UUIDs** — is wrapped in
`jtask.rtl.bidi_isolate()` so it stays atomic (`U+2066 … U+2069`).

---

## 9. Terminology

`docs/i18n-glossary.md` is the single source of truth. English uses
Taskwarrior's own vocabulary exactly; priority is **بالا / متوسط / پایین** —
**High / Medium / Low** (never «بحرانی»/"Critical" — Taskwarrior has only three
levels). New user-facing strings go through `i18n.t()`; raw Persian literals in
widget files fail `tests/test_no_new_hardcoded_strings.py`.

---

## Enforcement summary

| rule | test |
|---|---|
| QSS uses spacing/type/radius tokens; no dupe selector; no hex literal | `test_qss_uses_tokens.py` |
| palette parity + WCAG AA | `test_theme.py` |
| dialogs size to content; no premature validation; first-run form layout | `test_d3_dialog_form_standards.py` |
| toolbar grouped; every control tooltipped; flat overflow | `test_d4_toolbar.py` |
| priority wording; bidi-safe paths; dep-graph elision | `test_d5_terminology_widgets.py` |
| toast non-blocking; destructive keeps confirm; empty states styled | `test_d6_toast_empty_states.py` |
| no new hardcoded Persian | `test_no_new_hardcoded_strings.py` |
| fa/Jalali visible text unchanged | `test_i18n_snapshot.py` |
