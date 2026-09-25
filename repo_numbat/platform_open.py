"""Open a folder in the file manager or a terminal, on Linux, macOS and Windows."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

LINUX_TERMINALS = (
    ("x-terminal-emulator", []), ("gnome-terminal", ["--working-directory={path}"]),
    ("konsole", ["--workdir", "{path}"]), ("xfce4-terminal", ["--working-directory={path}"]),
    ("kgx", ["--working-directory={path}"]), ("ptyxis", ["--working-directory={path}"]),
    ("tilix", ["--working-directory={path}"]), ("alacritty", ["--working-directory", "{path}"]),
    ("kitty", ["--directory", "{path}"]), ("foot", ["--working-directory={path}"]),
    ("wezterm", ["start", "--cwd", "{path}"]), ("terminator", ["--working-directory={path}"]),
    ("xterm", []),
)


def open_folder(path: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_terminal(path: Path) -> str:
    """Launch a terminal in *path*. Returns '' on success or an error message."""
    try:
        if sys.platform == "win32":
            if shutil.which("wt"):
                subprocess.Popen(["wt", "-d", str(path)])
            else:
                subprocess.Popen(f'start "Repo Numbat" cmd /K cd /d "{path}"', shell=True)
            return ""
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", str(path)])
            return ""
        preferred = os.environ.get("TERMINAL")
        candidates = ([(preferred, ["{path}"] if preferred not in ("xterm", "x-terminal-emulator") else [])]
                      if preferred else []) + list(LINUX_TERMINALS)
        for exe, args in candidates:
            if shutil.which(exe):
                argv = [exe] + [a.format(path=path) for a in args]
                subprocess.Popen(argv, cwd=str(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return ""
        return "no terminal emulator found (set $TERMINAL)"
    except OSError as exc:
        return str(exc)
