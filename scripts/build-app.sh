#!/usr/bin/env bash
# Build a self-contained application with PyInstaller.
#   macOS:  dist/Repo Numbat.app  (drag it into /Applications)   add --dmg for a disk image
#   Linux:  dist/Repo Numbat/repo-numbat
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"
# shellcheck source=env.sh
source "$PROJECT/scripts/env.sh"

if ! "$VENV_PY" -c 'import PyInstaller' 2>/dev/null; then
    echo "repo-numbat: installing PyInstaller into $VENV"
    if command -v uv >/dev/null 2>&1; then uv pip install --python "$VENV_PY" pyinstaller
    else "$VENV_PY" -m pip install pyinstaller; fi
fi

cd "$PROJECT"
rm -rf build dist
"$VENV_PY" -m PyInstaller --noconfirm --clean packaging/repo-numbat.spec

if [ "$(uname -s)" = "Darwin" ]; then
    APP="$PROJECT/dist/Repo Numbat.app"
    # ad-hoc signature so Gatekeeper lets a locally built bundle launch
    codesign --force --deep --sign - "$APP" 2>/dev/null || true
    echo "built: $APP"
    if [ "${1:-}" = "--dmg" ]; then
        DMG="$PROJECT/dist/Repo-Numbat.dmg"
        STAGE="$(mktemp -d)"
        cp -R "$APP" "$STAGE/"
        ln -s /Applications "$STAGE/Applications"
        hdiutil create -volname "Repo Numbat" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
        rm -rf "$STAGE"
        echo "built: $DMG"
    else
        echo "to install: open dist && drag 'Repo Numbat.app' into Applications"
    fi
else
    echo "built: $PROJECT/dist/Repo Numbat/repo-numbat"
fi
