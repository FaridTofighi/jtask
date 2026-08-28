"""QApplication bootstrap: RTL, bundled Vazirmatn, theme, main window."""

from __future__ import annotations

import logging
import sys
from importlib import resources
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

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


def build_application(argv: list[str] | None = None) -> tuple[QApplication, object]:
    app = QApplication.instance() or QApplication(
        argv if argv is not None else sys.argv
    )
    app.setApplicationName("jtask-gui")
    app.setOrganizationName("jtask")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    family = _load_fonts()
    app.setFont(QFont(family, 10))

    settings = Settings()
    app.setStyleSheet(render_qss(settings.theme))

    from .main_window import MainWindow

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
