"""Talk to the GitHub REST API to find repositories that are not cloned locally.

Authentication (first one that works wins):
  1. token saved in Settings
  2. GITHUB_TOKEN / GH_TOKEN environment variables
  3. `gh auth token` if the GitHub CLI is installed and logged in
Without a token only the public repositories of a username can be listed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from repo_numbat import __version__

API = "https://api.github.com"


@dataclass
class GitHubRepo:
    full_name: str        # owner/name
    owner: str
    name: str
    private: bool
    fork: bool
    archived: bool
    description: str
    pushed_at: str        # ISO date
    size_kb: int
    default_branch: str
    clone_url: str        # https
    ssh_url: str
    html_url: str
    local_path: Path | None = None   # set when a local clone was matched

    @property
    def key(self) -> str:
        return self.full_name.lower()


class GitHubError(Exception):
    pass


# ------------------------------------------------------------------ auth
def find_token(saved: str = "") -> tuple[str, str]:
    """Return (token, source). Empty token means anonymous access."""
    if saved.strip():
        return saved.strip(), "settings"
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var].strip(), f"${var}"
    if shutil.which("gh"):
        try:
            proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=False)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip(), "gh auth token"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "", "anonymous"


# ------------------------------------------------------------- HTTP layer
def _get(url: str, token: str) -> tuple[object, dict]:
    return _request("GET", url, token)


def _request(method: str, url: str, token: str, body: dict | None = None) -> tuple[object, dict]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"repo-numbat/{__version__}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            message = json.loads(body).get("message", body)
        except ValueError:
            message = body
        if exc.code == 401:
            raise GitHubError("GitHub rejected the token (401). Check Settings > GitHub token.") from exc
        if exc.code == 422:
            errors = []
            try:
                errors = [e.get("message") or e.get("code", "") for e in json.loads(body).get("errors", [])]
            except ValueError:
                pass
            raise GitHubError(f"GitHub refused the request: {message}" + (f" ({'; '.join(errors)})" if errors else "")) from exc
        if exc.code == 404 and token:
            raise GitHubError("GitHub API 404: not found, or the token lacks the 'repo' scope for this action.") from exc
        if exc.code == 403 and "rate limit" in message.lower():
            raise GitHubError("GitHub API rate limit hit. Add a token in Settings to raise it.") from exc
        raise GitHubError(f"GitHub API {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"cannot reach GitHub: {exc.reason}") from exc


def _paged(url: str, token: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        data, headers = _get(f"{url}{sep}per_page=100&page={page}", token)
        if not isinstance(data, list):
            raise GitHubError(f"unexpected response from {url}")
        items.extend(data)
        if len(data) < 100 or 'rel="next"' not in headers.get("Link", ""):
            return items
        page += 1


def _to_repo(d: dict) -> GitHubRepo:
    return GitHubRepo(
        full_name=d["full_name"], owner=d["owner"]["login"], name=d["name"],
        private=bool(d.get("private")), fork=bool(d.get("fork")), archived=bool(d.get("archived")),
        description=d.get("description") or "", pushed_at=(d.get("pushed_at") or "")[:10],
        size_kb=int(d.get("size") or 0), default_branch=d.get("default_branch") or "",
        clone_url=d.get("clone_url") or "", ssh_url=d.get("ssh_url") or "", html_url=d.get("html_url") or "",
    )


def list_repos(token: str, username: str = "") -> tuple[list[GitHubRepo], str]:
    """All repos visible to the token (own, collaborator, org member) or the public repos of *username*.

    Returns (repos, login_used).
    """
    if token:
        me, _ = _get(f"{API}/user", token)
        login = me.get("login", "")
        raw = _paged(f"{API}/user/repos?affiliation=owner,collaborator,organization_member&sort=pushed", token)
        seen: dict[str, dict] = {d["full_name"].lower(): d for d in raw}
        # /user/repos does not always include every org repo the user can see; add orgs explicitly
        for org in _paged(f"{API}/user/orgs", token):
            try:
                for d in _paged(f"{API}/orgs/{org['login']}/repos?type=all", token):
                    seen.setdefault(d["full_name"].lower(), d)
            except GitHubError:
                continue  # org may restrict third-party token access
        return [_to_repo(d) for d in seen.values()], login
    if not username:
        raise GitHubError("No GitHub token found and no username set. Fill in Settings > GitHub.")
    raw = _paged(f"{API}/users/{urllib.parse.quote(username)}/repos?type=owner&sort=pushed", "")
    return [_to_repo(d) for d in raw], username


# ------------------------------------------------------------ matching
_SSH_RE = re.compile(r"^(?:ssh://)?(?:[\w.-]+@)?(?P<host>[\w.-]+)[:/](?P<path>.+)$")


def remote_key(url: str) -> str | None:
    """Normalise a GitHub remote URL to 'owner/name' (lower-case), or None if not GitHub."""
    if not url:
        return None
    host, path = "", ""
    if "://" in url:
        u = urllib.parse.urlparse(url)
        host, path = (u.hostname or ""), u.path
    else:
        m = _SSH_RE.match(url)
        if not m:
            return None
        host, path = m.group("host"), m.group("path")
    if host.lower() not in ("github.com", "www.github.com"):
        return None
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    name = parts[1][:-4] if parts[1].lower().endswith(".git") else parts[1]
    return f"{parts[0]}/{name}".lower()


def guess_username(remote_urls: list[str]) -> str:
    """Most common GitHub owner among the local remotes; a decent default for anonymous mode."""
    owners = Counter(k.split("/")[0] for k in map(remote_key, remote_urls) if k)
    return owners.most_common(1)[0][0] if owners else ""


def match_local(repos: list[GitHubRepo], local: dict[str, str], root: Path) -> None:
    """Fill ``local_path`` on each repo that exists locally.

    *local* maps repo directory path -> remote URL ('' when none).  A repo counts as
    present when a local remote points at it, or a folder with the same name exists.
    """
    by_key: dict[str, Path] = {}
    for path, url in local.items():
        if key := remote_key(url):
            by_key.setdefault(key, Path(path))
    folders = {Path(p).name.lower(): Path(p) for p in local}
    for r in repos:
        r.local_path = by_key.get(r.key) or folders.get(r.name.lower())
        if r.local_path is None and (root / r.name).is_dir():
            r.local_path = root / r.name


# ------------------------------------------------------------ creating
def whoami(token: str) -> str:
    """Login of the token's user."""
    if not token:
        raise GitHubError("A GitHub token is required to create repositories. "
                          "Run 'gh auth login' or set a token in Settings.")
    me, _ = _get(f"{API}/user", token)
    return me.get("login", "")


