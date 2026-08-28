#!/usr/bin/env bash
# Build a standalone Linux binary (PyInstaller) and wrap it as an AppImage.
#
# Prereqs (host):  python3-venv, and appimagetool on PATH
#   wget -O ~/bin/appimagetool https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
#   chmod +x ~/bin/appimagetool
#
# Usage:  ./packaging/build-appimage.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=.venv-build
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -e ".[gui]" pyinstaller

"$VENV/bin/pyinstaller" --noconfirm --clean packaging/jtask-gui.spec

APPDIR=dist/jtask-gui.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r dist/jtask-gui/* "$APPDIR/usr/bin/"
cp packaging/jtask-gui.desktop "$APPDIR/usr/share/applications/"
cp packaging/jtask-gui.desktop "$APPDIR/"
cp src/jtask_gui/resources/icon-256.png \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/jtask-gui.png"
cp src/jtask_gui/resources/icon-256.png "$APPDIR/jtask-gui.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/jtask-gui" "$@"
EOF
chmod +x "$APPDIR/AppRun"

appimagetool "$APPDIR" "dist/jtask-gui-x86_64.AppImage"
echo "built: dist/jtask-gui-x86_64.AppImage"
