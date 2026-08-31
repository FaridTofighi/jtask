# jtask-gui i18n glossary — terminology source of truth

Every user-facing term, its Persian (fa) label and its English (en) label. For
Taskwarrior attributes/concepts, the **TW** column confirms the English label
matches Taskwarrior's own vocabulary (verified against `task` 3.5.0 man pages:
`task(1)`, `taskrc(5)`, `task-color(5)`, `task-sync(5)`).

**This document drives the catalog.** The exhaustive machine list is
`src/jtask_gui/i18n/fa.py` (fa) and `src/jtask_gui/i18n/en.py` (en). The English
column here is the wording i5 must ship — it must be consistent everywhere (never
"Due" in one screen and "Deadline" in another for the same concept).

Status of the English column: **shipped in i5.** `src/jtask_gui/i18n/en.py` now
carries a full English override of every key in `fa.py`; the wording here is what
it ships. `tests/gui/test_i5_english_catalog.py` enforces coverage, the
"no stray Persian" rule, the Taskwarrior-vocabulary terms, and the §8 clean-ups.

---

## 1. Taskwarrior attributes & concepts (must match TW)

| Concept | fa | en | TW |
|---|---|---|---|
| task | کار | task | ✓ `task` |
| description | شرح | Description | ✓ `description` |
| project | پروژه | Project | ✓ `project` (dotted hierarchy) |
| tags | برچسب‌ها | Tags | ✓ `tags` (`+tag` / `-tag`) |
| priority | اولویت | Priority | ✓ `priority` — values `H`/`M`/`L` |
| priority H | بالا | High | ✓ (`priority:H`) |
| priority M | متوسط | Medium | ✓ (`priority:M`) |
| priority L | پایین | Low | ✓ (`priority:L`) |
| due | سررسید | Due | ✓ `due` |
| scheduled | زمان‌بندی | Scheduled | ✓ `scheduled` |
| wait | تاریخ انتظار / انتظار\* | Wait | ✓ `wait` |
| until | مهلت | Until | ✓ `until` |
| entry | ایجاد | Entry | ✓ `entry` (creation time) |
| modified | آخرین ویرایش | Modified | ✓ `modified` |
| end | پایان | End | ✓ `end` (completion/deletion time) |
| start | شروع زمان‌سنجی | Start | ✓ `start` (active-timer timestamp) |
| recurrence | تکرار | Recurrence | ✓ `recur` |
| dependencies | وابستگی‌ها | Dependencies | ✓ `depends` |
| annotation | یادداشت | Annotation | ✓ `annotation` (`annotate`/`denotate`) |
| urgency | فوریت | Urgency | ✓ `urgency` (computed) |
| UUID | شناسه (UUID) | UUID | ✓ `uuid` |
| id | شناسه | ID | ✓ `id` (working id) |
| context | زمینه | Context | ✓ `context` (read/write filters) |
| UDA | ویژگی سفارشی | UDA (user-defined attribute) | ✓ `uda.*` |

