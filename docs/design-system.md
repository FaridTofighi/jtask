# jtask-gui — design system

The enforced visual conventions. Established in mission **d** (d1–d7), then
given a visible pass (mission **m**) that was **partly reverted** after a
retroactive audit (see `docs/jtask-gui-design.md` → "Mission m — retroactive
audit + resolution"): a layered palette on a **teal** accent, a table with
zebra striping + state washes + an accent selection bar + quiet secondary
columns, a distinct toolbar with no label prefixes, consistent focus rings.
Every future feature follows these rather than re-deriving them. Colours live
in `src/jtask_gui/theme.py`; everything else in `src/jtask_gui/tokens.py`.

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

### Elevation layers — each surface sits visibly above the one behind it

| role | dark | light | used for |
|---|---|---|---|
| `bg` | `#0e1014` | `#f4f6fa` | the window / toolbar / status bar |
| `bg_alt` | `#15181e` | `#e9edf3` | sidebar, reports rail, table **header** |
| `surface` | `#1b1f27` | `#ffffff` | table body, cards, buttons, tree/console |
| `elevated` | `#232833` | `#ffffff` | dialogs, menus, tooltips, popovers, toast |
| `field` | `#12151b` | `#f1f4f8` | text inputs (a recessed well) |

`border` is the visible divider, `border_soft` the near-invisible hairline
(row lines, splitter, section dividers). Inputs recede (`field`), buttons lift
(`surface`) even on a raised dialog.

### The accent is used deliberately — `primary`

**Teal** — dark `#6cc7dd`, light `#0a6e8f` (`primary_fg` is the text on top;
`primary_soft` is the low-alpha wash; `focus` == `primary`). This is the
mission-d baseline; the mission-m blue re-tone was reverted. `primary` appears
in exactly these places and nowhere else: selection (table row + menu item =
`primary_soft` fill; the table adds a 3-px `primary` leading-edge bar painted
in `TaskTable.paintEvent`, see §11), the primary action button, the focus ring,
the active sidebar row (`primary_soft` bg + `primary` text), the detail-tab
underline, progress-bar fill, and the running-timer chip. **`accent`** (violet)
is the `#Primary:pressed` / `#Danger:pressed` flash and the 5th chart-series
colour — nothing else.

The light theme's base is a soft off-white (`bg = #f4f6fa`), not pure white, so
`surface` (`#ffffff`) cards lift off it. Contrast for body/secondary text and
the `overdue` / `due_soon` state colours against the base is still
WCAG-AA (`tests/gui/test_theme.py`).

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

**Free-text base direction is a two-tier rule** (`jtask_gui.bidi`), not a
first-character guess. A task description / annotation / project name renders
with:

1. **the UI language's direction by default** (like a word processor's
   paragraph direction tied to the input locale);
2. **the opposite direction only when the value is a clear majority
   (`≥ 60 %`) of the opposite script** (`jtask.rtl.script_balance`) — a
   genuinely foreign-language value.

So "جلسه با آرش" reads RTL, "Backup را بررسی کنم…" (Persian sentence, leading
Latin term) *also* reads RTL, and "Upgrade Docker Engine on staging servers"
(really English) reads LTR — in either UI language. Embedded opposite-script
runs shape and order natively *within* the paragraph; this only fixes the
paragraph's base direction. Surfaces that can't set a per-item base direction
(table cells, graphics items) wrap the text in a matching directional isolate
(`jtask_gui.bidi.directional_isolate` → `U+2067…U+2069` RTL / `U+2066…U+2069`
LTR).

| helper | use |
|---|---|
| `content_direction(text)` / `content_alignment(text)` | pure — the Qt direction / absolute horizontal-align flag by the two-tier rule |
| `directional_isolate(text)` | wrap text so its paragraph base direction is pinned regardless of the surrounding widget |
| `apply_content_direction(label, text)` | set a read-only `QLabel`'s `layoutDirection` + alignment |
| `align_item(item, text)` | set a `QListWidgetItem` / `QTreeWidgetItem`'s `textAlignment` |
| `bind_auto_direction(field)` | editable `QLineEdit` / `QTextEdit` — tracks the two-tier rule as the field's content changes |

Wired at: task table `description` + `project` columns (`_AUTO_DIR_KEYS` →
`TextAlignmentRole`), board cards, annotations tab + detail-panel summary,
calendar day list, timesheet tree, running-timer indicator, dependency-graph
nodes (RTL nodes elide-left and right-align inside the box), dependency picker.

Alignment flags here always carry **`Qt.AlignmentFlag.AlignAbsolute`**: a bare
`AlignLeft`/`AlignRight` is direction-relative and an RTL view/widget flips it
to the opposite visual edge, so a Persian string in the Persian UI would land
left. The helpers name the *visual* edge and pin it.

