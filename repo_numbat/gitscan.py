"""Collect the state of every git repository under a directory.

Everything here is plain Python plus the ``git`` command line tool, so it can be
used without the GUI (see ``repo_numbat.cli``).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from repo_numbat.ownership import Ownership, describe_ownership

GIT_TIMEOUT = 30
FETCH_TIMEOUT = 90


@dataclass
class RepoStatus:
    name: str
    path: Path
    is_git: bool = True
    error: str = ""

    branch: str = ""
    head: str = ""
    upstream: str = ""
    has_remote: bool = False
    remote_name: str = ""
    remote_url: str = ""

    untracked: int = 0
    unstaged: int = 0      # modified/deleted in the working tree, not staged
    staged: int = 0        # changes in the index
    conflicts: int = 0
    ahead: int = 0         # commits not yet pushed to upstream
    behind: int = 0        # commits on upstream not yet pulled
    stashes: int = 0

    last_commit: str = ""  # relative date of HEAD
    fetched: bool = False
    ownership: Ownership = field(default_factory=Ownership)

    # ------------------------------------------------------------------ flags
    @property
    def has_uncommitted(self) -> bool:
        return (self.untracked + self.unstaged + self.staged + self.conflicts) > 0

    @property
    def has_unpushed(self) -> bool:
        return self.ahead > 0 or (self.has_remote and not self.upstream and bool(self.head))

    @property
    def has_unpulled(self) -> bool:
        return self.behind > 0

    @property
    def is_clean(self) -> bool:
        return not (self.has_uncommitted or self.has_unpushed or self.has_unpulled or self.conflicts)

    @property
    def summary(self) -> str:
        """One-line verdict for the Status column."""
        if not self.is_git:
            return "Not a git repo"
        if self.error:
            return "Error"
        if self.conflicts:
            return "Merge conflicts"
        problems = []
        if self.has_uncommitted:
            problems.append("Uncommitted")
        if self.has_unpushed:
            problems.append("Unpushed")
        if self.has_unpulled:
            problems.append("Unpulled")
        if len(problems) == 3:
            return "All of the above"
        if not problems:
            return "Clean" if self.has_remote else "Clean (no remote)"
        return " + ".join(problems)

    @property
    def severity(self) -> str:
        """'ok' | 'warn' | 'bad' | 'none' - drives the coloured dot."""
        if not self.is_git or self.error:
            return "none"
        if self.conflicts or (self.ahead and self.behind):
            return "bad"
        if not self.is_clean:
            return "warn"
        return "ok" if self.has_remote else "none"

    @property
    def owner_text(self) -> str:
        return describe_ownership(self.ownership)


# ---------------------------------------------------------------------- git io
def _git(path: Path, *args: str, timeout: int = GIT_TIMEOUT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C", GIT_OPTIONAL_LOCKS="0")
    kwargs = {}
    if sys.platform == "win32":  # keep console windows from flashing up
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True, text=True, timeout=timeout, env=env, check=False, **kwargs,
    )


def _out(path: Path, *args: str, timeout: int = GIT_TIMEOUT) -> str:
    try:
        proc = _git(path, *args, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def is_git_repo(path: Path) -> bool:
    if (path / ".git").exists():
        return True
    # bare repositories or worktrees pointing elsewhere
    return _out(path, "rev-parse", "--is-inside-work-tree") == "true"


def find_repos(root: Path) -> list[Path]:
    """Immediate sub-directories of *root* (sorted, case-insensitive)."""
    if not root.is_dir():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    return sorted(dirs, key=lambda p: p.name.lower())


def scan_repo(path: Path, fetch: bool = False) -> RepoStatus:
    status = RepoStatus(name=path.name, path=path)
    status.ownership = Ownership.of(path)
    if not is_git_repo(path):
        status.is_git = False
        return status

    try:
        _fill_remote(status)
        if fetch and status.has_remote:
            status.fetched = _fetch(status)
        _fill_porcelain(status)
        status.stashes = len(_out(path, "stash", "list").splitlines())
        status.last_commit = _out(path, "log", "-1", "--format=%cr")
    except subprocess.TimeoutExpired:
        status.error = "git timed out"
    except OSError as exc:  # git missing, permissions ...
        status.error = str(exc)
    return status


def _fill_remote(status: RepoStatus) -> None:
    remotes = _out(status.path, "remote").splitlines()
    if not remotes:
        return
    status.has_remote = True
    status.remote_name = "origin" if "origin" in remotes else remotes[0]
    status.remote_url = _out(status.path, "remote", "get-url", status.remote_name)


def _fetch(status: RepoStatus) -> bool:
    try:
        proc = _git(status.path, "fetch", "--quiet", "--no-tags", status.remote_name, timeout=FETCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        status.error = "fetch timed out"
        return False
    if proc.returncode != 0:
        status.error = (proc.stderr.strip().splitlines() or ["fetch failed"])[-1]
        return False
    return True


def _fill_porcelain(status: RepoStatus) -> None:
    proc = _git(status.path, "status", "--porcelain=v2", "--branch", "--untracked-files=all")
    if proc.returncode != 0:
        status.error = (proc.stderr.strip().splitlines() or ["git status failed"])[-1]
        return
    for line in proc.stdout.splitlines():
        if line.startswith("# branch.oid "):
            oid = line.split(" ", 2)[2]
            status.head = "" if oid == "(initial)" else oid[:8]
        elif line.startswith("# branch.head "):
            head = line.split(" ", 2)[2]
            status.branch = "(detached)" if head == "(detached)" else head
        elif line.startswith("# branch.upstream "):
            status.upstream = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            _, _, ab = line.split(" ", 2)
            a, b = ab.split()
            status.ahead, status.behind = int(a[1:]), int(b[1:])
        elif line.startswith("?"):
            status.untracked += 1
        elif line.startswith("u"):
            status.conflicts += 1
        elif line[:1] in "12":
            xy = line.split(" ", 2)[1]
            if xy[0] != ".":
                status.staged += 1
            if xy[1] != ".":
                status.unstaged += 1
    if not status.head:
        status.branch = status.branch or "(no commits)"
