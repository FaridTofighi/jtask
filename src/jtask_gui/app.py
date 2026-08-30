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


def build_application(argv: list[str] | None = None) -> tuple[QApplication, object]:
    app = QApplication.instance() or QApplication(
        argv if argv is not None else sys.argv
    )
    app.setApplicationName("jtask-gui")
    app.setApplicationDisplayName("jtask")
    app.setOrganizationName("jtask")
    app.setDesktopFileName("jtask-gui")  # StartupWMClass / Wayland app-id
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setWindowIcon(app_icon())

    family = _load_fonts()
    app.setFont(QFont(family, 10))

    settings = Settings()

    from .i18n import set_language

    set_language(settings.language)

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
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
