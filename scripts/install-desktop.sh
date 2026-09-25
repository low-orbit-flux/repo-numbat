#!/usr/bin/env bash
# Linux: install a launcher into the application menu (~/.local/share/applications)
# plus the numbat icon, so Repo Numbat shows up in GNOME/KDE/XFCE menus.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
mkdir -p "$APPS"
for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "$ICONS/${size}x${size}/apps"
    cp "$PROJECT/repo_numbat/assets/numbat-${size}.png" "$ICONS/${size}x${size}/apps/repo-numbat.png"
done
mkdir -p "$ICONS/scalable/apps"
cp "$PROJECT/repo_numbat/assets/numbat.svg" "$ICONS/scalable/apps/repo-numbat.svg"
cat > "$APPS/repo-numbat.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Repo Numbat
Comment=Status of every git repository under ~/repos
Exec=$PROJECT/scripts/repo-numbat
Icon=repo-numbat
Terminal=false
Categories=Development;RevisionControl;
Keywords=git;repository;status;
StartupWMClass=repo-numbat
DESKTOP
chmod +x "$PROJECT/scripts/repo-numbat"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q "$ICONS" 2>/dev/null || true
echo "installed $APPS/repo-numbat.desktop"