\* jtask historically used two Persian wordings for priority/wait in different
screens (detail panel vs. Add/bulk dialogs). i5 **unifies** to one per language:
unified fa = «بالا / متوسط / پایین», en = «High / Medium / Low»; wait = «تاریخ انتظار» / «Wait».
(«بحرانی» was tried in i5 then reverted in d5 — «Critical» implies a 4th level Taskwarrior doesn't have.)

### Statuses (TW `status:` values)

| fa | en | TW |
|---|---|---|
| در جریان | Pending | ✓ `pending` |
| در انتظار | Waiting | ✓ `waiting` |
| انجام‌شده / تکمیل‌شده\* | Completed | ✓ `completed` |
| حذف‌شده | Deleted | ✓ `deleted` |
| تکرارشونده | Recurring | ✓ `recurring` |
| مسدودشده | Blocked | ✓ virtual tag `+BLOCKED` |

\* «انجام‌شده» and «تکمیل‌شده» both appear today; i5 → one (proposed «انجام‌شده» / "Completed").

### Virtual tags (filter builder picker — TW `+TAG`)

| fa | en | TW |
|---|---|---|
| معوق | Overdue | ✓ `+OVERDUE` |
| سررسید امروز | Due today | ✓ `+DUE` (today) |
| آماده | Ready | ✓ `+READY` |
| فعال | Active | ✓ `+ACTIVE` |
| مسدود | Blocked | ✓ `+BLOCKED` |
| بازدارنده | Blocking | ✓ `+BLOCKING` |
| در انتظار | Waiting | ✓ `+WAITING` |
| برچسب‌دار | Tagged | ✓ `+TAGGED` |
| یادداشت‌دار | Annotated | ✓ `+ANNOTATED` |

---

## 2. Commands / actions (TW verbs)

| fa | en | TW |
|---|---|---|
| افزودن کار | Add Task | ✓ `add` |
| ثبت کار انجام‌شده | Log completed task | ✓ `log` |
| انجام‌شده (کردن) | Mark done | ✓ `done` |
| حذف | Delete | ✓ `delete` |
| تکثیر | Duplicate | ✓ `duplicate` |
| افزودن به شرح | Append to description | ✓ `append` |
| پیش‌افزودن به شرح | Prepend to description | ✓ `prepend` |
| پاک‌سازی برای همیشه | Purge permanently | ✓ `purge` |
| واگرد | Undo | ✓ `undo` |
| شروع زمان‌سنجی | Start timer | ✓ `start` |
| توقف زمان‌سنجی | Stop timer | ✓ `stop` |
| یادداشت (افزودن/حذف) | Annotate / Denotate | ✓ `annotate` / `denotate` |
| ویرایش گروهی | Bulk edit | — (jtask; maps to `task <ids> modify`) |
| خروجی گرفتن | Export | ✓ `export` |
| ورود از فایل | Import | ✓ `import` |
| همگام‌سازی | Sync | ✓ `synchronize` / `sync` |
| پیکربندی | Configuration | ✓ `config` / `show` |
| تشخیص | Diagnostics | ✓ `diagnostics` |
| آمار | Statistics | ✓ `stats` |
| ماشین‌حساب | Calculator | ✓ `calc` |
| راهنمای فرمان‌ها | Command reference | ✓ `help` |
| کنسول فرمان | Command Console | — (jtask escape hatch) |

---

## 3. GTD / planning views (standard planning vocabulary, not literal TW)

| fa (label) | fa (stable key — i2) | en |
|---|---|---|
| امروز | `today` | Today |
| این هفته | `week` | This Week |
| معوق | `overdue` | Overdue |
| اقدامات بعدی | `next` | Next Actions |
| در انتظار | `waiting` | Waiting For |
| مسدودشده | `blocked` | Blocked |
| تکمیل‌شده | `completed` | Completed |
| گزارش‌ها و نمودارها | `reports` | Reports & Charts |
| برگهٔ زمان | `timesheet` | Timesheet |

(There is no "Someday/Maybe" quick-view today; if added later, en = "Someday/Maybe".)

---

## 4. Reports & charts

| fa | en |
|---|---|
| نمودار سوختن | Burndown chart |
| گراف تاریخچه (انباشته) | History graph (stacked) |
| تاریخچه (گروهی) | History (grouped) |
| خلاصهٔ پروژه‌ها | Project summary |
| تقویم جلالی | Calendar |
| گزارش پروژه‌ها | Projects report |
| گزارش برچسب‌ها | Tags report |
| روزانه / هفتگی / ماهانه | Daily / Weekly / Monthly |
| افزوده / تکمیل‌شده / حذف‌شده (سری‌ها) | Added / Completed / Deleted |
| تعداد کار (محور) | Task count |

---

## 5. Configuration surface (M8 managers)

| fa | en | TW |
|---|---|---|
| مدیریت Taskwarrior | Manage Taskwarrior | — |
| مقدار فعلی / پیش‌فرض / بازنویسی‌شده | Current / Default / Overridden | ✓ (`task show`) |
| بازگردانی به پیش‌فرض | Reset to default | — (`task config <name>`) |
| فیلتر خواندن / نوشتن | Read filter / Write filter | ✓ `context.<n>.read` / `.write` |
| فعال‌سازی / غیرفعال‌سازی زمینه | Activate / Deactivate context | ✓ `context <n>` / `context none` |
| نوع: رشته / عددی / تاریخ / مدت | Type: string / numeric / date / duration | ✓ `uda.<n>.type` |
| مقادیر مجاز | Allowed values | ✓ `uda.<n>.values` |
| گزارش داخلی / سفارشی | Built-in / Custom report | ✓ (built-in report set) |
| ستون‌ها / برچسب ستون‌ها / مرتب‌سازی / قالب تاریخ | Columns / Column labels / Sort / Date format | ✓ `report.<n>.{columns,labels,sort,dateformat}` |

---

## 6. Common UI chrome

| fa | en |
|---|---|
| انصراف | Cancel |
| بستن | Close |
| ذخیره | Save |
| ذخیرهٔ تغییرات | Save changes |
| اعمال | Apply |
| افزودن | Add |
| حذف | Delete |
| تأیید | Confirm |
| رونوشت | Copy |
| انتخاب… | Choose… |
| بدون | None |
| همه | All |
| نام | Name |
| از … تا | From … to |
| تنظیمات | Settings |
| زبان | Language |
| پوسته | Theme |
| ارقام فارسی | Persian digits |
| اعلان‌ها | Notifications |

---

## 7. Calendar system — Jalali names in English mode (transliteration, NOT translation)

When Language = English and Calendar = Jalali, month/weekday names are shown as
**Latin transliterations of the Persian names** — never "Saturday" for شنبه.
Canonical table (finalised in i5, stored with `JalaliCalendarSystem`):

**Weekdays** (week starts Saturday): Shanbeh · Yekshanbeh · Doshanbeh ·
Seshanbeh · Chaharshanbeh · Panjshanbeh · Jomeh

**Months**: Farvardin · Ordibehesht · Khordad · Tir · Mordad · Shahrivar ·
Mehr · Aban · Azar · Dey · Bahman · Esfand

Gregorian mode uses the locale's real names (January…, Monday…).

---

## 8. Wording clean-ups i5 must make (single wording per concept)

- priority H/M/L: pick one fa set + one en set (see §1 note).
  **Done (i5, revised d5):** fa = «بالا / متوسط / پایین», en = «High / Medium / Low» —
  across `priority.*`, `detail.priority.*`, `fb.priority.*`, `quickadd.priority.*`,
  `col.priority.*`.
- "completed" status: «انجام‌شده» everywhere (drop «تکمیل‌شده» as a *status*;
  keep «تکمیل‌شده» only where it means the GTD quick-view "Completed").
  **Done (i5):** status/`stats`/`col.status` all «انجام‌شده» / "Completed";
  `view.completed` keeps the GTD sense.
- "wait" attribute label: «تاریخ انتظار» everywhere (drop bare «انتظار»).
  **Done (i5):** `detail.date.wait`, `col.wait`, `quickadd.preview.wait` unified.
- history-view vs. filter-builder both say «در انتظار» for Waiting — already consistent.
