"""jtask command-line entry point.

jtask is a transparent Jalali/Persian layer over Taskwarrior.  Recognised
subcommands are handled here; anything else is passed straight through to the
``task`` binary after only its date tokens are rewritten, so no Taskwarrior
feature is ever hidden.
"""

from __future__ import annotations

import json as jsonlib
import re
import sys
from dataclasses import dataclass, field

from rich.console import Console

from . import config, rewrite, taskwarrior
from .errors import JtaskError
from .render.tables import message_panel, task_table
from .rtl import num, rtl, set_digit_mode
from .themes import Theme, list_themes, load_theme, resolve

KNOWN_COMMANDS = {
    "add", "list", "ls", "modify", "mod", "done", "delete", "del",
    "start", "stop", "annotate", "denotate",
    "waiting", "someday", "projects", "calendar", "cal", "review",
    "chart", "theme", "fonts", "config", "help",
}

_DATE_DISPLAY_COLUMNS = ["due", "scheduled", "wait", "until", "start"]


@dataclass
class Runtime:
    theme: Theme
    console: Console
    gregorian: bool = False
    json_out: bool = False
    date_udas: frozenset[str] = field(default_factory=frozenset)

    def out(self, renderable) -> None:
        self.console.print(renderable)

    def error(self, msg: str) -> None:
        self.console.print(message_panel(msg, self.theme, style="overdue"))


# --------------------------------------------------------------------------
# global flag handling
# --------------------------------------------------------------------------

def _extract_global_flags(argv: list[str]) -> tuple[dict, list[str]]:
    flags: dict = {
        "theme": None,
        "gregorian": False,
        "json": False,
        "digits": None,
    }
    rest: list[str] = []
    it = iter(range(len(argv)))
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("--theme", "-t") and i + 1 < len(argv):
            flags["theme"] = argv[i + 1]
            i += 2
            continue
        if tok.startswith("--theme="):
            flags["theme"] = tok.split("=", 1)[1]
        elif tok == "--gregorian":
            flags["gregorian"] = True
        elif tok == "--json":
            flags["json"] = True
        elif tok == "--digits":
            flags["digits"] = True
        elif tok == "--no-digits":
            flags["digits"] = False
        else:
            rest.append(tok)
        i += 1
    _ = it
    return flags, rest


def _build_runtime(flags: dict) -> Runtime:
    cfg = config.load()
    theme = resolve(
        cfg,
        theme_override=flags["theme"],
        digits_override=flags["digits"],
    )
    set_digit_mode(theme.persian_digits)
    try:
        udas = taskwarrior.date_uda_names()
    except JtaskError:
        udas = frozenset()
    return Runtime(
        theme=theme,
        console=Console(),
        gregorian=flags["gregorian"],
        json_out=flags["json"],
        date_udas=udas,
    )


# --------------------------------------------------------------------------
# shared rendering
# --------------------------------------------------------------------------

def _display_fmt(rt: Runtime) -> str:
    if rt.gregorian:
        return "gregorian"
    return rt.theme.date_format


def _prepare_tasks(rt: Runtime, tasks: list[dict]) -> list[dict]:
    return rewrite.rewrite_export(
        tasks,
        fmt=_display_fmt(rt),
        date_udas=rt.date_udas,
        keep_gregorian=True,
    )


def _emit_tasks(rt: Runtime, tasks: list[dict], *, title: str | None = None) -> None:
    if rt.json_out:
        rows = rewrite.rewrite_export(
            tasks, fmt=_display_fmt(rt), date_udas=rt.date_udas, keep_gregorian=True
        )
        rt.console.print_json(jsonlib.dumps(rows, ensure_ascii=False))
        return
    if not tasks:
        rt.out(message_panel("موردی برای نمایش یافت نشد.", rt.theme))
        return
    prepared = _prepare_tasks(rt, tasks)
    rt.out(task_table(prepared, rt.theme, title=title))


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def _rw(rt: Runtime, args: list[str]) -> list[str]:
    return rewrite.rewrite_args(args, date_udas=rt.date_udas)


def cmd_add(rt: Runtime, args: list[str]) -> int:
    out = taskwarrior.add(_rw(rt, args))
    rt.out(message_panel(out or "کار افزوده شد.", rt.theme, style="completed"))
    return 0


def cmd_list(rt: Runtime, args: list[str]) -> int:
    tasks = taskwarrior.export(_rw(rt, args))
    tasks = [t for t in tasks if t.get("status") not in {"deleted"}]
    _emit_tasks(rt, tasks, title="فهرست کارها")
    return 0


_ID_TOKEN_RE = re.compile(r"^(\d+([-,]\d+)*|[0-9a-fA-F]{8}-[0-9a-fA-F-]+)$")


