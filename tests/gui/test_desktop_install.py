"""`jtask-gui --install-desktop` registers the app so the desktop shows its icon."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from jtask_gui import desktop_install


@pytest.fixture
def xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    return tmp_path


def test_install_writes_the_entry_and_the_themed_icons(xdg):
    path = desktop_install.install()

    assert path == xdg / "applications" / "jtask-gui.desktop"
    assert desktop_install.installed()

    text = path.read_text(encoding="utf-8")
    assert "StartupWMClass=jtask-gui" in text          # GNOME window matching
    assert "Icon=jtask-gui" in text
    exec_line = next(ln for ln in text.splitlines() if ln.startswith("Exec="))
    assert exec_line[len("Exec="):].strip()            # a real launcher path

    png = xdg / "icons" / "hicolor" / "256x256" / "apps" / "jtask-gui.png"
    assert png.is_file() and png.stat().st_size > 0
    assert (xdg / "icons" / "hicolor" / "scalable" / "apps" / "jtask-gui.svg").is_file()


def test_uninstall_removes_everything_it_wrote(xdg):
    desktop_install.install()
    desktop_install.uninstall()

    assert not desktop_install.installed()
    assert not (xdg / "icons" / "hicolor" / "256x256" / "apps" / "jtask-gui.png").exists()


def test_embedded_entry_matches_the_packaging_file():
    """The built-in template and packaging/jtask-gui.desktop must not drift
    (everything but the Exec line, which the installer fills in)."""
    pkg = Path(__file__).parents[2] / "packaging" / "jtask-gui.desktop"

    def _no_exec(text: str) -> list[str]:
        return [ln for ln in text.strip().splitlines() if not ln.startswith("Exec=")]

    embedded = desktop_install._DESKTOP_ENTRY.replace("{exec}", "x")
    assert _no_exec(embedded) == _no_exec(pkg.read_text(encoding="utf-8"))


def test_cli_flag_installs_without_starting_a_window(xdg, monkeypatch):
    from jtask_gui import app

    monkeypatch.setattr(
        app, "build_application",
        lambda *a, **k: pytest.fail("GUI must not start for --install-desktop"),
    )
    assert app.main(["--install-desktop"]) == 0
    assert desktop_install.installed()


@pytest.mark.skipif(
    not shutil.which("desktop-file-validate"), reason="desktop-file-utils absent"
)
def test_installed_entry_passes_desktop_file_validate(xdg):
    path = desktop_install.install()
    proc = subprocess.run(
        ["desktop-file-validate", str(path)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
