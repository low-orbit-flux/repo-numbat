"""The Repo Numbat main window."""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import (QObject, QRunnable, QSettings, QSize, QSortFilterProxyModel, Qt, QThreadPool, QTimer,
                            Signal, Slot)
from PySide6.QtGui import QAction, QActionGroup, QColor, QGuiApplication, QKeySequence, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QSpinBox, QSplitter, QStyledItemDelegate, QTableView, QTabWidget,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

from repo_numbat import APP_NAME, __version__
from repo_numbat.create_remote_dialog import CreateRemoteDialog
from repo_numbat.github import GitHubError, find_token, remote_key, visibility_map
from repo_numbat.github_dialog import GitHubDialog
from repo_numbat.gitscan import RepoStatus, _git, find_repos, human_size, scan_repo
from repo_numbat.icons import app_icon, dot, toolbar_icon
from repo_numbat.platform_open import open_folder, open_terminal
from repo_numbat.theme import C, apply_theme

# ------------------------------------------------------------------ columns
@dataclass(frozen=True)
class Col:
    title: str
    width: int
    tip: str = ""

COLS = [
    Col("", 26, "Overall state: green = clean, amber = needs attention, red = conflicts/diverged, grey = no remote"),
    Col("Repo", 190),
    Col("Branch", 120),
    Col("Status", 170, "Uncommitted = files not added/committed, Unpushed = commits not on the remote, Unpulled = remote commits not merged"),
    Col("Untracked", 78, "Files not yet added to git"),
    Col("Modified", 72, "Tracked files changed but not staged"),
    Col("Staged", 62, "Changes added to the index but not committed"),
    Col("To push", 66, "Local commits missing from the remote"),
    Col("To pull", 66, "Remote commits missing locally (run Fetch for an up-to-date count)"),
    Col("Remote", 120, "Whether a git remote is configured"),
    Col("Visibility", 84, "public / private / unknown, asked from GitHub after each scan (Settings > GitHub)"),
    Col("Remote owner", 190, "User or group/organisation that owns the remote repository"),
    Col("Owner", 130, "Who owns the directory on this machine"),
    Col("Stashes", 62),
    Col("Dir size", 84, "Disk space used by the whole folder, including untracked and ignored files"),
    Col("Repo size", 84, "Disk space used by what git manages: tracked files plus .git (untracked build/data folders excluded)"),
    Col("Last commit", 120),
    Col("Remote URL", 280),
    Col("Path", 300),
]
(C_DOT, C_REPO, C_BRANCH, C_STATUS, C_UNTRACKED, C_MODIFIED, C_STAGED, C_AHEAD, C_BEHIND, C_REMOTE,
 C_VIS, C_ROWNER, C_OWNER, C_STASH, C_SIZE, C_REPOSIZE, C_LAST, C_URL, C_PATH) = range(len(COLS))
NUMERIC = {C_UNTRACKED, C_MODIFIED, C_STAGED, C_AHEAD, C_BEHIND, C_STASH}
ROLE_STATUS = Qt.ItemDataRole.UserRole + 1
ROLE_SORT = Qt.ItemDataRole.UserRole + 2   # QStandardItem shares Display/Edit, so numbers sort via this role
SEVERITY_RANK = {"bad": 0, "warn": 1, "ok": 2, "none": 3}


def remote_owner(url: str) -> str:
    """'git@github.com:acme/widget.git' -> 'acme @ github.com'."""
    if not url:
        return ""
    host, path = "", ""
    if "://" in url:
        u = urlparse(url)
        host, path = u.hostname or "", u.path
    elif ":" in url and "@" in url.split(":", 1)[0]:
        hostpart, path = url.split(":", 1)
        host = hostpart.split("@", 1)[1]
    else:
        return "local path"
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 2:
        return host
    owner = "/".join(parts[:-1])
    return f"{owner} @ {host}" if host else owner


