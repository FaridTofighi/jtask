#!/usr/bin/env bash
# Register jtask-gui with the local desktop (menu entry + icon), for a
# pip/pipx-installed copy. Run after `pip install jtask[gui]`.
set -euo pipefail
cd "$(dirname "$0")/.."

APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

mkdir -p "$APPS" "$ICONS/scalable/apps" "$ICONS/256x256/apps"
install -m644 packaging/jtask-gui.desktop "$APPS/jtask-gui.desktop"
install -m644 src/jtask_gui/resources/icon.svg "$ICONS/scalable/apps/jtask-gui.svg"
install -m644 src/jtask_gui/resources/icon-256.png "$ICONS/256x256/apps/jtask-gui.png"

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
echo "installed: $APPS/jtask-gui.desktop"