def _split_filter_mods(args: list[str]) -> tuple[list[str], list[str]]:
    """Split ``modify``-style args into (filter, modifications).

    Leading id / range / uuid tokens form the filter.  If there are none, the
    first token is taken as the filter (e.g. ``project:وب``); the rest are
    modifications.  Mirrors how a Taskwarrior user structures
    ``task <filter> modify <mods>``.
    """
    if not args:
        return [], []
    i = 0
    while i < len(args) and _ID_TOKEN_RE.match(args[i]):
        i += 1
    if i == 0:
        i = 1
    return args[:i], args[i:]


def _filter_verb(rt: Runtime, args: list[str], verb: str, ok_msg: str) -> int:
    rw = _rw(rt, args)
    out = taskwarrior.command(rw, verb)
    rt.out(message_panel(out or ok_msg, rt.theme, style="completed"))
    return 0


def _filter_verb_mods(rt: Runtime, args: list[str], verb: str, ok_msg: str) -> int:
    filt, mods = _split_filter_mods(_rw(rt, args))
    out = taskwarrior.command(filt, verb, mods)
    rt.out(message_panel(out or ok_msg, rt.theme, style="completed"))
    return 0


def cmd_modify(rt: Runtime, args: list[str]) -> int:
    return _filter_verb_mods(rt, args, "modify", "کار به‌روزرسانی شد.")


def cmd_done(rt: Runtime, args: list[str]) -> int:
    return _filter_verb(rt, args, "done", "کار انجام‌شده علامت خورد.")


def cmd_delete(rt: Runtime, args: list[str]) -> int:
    return _filter_verb(rt, args, "delete", "کار حذف شد.")


def cmd_start(rt: Runtime, args: list[str]) -> int:
    return _filter_verb(rt, args, "start", "زمان‌سنجی آغاز شد.")


def cmd_stop(rt: Runtime, args: list[str]) -> int:
    return _filter_verb(rt, args, "stop", "زمان‌سنجی متوقف شد.")


def cmd_annotate(rt: Runtime, args: list[str]) -> int:
    return _filter_verb_mods(rt, args, "annotate", "یادداشت افزوده شد.")


def cmd_denotate(rt: Runtime, args: list[str]) -> int:
    return _filter_verb_mods(rt, args, "denotate", "یادداشت حذف شد.")


def cmd_waiting(rt: Runtime, args: list[str]) -> int:
    tasks = taskwarrior.export(_rw(rt, ["+WAITING", *args]))
    _emit_tasks(rt, tasks, title="در انتظارِ (Waiting-For)")
    return 0


def cmd_someday(rt: Runtime, args: list[str]) -> int:
    tasks = taskwarrior.export(_rw(rt, ["+someday", "status:pending", *args]))
    _emit_tasks(rt, tasks, title="روزی/شاید (Someday-Maybe)")
    return 0


def cmd_projects(rt: Runtime, args: list[str]) -> int:
    from .gtd import project_summary

    project_summary(rt, args)
    return 0


def cmd_calendar(rt: Runtime, args: list[str]) -> int:
    from .render.calendar_view import show_calendar

    show_calendar(rt, args)
    return 0


def cmd_review(rt: Runtime, args: list[str]) -> int:
    from .gtd import weekly_review

    weekly_review(rt, args)
    return 0


def cmd_chart(rt: Runtime, args: list[str]) -> int:
    from .render.charts import run_chart

    return run_chart(rt, args)


def cmd_theme(rt: Runtime, args: list[str]) -> int:
    if not args or args[0] not in {"list", "preview", "set"}:
        rt.error("کاربرد: jtask theme list | preview <نام> | set <نام>")
        return 2
    sub = args[0]
    if sub == "list":
        active = config.load().get("theme")
        for name in list_themes():
            mark = "●" if name == active else "○"
            t = load_theme(name)
            rt.console.print(
                f"{mark} " + rtl(f"{name} — {t.description}"), style=t.color("primary")
            )
        return 0
    if len(args) < 2:
        rt.error("نام تم را وارد کنید.")
        return 2
    name = args[1]
    if sub == "preview":
        try:
            t = load_theme(name)
        except JtaskError as exc:
            rt.error(str(exc))
            return 1
        sample = [
            {"id": 1, "description": "خرید نان", "project": "خانه", "due": num("۱۴۰۳-۰۷-۱۰"),
             "tags": ["خرید"], "priority": "H", "urgency": 8.2, "status": "pending"},
            {"id": 2, "description": "تماس با آرش", "project": "کار", "due": num("۱۴۰۳-۰۷-۱۲"),
             "tags": [], "priority": "M", "urgency": 4.0, "status": "waiting"},
        ]
        rt.console.print(task_table(sample, t, title=f"پیش‌نمایش تم {name}"))
        return 0
    # set
    try:
        load_theme(name)
    except JtaskError as exc:
        rt.error(str(exc))
        return 1
    config.set_value("theme", name)
    rt.out(message_panel(f"تم فعال به «{name}» تغییر کرد.", rt.theme, style="completed"))
    return 0