class ElideLeftDelegate(QStyledItemDelegate):
    """Keep the end of long values (the repo name in a path or URL) visible when the column is narrow."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideLeft


# ----------------------------------------------------------------- workers
class ScanSignals(QObject):
    result = Signal(int, object)      # generation, RepoStatus
    detail = Signal(str, str)         # repo path, text
    command = Signal(str, str, bool)  # repo name, output, ok
    visibility = Signal(int, object, str)  # generation, {key: visibility}, error
    log = Signal(str)


class ScanTask(QRunnable):
    def __init__(self, signals: ScanSignals, generation: int, path: Path, fetch: bool):
        super().__init__()
        self.signals, self.generation, self.path, self.fetch = signals, generation, path, fetch
        self.setAutoDelete(True)

    def run(self) -> None:
        self.signals.result.emit(self.generation, scan_repo(self.path, fetch=self.fetch))


class DetailTask(QRunnable):
    def __init__(self, signals: ScanSignals, path: Path):
        super().__init__()
        self.signals, self.path = signals, path

    def run(self) -> None:
        try:
            branch = _git(self.path, "status", "--short", "--branch").stdout
            log = _git(self.path, "log", "--oneline", "-8", "--decorate").stdout
            remotes = _git(self.path, "remote", "-v").stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.signals.detail.emit(str(self.path), f"error: {exc}")
            return
        text = f"$ git status --short --branch\n{branch}\n$ git log --oneline -8\n{log or '(no commits)\n'}\n$ git remote -v\n{remotes or '(no remotes)\n'}"
        self.signals.detail.emit(str(self.path), text)


class VisibilityTask(QRunnable):
    def __init__(self, signals: ScanSignals, generation: int, keys: list[str], saved_token: str, username: str):
        super().__init__()
        self.signals, self.generation, self.keys = signals, generation, keys
        self.saved_token, self.username = saved_token, username

    def run(self) -> None:
        try:
            token, _ = find_token(self.saved_token)
            result = visibility_map(token, self.keys, self.username)
            self.signals.visibility.emit(self.generation, result, "")
        except GitHubError as exc:
            self.signals.visibility.emit(self.generation, {}, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.signals.visibility.emit(self.generation, {}, f"{type(exc).__name__}: {exc}")


class GitCommandTask(QRunnable):
    def __init__(self, signals: ScanSignals, name: str, path: Path, args: list[str]):
        super().__init__()
        self.signals, self.name, self.path, self.args = signals, name, path, args

    def run(self) -> None:
        try:
            proc = _git(self.path, *self.args, timeout=300)
            out = (proc.stdout + proc.stderr).strip()
            self.signals.command.emit(self.name, out or f"git {' '.join(self.args)}: done", proc.returncode == 0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.signals.command.emit(self.name, str(exc), False)


# ------------------------------------------------------------------ model
class RepoFilter(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.show_non_git = True
        self.only_attention = False
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)
        self.setSortRole(ROLE_SORT)

    def filterAcceptsRow(self, row, parent):
        item = self.sourceModel().item(row, C_DOT)
        st: RepoStatus | None = item.data(ROLE_STATUS) if item else None
        if st is not None:
            if not self.show_non_git and not st.is_git:
                return False
            if self.only_attention and (st.is_clean or not st.is_git):
                return False
        return super().filterAcceptsRow(row, parent)


class SettingsDialog(QDialog):
    def __init__(self, parent, settings: QSettings):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings
        form = QFormLayout(self)
        self.root = QLineEdit(settings.value("root", str(Path.home() / "repos")))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout(); row.addWidget(self.root); row.addWidget(browse)
        form.addRow("Repos folder", row)
        self.fetch = QCheckBox("Run 'git fetch' on every refresh (slower, needs network)")
        self.fetch.setChecked(settings.value("fetch", False, type=bool))
        form.addRow("", self.fetch)
        self.interval = QSpinBox(); self.interval.setRange(0, 720); self.interval.setSuffix(" min")
        self.interval.setSpecialValueText("off")
        self.interval.setValue(settings.value("interval", 0, type=int))
        form.addRow("Auto-refresh", self.interval)
        self.threads = QSpinBox(); self.threads.setRange(1, 32)
        self.threads.setValue(settings.value("threads", 8, type=int))
        form.addRow("Parallel scans", self.threads)
        form.addRow(QLabel("<b>GitHub</b> (used by the GitHub button)"))
        self.gh_user = QLineEdit(settings.value("github_user", ""))
        self.gh_user.setPlaceholderText("only needed without a token; guessed from your remotes if empty")
        form.addRow("GitHub username", self.gh_user)
        self.gh_token = QLineEdit(settings.value("github_token", ""))
        self.gh_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.gh_token.setPlaceholderText("optional; else $GITHUB_TOKEN, $GH_TOKEN or 'gh auth token' is used")
        form.addRow("GitHub token", self.gh_token)
        self.gh_vis = QCheckBox("Ask GitHub whether each repo is public or private after every scan")
        self.gh_vis.setChecked(settings.value("github_visibility", True, type=bool))
        form.addRow("", self.gh_vis)
        self.gh_ssh = QCheckBox("Clone with SSH URLs (git@github.com:…) instead of HTTPS")
        self.gh_ssh.setChecked(settings.value("github_ssh", True, type=bool))
        form.addRow("", self.gh_ssh)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose the folder that contains your repos", self.root.text())
        if d:
            self.root.setText(d)

    def accept(self):
        self.settings.setValue("root", self.root.text().strip() or str(Path.home() / "repos"))
        self.settings.setValue("fetch", self.fetch.isChecked())
        self.settings.setValue("interval", self.interval.value())
        self.settings.setValue("threads", self.threads.value())
        self.settings.setValue("github_user", self.gh_user.text().strip())
        self.settings.setValue("github_token", self.gh_token.text().strip())
        self.settings.setValue("github_ssh", self.gh_ssh.isChecked())
        self.settings.setValue("github_visibility", self.gh_vis.isChecked())
        super().accept()


# ------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self, root: Path | None = None, fetch: bool | None = None):
        super().__init__()
        self.settings = QSettings("repo-numbat", "repo-numbat")
        if root is not None:
            self.settings.setValue("root", str(root))
        if fetch:
            self.settings.setValue("fetch", True)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1400, 800)

        self.signals = ScanSignals()
        self.signals.result.connect(self._on_result)
        self.signals.detail.connect(self._on_detail)
        self.signals.command.connect(self._on_command)
        self.signals.visibility.connect(self._on_visibility)
        self.signals.log.connect(self.log)
        self.visibility_cache: dict[str, str] = {}
        self.pool = QThreadPool(self)
        self.generation = 0
        self.pending = 0
        self.statuses: dict[str, RepoStatus] = {}

        self._build_model()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._restore_state()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._apply_timer()
        self.log(f"{APP_NAME} {__version__} | Python {sys.version.split()[0]} | {sys.platform}")
        QTimer.singleShot(0, self.refresh)

    # ------------------------------------------------------------ building
    @property
    def root(self) -> Path:
        return Path(self.settings.value("root", str(Path.home() / "repos"))).expanduser()

    def _build_model(self):
        self.model = QStandardItemModel(0, len(COLS), self)
        for i, col in enumerate(COLS):
            self.model.setHeaderData(i, Qt.Orientation.Horizontal, col.title)
            if col.tip:
                self.model.setHeaderData(i, Qt.Orientation.Horizontal, col.tip, Qt.ItemDataRole.ToolTipRole)
        self.proxy = RepoFilter()
        self.proxy.setSourceModel(self.model)

    def _build_actions(self):
        def act(text, icon, slot, shortcut=None, tip=""):
            a = QAction(toolbar_icon(icon), text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(tip or text)
            a.setStatusTip(tip or text)
            return a
        self.act_refresh = act("Refresh", "refresh", self.refresh, "F5", "Re-scan every repo (local status only)")
        self.act_fetch = act("Fetch", "fetch", self.refresh_with_fetch, "Ctrl+F5", "git fetch every remote, then re-scan")
        self.act_stop = act("Stop", "stop", self.stop_scan, tip="Abandon the running scan")
        self.act_stop.setEnabled(False)
        self.act_open = act("Open", "folder", self.open_selected_folder, "Ctrl+O", "Open the selected repo in the file manager")
        self.act_term = act("Terminal", "terminal", self.open_selected_terminal, "Ctrl+T", "Open a terminal in the selected repo")
        self.act_copy = act("Copy path", "copy", self.copy_selected_path, "Ctrl+C")
        self.act_pull = act("Pull", "pull", self.pull_selected, tip="git pull --ff-only in the selected repo")
        self.act_push = act("Push", "push", self.push_selected, tip="git push in the selected repo")
        self.act_rescan_one = act("Rescan this repo", "refresh", self.rescan_selected)
        self.act_create_remote = act("Create remote", "remote", self.create_remote_selected, "Ctrl+N",
                                     "Create a GitHub repository for the selected repo (it has no remote) and connect it")
        self.act_github = act("GitHub", "github", self.show_github, "Ctrl+G",
                              "List your GitHub repositories that are not cloned into the repos folder")
        self.act_settings = act("Settings…", "settings", self.show_settings, "Ctrl+,")
        self.act_quit = QAction("Quit", self); self.act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_quit.triggered.connect(self.close)
        self.act_show_nongit = QAction("Show folders that are not git repos", self, checkable=True)
        self.act_show_nongit.setChecked(self.settings.value("show_non_git", True, type=bool))
        self.act_show_nongit.toggled.connect(self._apply_filters)
        self.act_only_attention = QAction("Only repos that need attention", self, checkable=True)
        self.act_only_attention.setChecked(self.settings.value("only_attention", False, type=bool))
        self.act_only_attention.toggled.connect(self._apply_filters)
        self.act_clear_log = act("Clear log", "clear", lambda: self.log_view.clear())
        self.act_about = QAction("About Repo Numbat", self); self.act_about.triggered.connect(self.about)

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        m.addActions([self.act_refresh, self.act_fetch, self.act_stop]); m.addSeparator()
        m.addAction(self.act_settings); m.addSeparator(); m.addAction(self.act_quit)
        m = mb.addMenu("&Repo")
        m.addActions([self.act_open, self.act_term, self.act_copy, self.act_rescan_one]); m.addSeparator()
        m.addActions([self.act_pull, self.act_push, self.act_create_remote]); m.addSeparator()
        m.addAction(self.act_github)
        m = mb.addMenu("&View")
        m.addActions([self.act_show_nongit, self.act_only_attention]); m.addSeparator()
        self.columns_menu = m.addMenu("Columns")
        m.addAction(self.act_clear_log)
        mb.addMenu("&Help").addAction(self.act_about)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(28, 28))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(tb)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(44, 44)))
        logo.setToolTip(f"{APP_NAME} {__version__}")
        logo.setContentsMargins(4, 0, 6, 0)
        tb.addWidget(logo)
        tb.addSeparator()
        for a in (self.act_open, self.act_refresh, self.act_fetch, self.act_stop):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.act_term, self.act_copy, self.act_pull, self.act_push, self.act_create_remote):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_github)
        tb.addAction(self.act_settings)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.root_label = QLabel()
        self.root_label.setStyleSheet(f"color: {C['muted']}; padding-right: 12px;")
        tb.addWidget(self.root_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        tb.addWidget(self.search)
        self.toolbar = tb

    def _build_central(self):
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(lambda _: self.open_selected_folder())
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setSectionsMovable(True)
        hh.setHighlightSections(False)
        for i, col in enumerate(COLS):
            self.table.setColumnWidth(i, col.width)
        hh.setSectionResizeMode(C_DOT, QHeaderView.ResizeMode.Fixed)
        self.elide_left = ElideLeftDelegate(self.table)
        for col in (C_PATH, C_URL):
            self.table.setItemDelegateForColumn(col, self.elide_left)
        self.table.sortByColumn(C_REPO, Qt.SortOrder.AscendingOrder)

        for i, col in enumerate(COLS):
            if i == C_DOT:
                continue
            a = QAction(col.title, self, checkable=True, checked=True)
            a.toggled.connect(lambda on, i=i: self.table.setColumnHidden(i, not on))
            self.columns_menu.addAction(a)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.log_view = QPlainTextEdit(); self.log_view.setReadOnly(True); self.log_view.setMaximumBlockCount(5000)
        self.detail_view = QPlainTextEdit(); self.detail_view.setReadOnly(True)
        mono = self.log_view.font(); mono.setFamily("monospace"); mono.setStyleHint(mono.StyleHint.Monospace)
        self.log_view.setFont(mono); self.detail_view.setFont(mono)
        self.tabs.addTab(self.log_view, "Log")
        self.tabs.addTab(self.detail_view, "Details")

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([600, 180])
        self.setCentralWidget(self.splitter)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.summary_label = QLabel("")
        sb.addWidget(self.summary_label, 1)
        self.progress = QProgressBar(); self.progress.setFixedWidth(220); self.progress.hide()
        sb.addPermanentWidget(self.progress)

    def _restore_state(self):
        if (g := self.settings.value("geometry")) is not None:
            self.restoreGeometry(g)
        if (s := self.settings.value("splitter")) is not None:
            self.splitter.restoreState(s)
        if (h := self.settings.value("header")) is not None:
            self.table.horizontalHeader().restoreState(h)
            for i, a in enumerate(self.columns_menu.actions(), start=1):
                a.setChecked(not self.table.isColumnHidden(i))
        self._apply_filters()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("header", self.table.horizontalHeader().saveState())
        self.settings.setValue("show_non_git", self.act_show_nongit.isChecked())
        self.settings.setValue("only_attention", self.act_only_attention.isChecked())
        self.generation += 1
        self.pool.clear()
        super().closeEvent(event)

    # ------------------------------------------------------------ scanning
    def log(self, message: str, kind: str = "SYS"):
        stamp = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"- {kind}: {stamp} {message}")

    def _apply_timer(self):
        minutes = self.settings.value("interval", 0, type=int)
        self.timer.stop()
        if minutes > 0:
            self.timer.start(minutes * 60_000)

    def _apply_filters(self):
        self.proxy.show_non_git = self.act_show_nongit.isChecked()
        self.proxy.only_attention = self.act_only_attention.isChecked()
        self.proxy.invalidateFilter()
        self._update_summary()

    def refresh_with_fetch(self):
        self.visibility_cache.clear()
        self.refresh(fetch=True)

    def refresh(self, checked: bool = False, fetch: bool | None = None):
        if fetch is None:
            fetch = self.settings.value("fetch", False, type=bool)
        self.generation += 1
        self.pool.clear()
        self.pool.setMaxThreadCount(self.settings.value("threads", 8, type=int))
        root = self.root
        self.root_label.setText(str(root))
        self.model.removeRows(0, self.model.rowCount())
        self.statuses.clear()
        self.detail_view.clear()
        dirs = find_repos(root)
        if not root.is_dir():
            self.log(f"repos folder not found: {root} (change it in Settings)", "ERR")
        self.log(f"scanning {len(dirs)} folders in {root}{' with fetch' if fetch else ''}", "SCAN")
        self.pending = len(dirs)
        self.progress.setRange(0, max(len(dirs), 1)); self.progress.setValue(0); self.progress.show()
        self.act_stop.setEnabled(True)
        self.summary_label.setText("Scanning…")
        for d in dirs:
            self.pool.start(ScanTask(self.signals, self.generation, d, fetch))
        if not dirs:
            self._scan_done()

    def stop_scan(self):
        self.generation += 1
        self.pool.clear()
        self.log("scan stopped", "SCAN")
        self._scan_done()

    def rescan_selected(self):
        if st := self.selected_status():
            self.log(f"rescanning {st.name}", "SCAN")
            self.rescan_path(st.path)

    def rescan_path(self, path: Path):
        self.pool.start(ScanTask(self.signals, self.generation, path, self.settings.value("fetch", False, type=bool)))

    @Slot(int, object)
    def _on_result(self, generation: int, st: RepoStatus):
        if generation != self.generation:
            return
        is_new = str(st.path) not in self.statuses
        self.statuses[str(st.path)] = st
        row = self._find_row(st.path)
        if row is None:
            row = self.model.rowCount()
            self.model.insertRow(row, [QStandardItem() for _ in COLS])
        self._fill_row(row, st)
        if st.error:
            self.log(f"{st.name}: {st.error}", "ERR")
        if is_new:
            self.pending -= 1
            self.progress.setValue(self.progress.maximum() - self.pending)
            if self.pending <= 0:
                self._scan_done()
        else:
            self._update_summary()
            self._selection_changed()

    def _scan_done(self):
        self.progress.hide()
        self.act_stop.setEnabled(False)
        self._update_summary()
        if self.statuses:
            self.log(self.summary_label.text(), "SCAN")
            self._start_visibility()

    def _find_row(self, path: Path) -> int | None:
        for r in range(self.model.rowCount()):
            if self.model.item(r, C_DOT).data(ROLE_STATUS).path == path:
                return r
        return None

    def _fill_row(self, row: int, st: RepoStatus):
        muted, warn, ok, bad = (QColor(C[k]) for k in ("muted", "warn", "ok", "bad"))

        def put(col: int, value, color: QColor | None = None, tip: str = ""):
            item = self.model.item(row, col)
            item.setData(value, Qt.ItemDataRole.DisplayRole)
            item.setData(value if isinstance(value, int) else str(value).lower(), ROLE_SORT)
            item.setForeground(color or QColor(C["text"]))
            item.setToolTip(tip)
            if col in NUMERIC:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        first = self.model.item(row, C_DOT)
        first.setData(st, ROLE_STATUS)
        first.setIcon(dot(st.severity))
        first.setData("", Qt.ItemDataRole.DisplayRole)
        first.setData(SEVERITY_RANK[st.severity], ROLE_SORT)
        first.setToolTip(st.summary)
        put(C_REPO, st.name, None if st.is_git else muted, str(st.path))
        put(C_BRANCH, st.branch, None if st.branch and not st.branch.startswith("(") else muted,
            f"HEAD {st.head}" if st.head else "")
        sev_color = {"ok": ok, "warn": warn, "bad": bad, "none": muted}[st.severity]
        put(C_STATUS, st.summary, sev_color, st.error)
        for col, n in ((C_UNTRACKED, st.untracked), (C_MODIFIED, st.unstaged), (C_STAGED, st.staged),
                       (C_AHEAD, st.ahead), (C_BEHIND, st.behind), (C_STASH, st.stashes)):
            if not st.is_git:
                put(col, "", muted)
                self.model.item(row, col).setData(-1, ROLE_SORT)
            else:
                put(col, n, warn if n else muted)
        if st.is_git and st.has_remote and not st.upstream and st.head:
            put(C_AHEAD, "no upstream", warn, "The branch has no upstream branch, so nothing has been pushed")
            self.model.item(row, C_AHEAD).setData(10**9, ROLE_SORT)
        if st.is_git and st.has_remote and not st.fetched:
            self.model.item(row, C_BEHIND).setToolTip("Based on the last fetch; press Fetch for a live count")
        if not st.is_git:
            put(C_REMOTE, "", muted)
        elif st.has_remote:
            put(C_REMOTE, "connected", ok, f"{st.remote_name}: {st.remote_url}")
        else:
            put(C_REMOTE, "not connected", muted)
        self._fill_visibility(row, st)
        put(C_ROWNER, remote_owner(st.remote_url) if st.is_git else "", None, st.remote_url)
        own = st.ownership
        put(C_OWNER, st.owner_text, ok if (own.is_mine or own.in_my_group) else warn,
            f"owner {own.owner}" + (f", group {own.group}" if own.group else "") + (f" ({own.error})" if own.error else ""))
        put(C_LAST, st.last_commit if st.is_git else "", muted if not st.last_commit else None)
        def put_size(col: int, n: int, tip: str, show: bool = True):
            item = self.model.item(row, col)
            item.setData(human_size(n) if show else "", Qt.ItemDataRole.DisplayRole)
            item.setData(n if show else -1, ROLE_SORT)
            item.setForeground(QColor(C["text"]))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(tip if show else "")
        put_size(C_SIZE, st.size_bytes, f"{st.size_bytes:,} bytes")
        extra = st.size_bytes - st.repo_bytes
        put_size(C_REPOSIZE, st.repo_bytes,
                 f"tracked files {human_size(st.repo_bytes - st.git_bytes)} + .git {human_size(st.git_bytes)}"
                 + (f"; {human_size(extra)} of untracked/ignored files not counted" if extra > 0 else ""),
                 show=st.is_git)
        put(C_URL, st.remote_url, muted if not st.remote_url else None)
        put(C_PATH, str(st.path), muted)

    def _fill_visibility(self, row: int, st: RepoStatus):
        item = self.model.item(row, C_VIS)
        key = remote_key(st.remote_url) if st.is_git else None
        if key and not st.visibility:
            st.visibility = self.visibility_cache.get(key, "")
        colors = {"public": QColor(C["warn"]), "private": QColor(C["ok"]), "unknown": QColor(C["muted"])}
        if not st.is_git:
            text, color, tip = "", QColor(C["muted"]), ""
        elif not st.has_remote:
            text, color, tip = "local", QColor(C["muted"]), "No remote, so the repo exists only on this machine"
        elif key is None:
            text, color, tip = "unknown", QColor(C["muted"]), "Not a GitHub remote; visibility is only looked up on GitHub"
        elif st.visibility:
            text, color = st.visibility, colors[st.visibility]
            tip = "GitHub could not show this repo: private and not visible with the current auth, or removed" if st.visibility == "unknown" else f"{st.visibility} on GitHub"
        else:
            text, color, tip = "…", QColor(C["muted"]), "Waiting for GitHub"
        item.setData(text, Qt.ItemDataRole.DisplayRole)
        item.setData(text, ROLE_SORT)
        item.setForeground(color)
        item.setToolTip(tip)

    def _start_visibility(self):
        if not self.settings.value("github_visibility", True, type=bool):
            return
        keys = sorted({k for k in (remote_key(s.remote_url) for s in self.statuses.values() if s.is_git) if k}
                      - set(self.visibility_cache))
        if not keys:
            return
        self.log(f"asking GitHub about {len(keys)} repos' visibility", "GH")
        self.pool.start(VisibilityTask(self.signals, self.generation, keys,
                                       self.settings.value("github_token", ""), self.settings.value("github_user", "")))

    @Slot(int, object, str)
    def _on_visibility(self, generation: int, result: dict, error: str):
        if error:
            self.log(f"visibility lookup failed: {error}", "ERR")
        if generation != self.generation:
            return
        self.visibility_cache.update(result)
        for r in range(self.model.rowCount()):
            st: RepoStatus = self.model.item(r, C_DOT).data(ROLE_STATUS)
            key = remote_key(st.remote_url) if st.is_git else None
            if key in result:
                st.visibility = result[key]
                self._fill_visibility(r, st)
            elif key and error and not st.visibility:
                st.visibility = "unknown"
                self._fill_visibility(r, st)

    def note_visibility(self, path: Path, visibility: str):
        """Called after Create remote so the new repo shows its visibility without another lookup."""
        st = self.statuses.get(str(path))
        if st and (key := remote_key(st.remote_url)):
            self.visibility_cache[key] = visibility
        # the rescan started by the dialog will pick it up from the cache; for the current row as well:
        row = self._find_row(path)
        if row is not None and st:
            st.visibility = visibility
            self._fill_visibility(row, st)

    def _update_summary(self):
        sts = [s for s in self.statuses.values() if s.is_git]
        if not sts:
            self.summary_label.setText("No git repositories found" if self.statuses else "")
            return
        n = len(sts)
        parts = [f"{n} repos", f"{sum(s.is_clean for s in sts)} clean",
                 f"{sum(s.has_uncommitted for s in sts)} uncommitted", f"{sum(s.has_unpushed for s in sts)} unpushed",
                 f"{sum(s.has_unpulled for s in sts)} unpulled", f"{sum(not s.has_remote for s in sts)} without remote"]
        shown = self.proxy.rowCount()
        if shown != self.model.rowCount():
            parts.append(f"showing {shown} of {self.model.rowCount()}")
        self.summary_label.setText(" | ".join(parts))

    # --------------------------------------------------------- selection
    def selected_status(self) -> RepoStatus | None:
        idx = self.table.selectionModel().currentIndex()
        if not idx.isValid():
            return None
        src = self.proxy.mapToSource(idx)
        return self.model.item(src.row(), C_DOT).data(ROLE_STATUS)

    def _selection_changed(self, *_):
        st = self.selected_status()
        enabled = st is not None
        for a in (self.act_open, self.act_term, self.act_copy):
            a.setEnabled(enabled)
        for a in (self.act_rescan_one, self.act_pull, self.act_push):
            a.setEnabled(enabled and st.is_git)
        has_remote = bool(st and st.is_git and st.has_remote)
        self.act_pull.setEnabled(has_remote); self.act_push.setEnabled(has_remote)
        self.act_create_remote.setEnabled(bool(st and st.is_git and not st.has_remote))
        if st is None:
            self.detail_view.clear()
            return
        header = (f"{st.name}  [{st.path}]\n"
                  f"owner: {st.owner_text} | remote: {st.remote_url or 'none'} | upstream: {st.upstream or 'none'}\n\n")
        if st.is_git:
            self.detail_view.setPlainText(header + "loading…")
            self.pool.start(DetailTask(self.signals, st.path))
        else:
            self.detail_view.setPlainText(header + "Not a git repository.")

    @Slot(str, str)
    def _on_detail(self, path: str, text: str):
        st = self.selected_status()
        if st and str(st.path) == path:
            head = self.detail_view.toPlainText().split("\n\n", 1)[0]
            self.detail_view.setPlainText(head + "\n\n" + text)

    def _context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if idx.isValid():
            self.table.selectRow(idx.row())
        menu = QMenu(self)
        menu.addActions([self.act_open, self.act_term, self.act_copy, self.act_rescan_one])
        menu.addSeparator()
        menu.addActions([self.act_pull, self.act_push, self.act_create_remote])
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------ actions
    def open_selected_folder(self):
        if st := self.selected_status():
            if not open_folder(st.path):
                self.log(f"could not open {st.path}", "ERR")

    def open_selected_terminal(self):
        if st := self.selected_status():
            err = open_terminal(st.path)
            self.log(f"terminal in {st.name}" + (f" failed: {err}" if err else ""), "ERR" if err else "SYS")

    def copy_selected_path(self):
        if st := self.selected_status():
            QGuiApplication.clipboard().setText(str(st.path))
            self.log(f"copied {st.path}")

    def _confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def pull_selected(self):
        st = self.selected_status()
        if st and self._confirm("Pull", f"Run 'git pull --ff-only' in {st.name}?"):
            self.log(f"{st.name}: git pull --ff-only", "GIT")
            self.pool.start(GitCommandTask(self.signals, st.name, st.path, ["pull", "--ff-only"]))

    def push_selected(self):
        st = self.selected_status()
        if not st:
            return
        args = ["push"]
        if not st.upstream:
            args = ["push", "--set-upstream", st.remote_name or "origin", st.branch]
        if self._confirm("Push", f"Run 'git {' '.join(args)}' in {st.name}?"):
            self.log(f"{st.name}: git {' '.join(args)}", "GIT")
            self.pool.start(GitCommandTask(self.signals, st.name, st.path, args))

    @Slot(str, str, bool)
    def _on_command(self, name: str, output: str, ok: bool):
        for line in output.splitlines():
            self.log(f"{name}: {line}", "GIT" if ok else "ERR")
        path = next((s.path for s in self.statuses.values() if s.name == name), None)
        if path:
            self.pool.start(ScanTask(self.signals, self.generation, path, False))

    def show_settings(self):
        old_root = self.root
        if SettingsDialog(self, self.settings).exec() == QDialog.DialogCode.Accepted:
            self._apply_timer()
            if self.root != old_root:
                self.log(f"repos folder changed to {self.root}")
            self.refresh()

    def create_remote_selected(self):
        st = self.selected_status()
        if st and st.is_git and not st.has_remote:
            CreateRemoteDialog(self, st).exec()

    def show_github(self):
        GitHubDialog(self).exec()

    def about(self):
        QMessageBox.about(self, "About Repo Numbat",
                          f"<b>{APP_NAME} {__version__}</b><br>"
                          "A dashboard for the git repositories in your <code>repos</code> folder.<br><br>"
                          "Green: clean and in sync. Amber: something to add, commit, push or pull. "
                          "Red: conflicts or a diverged branch. Grey: no remote configured.<br><br>"
                          "The numbat (<i>Myrmecobius fasciatus</i>) is a striped termite-eating marsupial from Western Australia.")


def run_gui(root: Path | None = None, fetch: bool = False) -> int:
    QApplication.setApplicationName("repo-numbat")
    QApplication.setApplicationDisplayName(APP_NAME)
    QApplication.setOrganizationName("repo-numbat")
    # Wayland/GNOME match the window to repo-numbat.desktop through this app id
    QGuiApplication.setDesktopFileName("repo-numbat")
    if sys.platform == "win32":  # taskbar icon grouping
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("repo-numbat")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    apply_theme(app)
    win = MainWindow(root=root, fetch=fetch or None)
    win.show()
    return app.exec()


def main() -> int:
    from repo_numbat.cli import main as cli_main
    return cli_main()
