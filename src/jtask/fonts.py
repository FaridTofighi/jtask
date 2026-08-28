"""Vazirmatn font setup instructions and best-effort detection.

A Python process cannot change the terminal emulator's font — that is an
emulator setting.  So jtask prints copy-pasteable setup steps and can check
whether the font family appears installed system-wide.
"""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from .rtl import rtl

__all__ = ["fonts_command", "first_run_hint", "is_vazir_installed"]

_INSTALL = """\
نصب فونت وزیرمتن (Vazirmatn) — جانشین فعالِ «وزیر»:

  # Debian/Ubuntu
  sudo apt install fonts-vazirmatn      # اگر در مخزن موجود بود

  # یا نصب دستی برای کاربر جاری:
  mkdir -p ~/.local/share/fonts
  cd /tmp && curl -LO https://github.com/rastikerdar/vazirmatn/releases/latest/download/vazirmatn-v33.003.zip
  unzip -o vazirmatn-v33.003.zip -d vazirmatn && cp vazirmatn/fonts/ttf/*.ttf ~/.local/share/fonts/
  fc-cache -f
"""

_TERMINALS = """\
تنظیم فونت در ترمینال‌ها (نصب به‌تنهایی کافی نیست؛ پروفایل ترمینال هم باید به آن اشاره کند):

GNOME Terminal:
  Preferences → پروفایل فعال → Text → «Custom font» را روشن کنید و
  «Vazirmatn Regular» را با اندازهٔ دلخواه انتخاب کنید.
  یا از خط فرمان:
    dconf write /org/gnome/terminal/legacy/profiles:/:$(gsettings get org.gnome.Terminal.ProfilesList default | tr -d \\')/font "'Vazirmatn 13'"

Kitty  (~/.config/kitty/kitty.conf):
  font_family      Vazirmatn
  font_size        13.0

Alacritty  (~/.config/alacritty/alacritty.toml):
  [font]
  normal = { family = "Vazirmatn", style = "Regular" }
  size = 13.0

VS Code integrated terminal  (settings.json):
  "terminal.integrated.fontFamily": "Vazirmatn",
  "terminal.integrated.fontSize": 13
"""


def is_vazir_installed() -> tuple[bool, list[str]]:
    """Return (found, matching_family_lines) using ``fc-list`` when available."""
    if not shutil.which("fc-list"):
        return False, []
    try:
        out = subprocess.run(
            ["fc-list"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return False, []
    hits = [
        line
        for line in out.splitlines()
        if "vazirmatn" in line.lower() or "vazir" in line.lower()
    ]
    return bool(hits), hits


def _panel(body: str) -> Panel:
    return Panel(Text(body, justify="left"), border_style="cyan", expand=False)


def first_run_hint() -> Panel:
    return Panel(
        Text(
            rtl("به jtask خوش آمدید! برای نمایش درست فارسی، فونت وزیرمتن را نصب و")
            + "\n"
            + rtl("در پروفایل ترمینال انتخاب کنید.  راهنما:  jtask fonts"),
            justify="right",
        ),
        border_style="magenta",
        expand=False,
    )


def fonts_command(rt, args: list[str]) -> int:
    if args and args[0] == "check":
        found, hits = is_vazir_installed()
        if found:
            body = rtl("فونت وزیرمتن روی سیستم پیدا شد ✔") + "\n\n" + "\n".join(hits[:8])
            body += "\n\n" + rtl(
                "یادآوری: نصب کافی نیست — پروفایل ترمینال هم باید فونت را «Vazirmatn» کند."
            )
        else:
            body = rtl("فونت وزیرمتن پیدا نشد — دستور نصب را در «jtask fonts» ببینید.")
        rt.console.print(_panel(body))
        return 0
    rt.console.print(Group(_panel(_INSTALL), _panel(_TERMINALS)))
    return 0