def cmd_fonts(rt: Runtime, args: list[str]) -> int:
    from .fonts import fonts_command

    return fonts_command(rt, args)


def cmd_config(rt: Runtime, args: list[str]) -> int:
    if not args:
        cfg = config.load()
        for k, v in cfg.items():
            rt.console.print(rtl(f"{k} = {v}"))
        rt.console.print(rtl(f"مسیر: {config.config_path()}"))
        return 0
    sub = args[0]
    if sub == "path":
        rt.console.print(str(config.config_path()))
        return 0
    if sub == "get" and len(args) >= 2:
        rt.console.print(rtl(f"{args[1]} = {config.get(args[1])}"))
        return 0
    if sub == "set" and len(args) >= 3:
        config.set_value(args[1], args[2])
        rt.out(message_panel("ذخیره شد.", rt.theme, style="completed"))
        return 0
    rt.error("کاربرد: jtask config [get <کلید> | set <کلید> <مقدار> | path]")
    return 2


HELP_TEXT = """\
jtask — پوستهٔ فارسی/جلالی برای Taskwarrior

کاربرد:  jtask [پرچم‌های سراسری] <فرمان> [آرگومان‌ها]

فرمان‌ها:
  add        افزودن کار (تاریخ‌ها جلالی: due:1403.07.10 یا due:فردا)
  list       فهرست کارها (همهٔ فیلترهای Taskwarrior پشتیبانی می‌شود)
  modify     تغییر کار(ها)
  done       علامت‌گذاری انجام‌شده
  delete     حذف کار
  start/stop شروع/توقف زمان‌سنجی
  annotate   افزودن یادداشت
  waiting    نمای «در انتظارِ» (GTD)
  someday    نمای «روزی/شاید» (GTD)
  projects   خلاصهٔ پروژه‌ها
  calendar   تقویم جلالی کارها
  review     مرور هفتگی هدایت‌شده (GTD)
  chart      نمودارهای ترمینالی (burndown, projects, status, heatmap, timeline, velocity)
  theme      list | preview <نام> | set <نام>
  fonts      راهنمای نصب فونت وزیرمتن + بررسی نصب
  config     مشاهده/تنظیم پیکربندی

پرچم‌های سراسری:
  --theme <نام>     تم را برای این اجرا تغییر بده
  --gregorian       تاریخ‌ها را میلادی نشان بده (اشکال‌زدایی)
  --json            خروجی JSON با هر دو نمایش جلالی و میلادی
  --digits/--no-digits   ارقام فارسی را روشن/خاموش کن

هر فرمان ناشناخته مستقیماً به «task» منتقل می‌شود (فقط توکن‌های تاریخ جلالی بازنویسی می‌شوند).
"""


def cmd_help(rt: Runtime, args: list[str]) -> int:
    rt.console.print(rtl(HELP_TEXT) if False else HELP_TEXT)
    return 0


_DISPATCH = {
    "add": cmd_add,
    "list": cmd_list,
    "ls": cmd_list,
    "modify": cmd_modify,
    "mod": cmd_modify,
    "done": cmd_done,
    "delete": cmd_delete,
    "del": cmd_delete,
    "start": cmd_start,
    "stop": cmd_stop,
    "annotate": cmd_annotate,
    "denotate": cmd_denotate,
    "waiting": cmd_waiting,
    "someday": cmd_someday,
    "projects": cmd_projects,
    "calendar": cmd_calendar,
    "cal": cmd_calendar,
    "review": cmd_review,
    "chart": cmd_chart,
    "theme": cmd_theme,
    "fonts": cmd_fonts,
    "config": cmd_config,
    "help": cmd_help,
}


def _first_run_notice(rt: Runtime) -> None:
    if config.is_first_run():
        from .fonts import first_run_hint

        rt.console.print(first_run_hint())
        config.mark_first_run_done()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    flags, rest = _extract_global_flags(argv)

    if not rest or rest[0] in ("-h", "--help"):
        rest = ["help"]

    try:
        rt = _build_runtime(flags)
    except JtaskError as exc:
        Console().print(message_panel(str(exc), load_theme("شب"), style="overdue"))
        return 1

    _first_run_notice(rt)

    cmd = rest[0]
    cmd_args = rest[1:]

    try:
        if cmd in _DISPATCH:
            return _DISPATCH[cmd](rt, cmd_args)
        # transparent passthrough: rewrite date tokens, hand the rest to `task`
        rewritten = rewrite.rewrite_args(rest, date_udas=rt.date_udas)
        return taskwarrior.passthrough(rewritten)
    except JtaskError as exc:
        rt.error(str(exc))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
