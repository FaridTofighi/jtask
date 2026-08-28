<div dir="rtl">

# jtask — پوستهٔ فارسی/جلالی برای Taskwarrior

`jtask` یک لایهٔ نازک و شفاف روی [Taskwarrior](https://taskwarrior.org) است که همهٔ
تاریخ‌ها را **جلالی (شمسی)** می‌کند، رابط را کاملاً **فارسی و راست‌به‌چپ** نشان می‌دهد،
**نمودارهای ترمینالی** می‌کشد و **قالب‌بندی (تم) دلخواه** دارد — بدون آن‌که هیچ قابلیتی از
Taskwarrior از دست برود.

Taskwarrior هیچ پشتیبانی بومی از تقویم جلالی ندارد؛ داده‌ها را همیشه میلادی/UTC ذخیره
می‌کند. `jtask` این شکاف را پر می‌کند: **ورودی و خروجی همه جلالی است**، ولی داده‌های روی
دیسک دست‌نخورده و ۱۰۰٪ سازگار با `task` باقی می‌مانند. `jtask` هرگز مستقیم در فایل‌های
Taskwarrior نمی‌نویسد؛ فقط `task` را صدا می‌زند (`task export` برای خواندن،
`task add` / `task <فیلتر> <فرمان>` برای نوشتن).

## نصب

```bash
# ۱) فونت وزیرمتن (برای نمایش درست فارسی در ترمینال)
jtask fonts            # راهنمای کامل نصب و تنظیم ترمینال را چاپ می‌کند

# ۲) خودِ jtask
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

نیازمندی‌ها: پایتون ۳٫۱۰ به بالا و نصب‌بودن `task` (Taskwarrior 3.x) روی `PATH`.

## راه‌اندازی سریع

```bash
jtask fonts check                       # آیا وزیرمتن نصب است؟
jtask add "تماس با آرش" due:1403.07.10   # افزودن کار با سررسید جلالی
jtask add "جلسه" due:فردا priority:H     # تاریخ نسبی فارسی
jtask list                              # فهرست کارها؛ همهٔ تاریخ‌ها جلالی
jtask chart burndown                    # نمودار سوختن در ترمینال
jtask theme set روز                     # تغییر تم به روشن
```

## فرمان‌ها

| فرمان | کار |
|---|---|
| `add` | افزودن کار — تاریخ‌ها جلالی: `due:1403.07.10`، `due:1403.07.10T14:30`، `due:فردا` |
| `list` | فهرست کارها؛ همهٔ فیلترهای Taskwarrior پشتیبانی می‌شود (`jtask list project:وب +مهم`) |
| `modify` | تغییر کار(ها): `jtask modify 1 due:1403.08.01` یا `jtask modify project:وب +مهم` |
| `done` / `delete` | انجام‌شده/حذف |
| `start` / `stop` | شروع/توقف زمان‌سنجی |
| `annotate` | افزودن یادداشت: `jtask annotate 2 "پیگیری با ایمیل"` |
| `waiting` | نمای «در انتظارِ» (GTD) — کارهای `+WAITING` |
| `someday` | نمای «روزی/شاید» (GTD) — کارهای `+someday` |
| `projects` | خلاصهٔ پروژه‌ها با شمار باز/مسدود/عقب‌افتاده |
| `calendar` | تقویم ماه جلالی (`jtask calendar 1403.07`)؛ `--week` برای نمای هفته |
| `review` | مرور هفتگی هدایت‌شدهٔ GTD |
| `chart <نوع>` | `burndown`، `projects`، `status`، `heatmap`، `timeline`، `velocity` |
| `theme` | `list` \| `preview <نام>` \| `set <نام>` |
| `fonts` | راهنمای نصب وزیرمتن؛ `fonts check` برای بررسی نصب |
| `config` | `get <کلید>` \| `set <کلید> <مقدار>` \| `path` |

هر فرمان یا آرگومانی که `jtask` نشناسد، **مستقیماً به `task` منتقل می‌شود** و فقط
توکن‌های تاریخ جلالی بازنویسی می‌شوند — پس هیچ قابلیت Taskwarrior (UDA، تکرار،
وابستگی، context و…) از دسترس خارج نمی‌شود.

### پرچم‌های سراسری

| پرچم | کار |
|---|---|
| `--theme <نام>` | تم را فقط برای این اجرا عوض کن |
| `--gregorian` | تاریخ‌ها را میلادی نشان بده (اشکال‌زدایی) |
| `--json` | خروجی JSON با **هر دو** نمایش جلالی و میلادی برای هر فیلد |
| `--digits` / `--no-digits` | ارقام فارسی را روشن/خاموش کن |

## تاریخ‌های نسبی فارسی

`امروز`، `فردا`، `دیروز`، `پس‌فردا`، `پریروز`، `۳ روز دیگر`، `۵ روز پیش`،
`این شنبه` (…تا `این جمعه`)، `شنبه بعد`، `هفتهٔ بعد`، `پایان هفته`، `اول ماه بعد`،
`آخر ماه`. هفته از **شنبه** شروع می‌شود.

جداکننده‌ها: `-`، `/`، `.` — و ارقام فارسی یا انگلیسی هر دو پذیرفته می‌شوند
(`۱۴۰۳/۰۷/۱۰` و `1403/07/10`).

## تم‌ها

دو تم آماده: **`شب`** (تیره) و **`روز`** (روشن). برای تم دلخواه، یک فایل YAML در
`~/.config/jtask/themes/` بگذارید — بدون هیچ تغییری در کد:

</div>

```yaml
name: من
colors:
  primary: "#7fd1e0"
  overdue: "#ff5c57"
  due_soon: "#f3f99d"
  waiting: "#57c7ff"
  completed: "#5af78e"
  blocked: "#ff6ac1"
table:
  box: ROUNDED
persian_digits: true
date_format: short      # short: ۱۴۰۳-۰۷-۱۰   |   long: چهارشنبه ۱۰ مهر ۱۴۰۳
```

<div dir="rtl">

## رابط گرافیکی دسکتاپ (`jtask-gui`)

یک برنامهٔ دسکتاپ PyQt6 نیز در حال ساخت است (گام نخست تکمیل شده): پوستهٔ برنامه با
نوار پیمایش راست‌به‌چپ، جدول کارها مبتنی بر مدل Qt، پنل جزئیات با همهٔ ویژگی‌ها و
تاریخ‌گزین جلالی، افزودن سریع با پیش‌نمایش زنده، دو پوستهٔ کامل (`شب`/`روز`)،
فونت وزیرمتن همراهِ برنامه، و کنسول فرمان خام. نمودارها و تقویم تعاملی در گام بعدی.

```bash
pip install -e ".[gui]"
jtask-gui
```

همهٔ فراخوانی‌های `task` خارج از رشتهٔ رابط اجرا می‌شوند؛ داده‌های Taskwarrior هرگز
مستقیم نوشته نمی‌شوند. جزئیات طراحی در `docs/jtask-gui-design.md`.

## محدودیت‌های شناخته‌شده

- زمان‌ها با **منطقهٔ زمانی سیستم** تفسیر می‌شوند (Taskwarrior همه‌چیز را UTC ذخیره
  می‌کند). برای کاربران ایران این یعنی رفت‌وبرگشت تاریخِ بدون‌ساعت دقیق است.
- در فرمان‌های منتقل‌شده به `task`، ترتیب آرگومان‌ها همان قاعدهٔ Taskwarrior است
  (فیلتر پیش از فرمان): `jtask due.before:1403.08.01 export`.
- `jtask` نمی‌تواند فونت ترمینال را عوض کند؛ این کارِ تنظیماتِ خودِ ترمینال است
  (`jtask fonts`).

</div>

---

## English summary

`jtask` is a transparent Persian/Jalali layer over Taskwarrior. Every date you type or
see is Jalali (Solar Hijri); the UI is Persian and right-to-left. Taskwarrior's own data
stays untouched Gregorian/UTC — `jtask` only shells out to the `task` binary
(`task export` to read, `task add` / `task <filter> <verb>` to write) and rewrites
date-bearing tokens in both directions.

- **Dates everywhere Jalali**: `due:`, `scheduled:`, `wait:`, `until:`, `entry`, `start`,
  `end`, `modified`, date UDAs, and `attr.before:` / `attr.after:` modifiers. Persian
  relative expressions (`فردا`, `۳ روز دیگر`, `شنبه بعد`, …) resolve before conversion.
- **Charts in the terminal**: `burndown`, `projects`, `status`, `heatmap` (Saturday-first),
  `timeline`, `velocity` — all with Jalali axes and theme colors.
- **Themes**: built-in `شب` / `روز`; drop a YAML into `~/.config/jtask/themes/` for your own.
- **Lossless passthrough**: unknown subcommands/args go straight to `task`.
- `--json` emits both Jalali and Gregorian representations per field;
  `--gregorian` shows raw Gregorian for debugging.

### Desktop GUI (`jtask-gui`)

A PyQt6 desktop app built on the same core (Milestone 1 complete: RTL app shell,
Qt-model task table, full detail panel with Jalali date pickers, live-preview
quick-add, two themes, bundled Vazirmatn, raw command console). Charts and the
interactive Jalali calendar land in Milestone 2. See `docs/jtask-gui-design.md`.

```bash
pip install -e ".[gui]"
jtask-gui
```

### Development

```bash
pip install -e ".[dev,gui]"
pytest -q          # 118 tests: core (jalali/rewrite/rtl/reports) + pytest-qt GUI suite
ruff check . && mypy      # mypy targets the framework-agnostic core
```
