"""QApplication bootstrap: RTL, bundled Vazirmatn, theme, main window."""

from __future__ import annotations

import logging
import sys
from importlib import resources
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication

try:  # honour fractional display scaling for crisp Persian text
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
except Exception:  # pragma: no cover - already set / unsupported
    pass

from .settings import Settings
from .theme import render_qss

log = logging.getLogger("jtask_gui")

_FONT_FILES = ("Vazirmatn-Regular.ttf", "Vazirmatn-Medium.ttf", "Vazirmatn-Bold.ttf")

_restart_requested = False


def request_restart() -> None:
    """Ask ``main()`` to re-exec the process once Qt has fully shut down.

    Re-exec (rather than ``QProcess.startDetached`` from the still-live process)
    keeps it a single process with one fresh D-Bus connection — no
    ``xdg-desktop-portal`` "connection already associated with an application
    ID" warning, no brief second window.
    """
    global _restart_requested
    _restart_requested = True
    QApplication.quit()


def _load_fonts() -> str:
    """Load bundled Vazirmatn; return the family name (falls back gracefully)."""
    loaded_family = ""
    fonts_dir = resources.files(__package__) / "resources/fonts"
    for name in _FONT_FILES:
        try:
            with resources.as_file(fonts_dir / name) as p:
                fid = QFontDatabase.addApplicationFont(str(p))
        except (FileNotFoundError, OSError):
            fid = -1
        if fid == -1:
            log.warning("failed to load bundled font %s", name)
            continue
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            loaded_family = fams[0]
    if not loaded_family:
        # bundled load failed entirely — try a system copy, else Qt default
        if "Vazirmatn" in QFontDatabase.families():
            return "Vazirmatn"
        log.warning("Vazirmatn unavailable; using the system default font")
        return QApplication.font().family()
    return loaded_family


def app_icon() -> QIcon:
    icon = QIcon()
    base = resources.files(__package__) / "resources"
    for size in (256, 128, 64, 48):
        try:
            with resources.as_file(base / f"icon-{size}.png") as p:
                icon.addFile(str(p))
        except (FileNotFoundError, OSError):
            pass
    return icon


_QT_HANDLER_INSTALLED = False

# Benign Qt noise we don't want on the user's console. These are cosmetic —
# the app-id registration failing only affects how the desktop portal labels
# jtask, not any functionality.
_QT_SUPPRESS = (
    "Failed to register with host portal",
    "Could not register app ID",
)


def _install_qt_message_handler() -> None:
    global _QT_HANDLER_INSTALLED
    if _QT_HANDLER_INSTALLED:
        return
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    _levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(mode, _context, message: str) -> None:
        if any(s in message for s in _QT_SUPPRESS):
            log.debug("suppressed Qt message: %s", message)
            return
        logging.getLogger("jtask_gui.qt").log(_levels.get(mode, logging.INFO), "%s", message)

    qInstallMessageHandler(handler)
    _QT_HANDLER_INSTALLED = True


def _apply_taskwarrior_overrides(settings) -> None:
    """Push the user's binary / TASKDATA / TASKRC overrides into the environment
    before anything calls ``task``. Empty settings leave the ambient env alone.
    ``jtask.taskwarrior.binary()`` already honours ``JTASK_TASK_BIN``."""
    import os

    for value, var in (
        (settings.task_bin, "JTASK_TASK_BIN"),
        (settings.taskdata, "TASKDATA"),
        (settings.taskrc, "TASKRC"),
    ):
        if value:
            os.environ[var] = value
            log.info("taskwarrior override: %s=%s", var, value)


def build_application(argv: list[str] | None = None) -> tuple[QApplication, object]:
    _install_qt_message_handler()

    # Identity (name / org / desktop file) MUST be set before the QApplication is
    # constructed. Qt registers the app-id with the desktop portal once at
    # construction; re-setting any of these afterwards makes it re-register on
    # the same D-Bus connection → the portal rejects it with a noisy
    # ``qt.qpa.services: … Connection already associated with an application ID``.
    # In production ``QApplication.instance()`` is None here so this is
    # pre-construction; under in-process pytest-qt an app already exists, which
    # is harmless (offscreen, no portal) and covered by the message handler.
    QApplication.setApplicationName("jtask-gui")
    QApplication.setOrganizationName("jtask")
    QApplication.setDesktopFileName("jtask-gui")  # StartupWMClass / Wayland app-id

    app = QApplication.instance() or QApplication(
        argv if argv is not None else sys.argv
    )
    app.setApplicationDisplayName("jtask")  # cosmetic; never touches the app-id
    app.setWindowIcon(app_icon())

    family = _load_fonts()
    app.setFont(QFont(family, 10))

    settings = Settings()
    _apply_taskwarrior_overrides(settings)

    from .i18n import is_rtl, set_language

    set_language(settings.language)
    # Layout direction follows the UI language only (never the calendar system).
    app.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if is_rtl() else Qt.LayoutDirection.LeftToRight
    )

    qss = render_qss(settings.theme)
    app.setStyleSheet(qss)
    if app.styleSheet():
        log.info("theme %r applied (%d chars of QSS)", settings.theme, len(qss))
    else:  # pragma: no cover
        log.warning("stylesheet did not stick — UI will look unstyled")

    from .main_window import MainWindow

    if not settings.wizard_done and QApplication.instance().platformName() != "offscreen":
        from .widgets.first_run import FirstRunWizard

        wiz = FirstRunWizard(settings)
        wiz.exec()  # _finish() applies choices if accepted
        # Mark it done however the dialog closed (button, Esc, window X) — the
        # wizard is a one-time thing; it must never re-appear on the next launch.
        settings.wizard_done = True
        settings.sync()
        app.setStyleSheet(render_qss(settings.theme))

    window = MainWindow(settings)

    def _teardown() -> None:
        # Stop polling and drain in-flight workers before the process exits, so
        # a background thread can't emit onto a freed signal object (which
        # aborts the interpreter). Covers normal quit and the restart flow.
        from . import workers

        try:
            window._notify.stop()
        except Exception:  # noqa: BLE001
            pass
        workers.shutdown()

    app.aboutToQuit.connect(_teardown)

    window.show()
    return app, window


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        filename=str(Path.home() / ".cache" / "jtask-gui.log"),
        filemode="a",
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        (Path.home() / ".cache").mkdir(exist_ok=True)
    except OSError:
        pass
    app, _window = build_application(argv)
    rc = app.exec()
    if _restart_requested:
        _reexec()
    return rc


def _reexec() -> None:
    """Replace this process with a fresh instance (used by the restart flow)."""
    import os

    args = [sys.executable, *sys.argv]
    log.info("re-exec for restart: %s", args)
    try:
        os.execv(sys.executable, args)
    except OSError:  # pragma: no cover - extremely unlikely
        import subprocess

        subprocess.Popen(args)  # noqa: S603
        raise SystemExit(0) from None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