def list_orgs(token: str) -> list[str]:
    """Organisations the token's user belongs to."""
    return [o["login"] for o in _paged(f"{API}/user/orgs", token)]


def create_repo(token: str, owner: str, is_org: bool, name: str, description: str = "",
                private: bool = True) -> GitHubRepo:
    """Create an empty repository under *owner* (the user or one of their orgs)."""
    url = f"{API}/orgs/{urllib.parse.quote(owner)}/repos" if is_org else f"{API}/user/repos"
    body = {"name": name, "description": description, "private": private, "auto_init": False}
    data, _ = _request("POST", url, token, body)
    if not isinstance(data, dict) or "full_name" not in data:
        raise GitHubError("unexpected response when creating the repository")
    return _to_repo(data)


def repo_visibility(token: str, owner: str, name: str) -> str:
    """'public' | 'private' | 'unknown' for one GitHub repository."""
    try:
        data, _ = _get(f"{API}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}", token)
    except GitHubError as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            return "unknown"   # private and not visible to us, or gone
        raise
    if not isinstance(data, dict) or "private" not in data:
        return "unknown"
    return "private" if data["private"] else "public"


def visibility_map(token: str, keys: list[str], username: str = "") -> dict[str, str]:
    """Visibility for each 'owner/name' key, using one listing call plus per-repo lookups for the rest."""
    result: dict[str, str] = {}
    if not keys:
        return result
    try:
        repos, _ = list_repos(token, username)
        listed = {r.key: ("private" if r.private else "public") for r in repos}
    except GitHubError:
        listed = {}
    for key in keys:
        if key in listed:
            result[key] = listed[key]
        else:
            owner, name = key.split("/", 1)
            result[key] = repo_visibility(token, owner, name)
    return result
