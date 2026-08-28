# PyInstaller spec for jtask-gui.
# Build:  pyinstaller packaging/jtask-gui.spec  (from the repo root, in the venv)

from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files("jtask", includes=["themes_data/*"])
datas += collect_data_files("jtask_gui", includes=["resources/**/*"])

a = Analysis(
    ["../src/jtask_gui/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=["jtask_gui", "jtask"],
    hookspath=[],
    excludes=["tkinter", "PyQt6.QtWebEngineCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="jtask-gui",
    console=False,
    icon="../src/jtask_gui/resources/icon-256.png",
)
coll = COLLECT(exe, a.binaries, a.datas, name="jtask-gui")
