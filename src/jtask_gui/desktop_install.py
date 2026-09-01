"""Register jtask-gui with the freedesktop desktop environment.

A ``pip``/``pipx`` install drops only the ``jtask-gui`` launcher — no ``.desktop``
entry and no themed icon — so GNOME/KDE/XFCE cannot match the running window to
an application and fall back to a generic icon (the window's own
``_NET_WM_ICON`` is not enough on GNOME, which identifies apps by
``StartupWMClass`` → an installed ``*.desktop`` file).

``jtask-gui --install-desktop`` writes the entry and icons into
``$XDG_DATA_HOME`` (``~/.local/share`` by default); ``build_application`` prints a
one-line hint on startup when they are missing. The system-package /
AppImage path keeps using ``packaging/jtask-gui.desktop`` directly —
``tests/gui/test_desktop_install.py`` asserts the two never drift.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

log = logging.getLogger("jtask_gui")

APP_ID = "jtask-gui"

# Kept byte-identical to packaging/jtask-gui.desktop except the Exec line, which
# is filled in at install time with the resolved launcher path.
_DESKTOP_ENTRY = """\
[Desktop Entry]
Type=Application
Name=jtask
Name[fa]=جی‌تسک
GenericName=Task Manager
GenericName[fa]=مدیریت کارها
Comment=Persian/Jalali desktop front-end for Taskwarrior
Comment[fa]=رابط دسکتاپ فارسی/جلالی برای Taskwarrior
Exec={exec}
Icon=jtask-gui
Terminal=false
Categories=Office;ProjectManagement;Qt;
Keywords=task;todo;taskwarrior;jalali;persian;
StartupWMClass=jtask-gui
StartupNotify=true
"""

# raster icon basenames in resources/ -> hicolor size folder
_PNG_SIZES = (48, 64, 128, 256)


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def desktop_path() -> Path:
    return data_home() / "applications" / f"{APP_ID}.desktop"


def installed() -> bool:
    return desktop_path().is_file()


def _launcher() -> str:
    """Absolute path to the ``jtask-gui`` entry point, or the bare name if it is
    not on ``PATH`` (a login shell usually has ``~/.local/bin``)."""
    found = shutil.which(APP_ID)
    if found:
        return found
    arg0 = Path(sys.argv[0])
    if arg0.name == APP_ID and arg0.exists():
        return str(arg0.resolve())
    return APP_ID


def _run_quiet(*cmd: str) -> None:
    try:
        subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        pass


def install() -> Path:
    """Write the ``.desktop`` entry and icons under ``$XDG_DATA_HOME``.

    Returns the path of the installed ``.desktop`` file. Overwrites any existing
    copy so a reinstall / upgrade refreshes it.
    """
    apps = data_home() / "applications"
    icons = data_home() / "icons" / "hicolor"
    apps.mkdir(parents=True, exist_ok=True)

    dest = apps / f"{APP_ID}.desktop"
    dest.write_text(_DESKTOP_ENTRY.format(exec=_launcher()), encoding="utf-8")
    dest.chmod(0o644)

    res = resources.files(__package__) / "resources"
    for size in _PNG_SIZES:
        src = res / f"icon-{size}.png"
        if src.is_file():
            out = icons / f"{size}x{size}" / "apps"
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{APP_ID}.png").write_bytes(src.read_bytes())
    svg = res / "icon.svg"
    if svg.is_file():
        out = icons / "scalable" / "apps"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{APP_ID}.svg").write_bytes(svg.read_bytes())

    _run_quiet("update-desktop-database", str(apps))
    _run_quiet("gtk-update-icon-cache", "-f", "-t", str(icons))

    log.info("desktop entry installed: %s", dest)
    return dest


def uninstall() -> None:
    """Remove everything :func:`install` wrote."""
    desktop_path().unlink(missing_ok=True)
    icons = data_home() / "icons" / "hicolor"
    for size in _PNG_SIZES:
        (icons / f"{size}x{size}" / "apps" / f"{APP_ID}.png").unlink(missing_ok=True)
    (icons / "scalable" / "apps" / f"{APP_ID}.svg").unlink(missing_ok=True)
    _run_quiet("update-desktop-database", str(data_home() / "applications"))
    _run_quiet("gtk-update-icon-cache", "-f", "-t", str(icons))
