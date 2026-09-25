"""Headless mode: print the same table to the terminal (``repo-numbat --cli``)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from repo_numbat.gitscan import RepoStatus, find_repos, human_size, scan_repo


def default_root() -> Path:
    return Path.home() / "repos"


def scan_all(root: Path, fetch: bool = False, workers: int = 8) -> list[RepoStatus]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda p: scan_repo(p, fetch=fetch), find_repos(root)))


def format_table(rows: list[RepoStatus]) -> str:
    headers = ["Repo", "Branch", "Status", "Untracked", "Modified", "Staged", "Ahead", "Behind", "Dir size", "Repo size", "Remote", "Owner"]
    table = [headers]
    for r in rows:
        table.append([
            r.name, r.branch, r.summary, str(r.untracked), str(r.unstaged), str(r.staged),
            str(r.ahead), str(r.behind), human_size(r.size_bytes), human_size(r.repo_bytes) if r.is_git else "", r.remote_url if r.has_remote else "none", r.owner_text,
        ])
    widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
    lines = []
    for n, row in enumerate(table):
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if n == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="repo-numbat", description="Status of every git repo under ~/repos")
    ap.add_argument("--root", type=Path, default=default_root(), help="directory containing the repos")
    ap.add_argument("--fetch", action="store_true", help="run 'git fetch' first so behind/ahead counts are current")
    ap.add_argument("--cli", action="store_true", help="print a text table instead of opening the GUI")
    args = ap.parse_args(argv)
    if not args.cli:
        from repo_numbat.app import run_gui
        return run_gui(args.root, fetch=args.fetch)
    print(format_table(scan_all(args.root, fetch=args.fetch)))
    return 0
