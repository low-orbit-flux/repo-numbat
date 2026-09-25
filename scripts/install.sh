#!/usr/bin/env bash
# Install Repo Numbat on this machine (Linux or macOS).
#
#   ./scripts/install.sh              user install (no root needed)
#   ./scripts/install.sh --system     Linux: /opt/repo-numbat + /usr/local/bin (uses sudo)
#   ./scripts/install.sh --prefix DIR install the program files into DIR
#   ./scripts/install.sh --uninstall  remove everything this script installed
#
# Linux: copies the program to ~/.local/share/repo-numbat, creates its own
#        virtualenv there, links ~/.local/bin/repo-numbat, and installs the
#        application-menu entry plus icons (so the dock shows the numbat).
# macOS: builds "Repo Numbat.app" and copies it into /Applications (or
#        ~/Applications), and links ~/.local/bin/repo-numbat to the bundle.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/.." && pwd)"
OS="$(uname -s)"
SYSTEM=0
UNINSTALL=0
PREFIX=""

while [ $# -gt 0 ]; do
    case "$1" in
        --system) SYSTEM=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --prefix) PREFIX="$2"; shift ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$SYSTEM" = 1 ]; then
    PREFIX="${PREFIX:-/opt/repo-numbat}"
    BIN_DIR=/usr/local/bin
    APPS_DIR=/usr/share/applications
    ICON_DIR=/usr/share/icons/hicolor
    SUDO="sudo"
    [ "$(id -u)" = 0 ] && SUDO=""
else
    PREFIX="${PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/repo-numbat}"
    BIN_DIR="$HOME/.local/bin"
    APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
    SUDO=""
fi

refresh_menus() {
    if [ "$OS" != "Darwin" ]; then
        command -v update-desktop-database >/dev/null 2>&1 && $SUDO update-desktop-database "$APPS_DIR" 2>/dev/null || true
        command -v gtk-update-icon-cache >/dev/null 2>&1 && $SUDO gtk-update-icon-cache -q "$ICON_DIR" 2>/dev/null || true
    fi
}

# ----------------------------------------------------------------- uninstall
if [ "$UNINSTALL" = 1 ]; then
    echo "removing Repo Numbat"
    $SUDO rm -rf "$PREFIX"
    $SUDO rm -f "$BIN_DIR/repo-numbat"
    if [ "$OS" = "Darwin" ]; then
        rm -rf "/Applications/Repo Numbat.app" "$HOME/Applications/Repo Numbat.app"
    else
        $SUDO rm -f "$APPS_DIR/repo-numbat.desktop"
        for size in 16 24 32 48 64 128 256 512; do
            $SUDO rm -f "$ICON_DIR/${size}x${size}/apps/repo-numbat.png"
        done
        $SUDO rm -f "$ICON_DIR/scalable/apps/repo-numbat.svg"
        refresh_menus
    fi
    echo "done (settings in ~/.config/repo-numbat were kept)"
    exit 0
fi

# --------------------------------------------------------------------- macOS
if [ "$OS" = "Darwin" ]; then
    "$SRC/scripts/build-app.sh"
    DEST=/Applications
    [ -w "$DEST" ] || DEST="$HOME/Applications"
    mkdir -p "$DEST"
    rm -rf "$DEST/Repo Numbat.app"
    cp -R "$SRC/dist/Repo Numbat.app" "$DEST/"
    mkdir -p "$BIN_DIR"
    ln -sf "$DEST/Repo Numbat.app/Contents/MacOS/repo-numbat" "$BIN_DIR/repo-numbat"
    echo "installed $DEST/Repo Numbat.app (also: $BIN_DIR/repo-numbat)"
    exit 0
fi

# --------------------------------------------------------------------- Linux
echo "installing program files to $PREFIX"
$SUDO mkdir -p "$PREFIX"
copy_tree() {
    if command -v rsync >/dev/null 2>&1; then
        $SUDO rsync -a --delete --exclude .git --exclude .venv --exclude build --exclude dist \
            --exclude __pycache__ --exclude '*.pyc' "$SRC/" "$PREFIX/"
    else
        $SUDO find "$PREFIX" -mindepth 1 -maxdepth 1 ! -name .venv -exec rm -rf {} +
        for item in repo_numbat scripts tools packaging requirements.txt pyproject.toml README.md LICENSE; do
            [ -e "$SRC/$item" ] && $SUDO cp -R "$SRC/$item" "$PREFIX/"
        done
        $SUDO find "$PREFIX" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
    fi
}
copy_tree
if [ "$SYSTEM" = 1 ]; then
    $SUDO chown -R "$(id -u):$(id -g)" "$PREFIX"   # build the venv as the current user
fi

echo "creating the virtualenv"
# env.sh creates $PREFIX/.venv, installs requirements and the repo-numbat alias
( set +u; REPO_NUMBAT_VENV="$PREFIX/.venv" bash -c "source '$PREFIX/scripts/env.sh'" )
chmod +x "$PREFIX/scripts/"*.sh "$PREFIX/scripts/repo-numbat" "$PREFIX/scripts/repo-numbat.command" 2>/dev/null || true
if [ "$SYSTEM" = 1 ]; then
    $SUDO chown -R root:root "$PREFIX"
fi

echo "linking $BIN_DIR/repo-numbat"
$SUDO mkdir -p "$BIN_DIR"
$SUDO ln -sf "$PREFIX/scripts/repo-numbat" "$BIN_DIR/repo-numbat"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "note: $BIN_DIR is not on your PATH; add it to run 'repo-numbat' from a shell" ;;
esac

echo "installing menu entry and icons"
$SUDO mkdir -p "$APPS_DIR"
for size in 16 24 32 48 64 128 256 512; do
    $SUDO mkdir -p "$ICON_DIR/${size}x${size}/apps"
    $SUDO cp "$PREFIX/repo_numbat/assets/numbat-${size}.png" "$ICON_DIR/${size}x${size}/apps/repo-numbat.png"
done
$SUDO mkdir -p "$ICON_DIR/scalable/apps"
$SUDO cp "$PREFIX/repo_numbat/assets/numbat.svg" "$ICON_DIR/scalable/apps/repo-numbat.svg"
$SUDO tee "$APPS_DIR/repo-numbat.desktop" >/dev/null <<DESKTOP
[Desktop Entry]
Type=Application
Name=Repo Numbat
Comment=Status of every git repository under ~/repos
Exec=$PREFIX/scripts/repo-numbat
Icon=repo-numbat
Terminal=false
Categories=Development;RevisionControl;
Keywords=git;repository;status;
StartupWMClass=repo-numbat
DESKTOP
refresh_menus
echo "installed: $PREFIX"
echo "           $BIN_DIR/repo-numbat"
echo "           $APPS_DIR/repo-numbat.desktop"