---

## 9. Terminology

`docs/i18n-glossary.md` is the single source of truth. English uses
Taskwarrior's own vocabulary exactly; priority is **بالا / متوسط / پایین** —
**High / Medium / Low** (never «بحرانی»/"Critical" — Taskwarrior has only three
levels). New user-facing strings go through `i18n.t()`; raw Persian literals in
widget files fail `tests/test_no_new_hardcoded_strings.py`.

---

## 10. Motion

Exactly **one** animated pane: the detail panel slides in/out (a
`QVariantAnimation` on the splitter sizes, `main_window._animate_detail`,
0 ms under the `offscreen` platform). This is deliberate — it is the only panel
that appears *over* the working area in response to a selection. The sidebar,
console dock and reports view swap instantly; adding slide transitions there
was evaluated and rejected as motion for its own sake. Any *new* panel that
overlays the workspace should reuse `_animate_detail`'s curve/duration.

---

## 11. The task table

The primary surface, so its rendering rules are specific (`models/task_model.py`):

- **No label prefixes on toolbar controls.** The quick-add, filter and group-by
  controls carry their own placeholder / first-item text; a separate `QLabel:`
  in front of an input is not used.
- **Zebra striping** (M1 design decision) — `setAlternatingRowColors(True)` +
  the `row_alt` palette role, a subtle lift off `surface`. A row's *state*
  colour wash (`_background`) layers on top for overdue / blocked / due-soon /
  waiting rows, and the selection accent bar sits above both. `row_line` gives
  each row a `border_soft` hairline as well.
- **Selection is one continuous band, never per-cell boxes.**
  `QTableView::item:selected` is `background-color` **only** — no `border`
  (a per-item border draws a line on every internal cell edge). The single
  3-px `primary` accent bar on the row's **leading edge** (left in LTR, right
  in RTL) is painted once per selected row in `TaskTable.paintEvent`
  (`_bar_x()` picks the side from `layoutDirection()`), not by QSS.
  `tests/gui/test_task_table_selection.py` guards both.
- **One `indicators` column, not three.** The annotation / recurrence /
  dependency markers share a single narrow column placed right after
  `description` (the model composites 1–3 tinted icons into one pixmap via
  `DecorationRole`), so `status` stays the last visible column and the
  selection band never extends past it into blank-header cells.
- **The description leads.** It is normal-weight-plus (`DemiBold`) `text`;
  everything else is quieter — `id` and `urgency` render in `text_muted`,
  `priority` in its own colour (`H`→`overdue`, `M`→`due_soon`, `L`→muted),
  `status` is **blank for `pending`** (the default state is not worth a column
  of repeated text) and only shows waiting / completed / deleted / recurring.
- **Alignment follows direction, per column.** `id` / `urgency` always trail
  (number convention); `description` follows its own first-strong direction
  (§8); every other column aligns to the reading-start edge for the active
  language (`_halign`).
- Row state (overdue / blocked / due-soon / waiting / completed) still drives a
  full-row background wash and the `due` / description text colour, unchanged
  from the row-state precedence rules.

---

## 12. Wrapped-card lists (annotations tab)

`widgets/annotations_view.py` is the pattern for a list of free-text items that
must wrap to the panel width and read as distinct-but-calm cards, not a single
scrolling text block:

- **Real wrapping, not a single-line item.** Each entry is its own item
  *widget* (`QListWidget.setItemWidget`), not `QListWidgetItem.setText()` — a
  plain list item never word-wraps to the viewport, which is exactly the bug
  this fixed. The list subclass re-applies every item's `sizeHint()` from the
  current viewport width on every `resizeEvent`, and
  `setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)` makes "needs a wider
  panel to read a note" structurally impossible rather than just unlikely.
- **A curated, bounded tint set — never arbitrary colour.** `theme.
  NOTE_TINT_ROLES` (4 roles, same discipline as `boards.COLUMN_ACCENT_ROLES`):
  each is the sidebar's own `bg_alt` washed ~10 % with an existing hue
  (`primary`/`accent`/`success`/`waiting`), defined per theme in `_SHAB`/`_RUZ`
  — a "slight variation," never a jump to a saturated card. Cycled by list
  position (`i % len(NOTE_TINT_ROLES)`), not assigned per-item independently.
- **Selection reuses the table-row convention** (§11): `background-color`
  only, via the same `@selection@` token — no per-card border swap, no new
  selection style invented for this list.
- Timestamp and body are two labels, not one string — the timestamp through
  the shared `calendar_system.active().format_utc()` path, `bidi_isolate`d
  (mirroring the detail-panel audit line), body through `bidi.
  directional_isolate` (§8).

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
