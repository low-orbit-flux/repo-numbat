"""Dialog listing GitHub repositories that are not cloned under the repos folder."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from repo_numbat.github import GitHubError, GitHubRepo, find_token, guess_username, list_repos, match_local
from repo_numbat.gitscan import human_size
from repo_numbat.theme import C

HEADERS = ["Repository", "Visibility", "Local folder", "Last push", "Size", "Default branch", "Description"]


class _Signals(QObject):
    loaded = Signal(object, str, str)   # repos, login, auth source
    failed = Signal(str)
    cloned = Signal(str, str, bool)     # name, output, ok


class _ListTask(QRunnable):
    def __init__(self, signals, token, username, local, root):
        super().__init__()
        self.signals, self.token, self.username, self.local, self.root = signals, token, username, local, root

    def run(self):
        try:
            token, source = find_token(self.token)
            username = self.username or ("" if token else guess_username(list(self.local.values())))
            repos, login = list_repos(token, username)
            match_local(repos, self.local, self.root)
            self.signals.loaded.emit(repos, login, source)
        except GitHubError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class _CloneTask(QRunnable):
    def __init__(self, signals, name: str, url: str, dest: Path):
        super().__init__()
        self.signals, self.name, self.url, self.dest = signals, name, url, dest

    def run(self):
        kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" else {}
        try:
            proc = subprocess.run(["git", "clone", "--", self.url, str(self.dest)], capture_output=True, text=True,
                                  timeout=1800, check=False, env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"},
                                  **kwargs)
            out = (proc.stdout + proc.stderr).strip() or "done"
            self.signals.cloned.emit(self.name, out, proc.returncode == 0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.signals.cloned.emit(self.name, str(exc), False)


class _NumItem(QTableWidgetItem):
    """Shows text but sorts on a numeric value."""

    def __init__(self, text: str, value: int):
        super().__init__(text)
        self.value = value

    def __lt__(self, other):
        return self.value < getattr(other, "value", 0)


class GitHubDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.repos: list[GitHubRepo] = []
        self.setWindowTitle("GitHub repositories not on this machine")
        self.resize(1000, 560)
        self.signals = _Signals()
        self.signals.loaded.connect(self._loaded)
        self.signals.failed.connect(self._failed)
        self.signals.cloned.connect(self._cloned)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.status = QLabel("Contacting GitHub…")
        top.addWidget(self.status, 1)
        self.show_all = QCheckBox("Also show repos that are already cloned")
        self.show_all.toggled.connect(self._fill)
        top.addWidget(self.show_all)
        self.filter = QLineEdit(); self.filter.setPlaceholderText("Filter…"); self.filter.setFixedWidth(220)
        self.filter.textChanged.connect(self._fill)
        top.addWidget(self.filter)
        layout.addLayout(top)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(True)
        for i, w in enumerate((260, 80, 150, 90, 80, 110)):
            self.table.setColumnWidth(i, w)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _: self.open_browser())
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_clone = QPushButton("Clone selected"); self.btn_clone.clicked.connect(self.clone_selected)
        self.btn_copy = QPushButton("Copy clone URL"); self.btn_copy.clicked.connect(self.copy_url)
        self.btn_open = QPushButton("Open on GitHub"); self.btn_open.clicked.connect(self.open_browser)
        self.btn_reload = QPushButton("Reload"); self.btn_reload.clicked.connect(self.reload)
        close = QPushButton("Close"); close.clicked.connect(self.accept)
        for b in (self.btn_clone, self.btn_copy, self.btn_open, self.btn_reload):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._selection_changed()
        self.reload()

    # ------------------------------------------------------------ loading
    def reload(self):
        self.status.setText("Contacting GitHub…")
        self.btn_reload.setEnabled(False)
        local = {str(s.path): s.remote_url for s in self.main.statuses.values()}
        token = self.main.settings.value("github_token", "")
        username = self.main.settings.value("github_user", "")
        self.main.pool.start(_ListTask(self.signals, token, username, local, self.main.root))

    def _loaded(self, repos, login, source):
        self.repos = sorted(repos, key=lambda r: r.pushed_at, reverse=True)
        missing = sum(r.local_path is None for r in self.repos)
        note = "  (public repos only; add a token in Settings for private and organisation repos)" if source == "anonymous" else ""
        self.status.setText(f"{login} via {source}: {len(self.repos)} repos on GitHub, {missing} not cloned under {self.main.root}{note}")
        self.main.log(f"GitHub ({login}, {source}): {len(self.repos)} repos, {missing} not on this host", "GH")
        self.btn_reload.setEnabled(True)
        self._fill()

    def _failed(self, message):
        self.status.setText(message)
        self.main.log(message, "ERR")
        self.btn_reload.setEnabled(True)

    def _fill(self, *_):
        needle = self.filter.text().lower()
        rows = [r for r in self.repos if (self.show_all.isChecked() or r.local_path is None)
                and (not needle or needle in r.full_name.lower() or needle in r.description.lower())]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        ok, muted, warn = QColor(C["ok"]), QColor(C["muted"]), QColor(C["warn"])
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            vis = "private" if r.private else "public"
            if r.fork:
                vis += ", fork"
            if r.archived:
                vis += ", archived"
            size = _NumItem(human_size(r.size_kb * 1024), r.size_kb)
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            items = [QTableWidgetItem(r.full_name), QTableWidgetItem(vis),
                     QTableWidgetItem(r.local_path.name if r.local_path else "not cloned"),
                     QTableWidgetItem(r.pushed_at), size, QTableWidgetItem(r.default_branch),
                     QTableWidgetItem(r.description)]
            items[0].setData(Qt.ItemDataRole.UserRole, r)
            items[0].setToolTip(r.html_url)
            items[2].setForeground(ok if r.local_path else warn)
            items[2].setToolTip(str(r.local_path) if r.local_path else "")
            items[6].setForeground(muted)
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

    # ------------------------------------------------------------ actions
    def selected(self) -> list[GitHubRepo]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows]

    def _selection_changed(self):
        sel = self.selected()
        self.btn_clone.setEnabled(any(r.local_path is None for r in sel))
        self.btn_copy.setEnabled(len(sel) == 1)
        self.btn_open.setEnabled(len(sel) >= 1)

    def clone_selected(self):
        targets = [r for r in self.selected() if r.local_path is None]
        if not targets:
            return
        use_ssh = self.main.settings.value("github_ssh", True, type=bool)
        names = "\n".join(f"  {r.full_name}" for r in targets)
        if QMessageBox.question(self, "Clone", f"Clone into {self.main.root}:\n{names}") != QMessageBox.StandardButton.Yes:
            return
        for r in targets:
            dest = self.main.root / r.name
            if dest.exists():
                self.main.log(f"clone {r.full_name}: {dest} already exists", "ERR")
                continue
            url = r.ssh_url if use_ssh and r.ssh_url else r.clone_url
            self.main.log(f"git clone {url} {dest}", "GIT")
            self.main.pool.start(_CloneTask(self.signals, r.full_name, url, dest))

    def _cloned(self, name, output, ok):
        for line in output.splitlines():
            self.main.log(f"clone {name}: {line}", "GIT" if ok else "ERR")
        for r in self.repos:
            if r.full_name == name and ok:
                r.local_path = self.main.root / r.name
        self._fill()
        if ok:
            self.main.refresh()

    def copy_url(self):
        sel = self.selected()
        if len(sel) == 1:
            use_ssh = self.main.settings.value("github_ssh", True, type=bool)
            QGuiApplication.clipboard().setText(sel[0].ssh_url if use_ssh else sel[0].clone_url)

    def open_browser(self):
        for r in self.selected()[:5]:
            QDesktopServices.openUrl(QUrl(r.html_url))
