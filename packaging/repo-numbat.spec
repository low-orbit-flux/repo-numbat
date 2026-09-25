# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: builds a self-contained app.
#   macOS   -> dist/Repo Numbat.app   (drag into /Applications)
#   Windows -> dist/Repo Numbat/Repo Numbat.exe
#   Linux   -> dist/Repo Numbat/repo-numbat
# Run through scripts/build-app.sh or scripts/build-app.bat.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ASSETS = ROOT / "repo_numbat" / "assets"
APP_NAME = "Repo Numbat"
EXE_NAME = "repo-numbat" if sys.platform != "win32" else APP_NAME
ICON = {"darwin": ASSETS / "numbat.icns", "win32": ASSETS / "numbat.ico"}.get(sys.platform, ASSETS / "numbat-256.png")

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    datas=[(str(ASSETS), "repo_numbat/assets")],
    hiddenimports=["PySide6.QtSvg"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtPdf", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=EXE_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ICON),
        bundle_identifier="net.low-orbit.repo-numbat",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "MIT License",
        },
    )
