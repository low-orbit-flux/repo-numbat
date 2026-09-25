"""Dialog that creates a GitHub repository for a local repo that has no remote."""
from __future__ import annotations

import re
import subprocess

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QRadioButton, QVBoxLayout, QWidget)

from repo_numbat.github import GitHubError, create_repo, find_token, list_orgs, whoami
from repo_numbat.gitscan import RepoStatus, _git
from repo_numbat.theme import C

NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class _Signals(QObject):
    identity = Signal(str, str, object)   # login, auth source, [orgs]
    failed = Signal(str)
    done = Signal(str, object, bool)      # repo name, log lines, ok


class _IdentityTask(QRunnable):
    def __init__(self, signals, saved_token):
        super().__init__()
        self.signals, self.saved_token = signals, saved_token

    def run(self):
        try:
            token, source = find_token(self.saved_token)
            login = whoami(token)
            orgs = list_orgs(token)
            self.signals.identity.emit(login, source, orgs)
        except GitHubError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class _CreateTask(QRunnable):
    def __init__(self, signals, saved_token, st: RepoStatus, owner, is_org, name, description, private, use_ssh, push):
        super().__init__()
        self.signals, self.saved_token, self.st = signals, saved_token, st
        self.owner, self.is_org, self.name = owner, is_org, name
        self.description, self.private, self.use_ssh, self.push = description, private, use_ssh, push

    def run(self):
        lines: list[str] = []
        try:
            token, _ = find_token(self.saved_token)
            repo = create_repo(token, self.owner, self.is_org, self.name, self.description, self.private)
            lines.append(f"created {repo.html_url} ({'private' if repo.private else 'public'})")
            url = repo.ssh_url if self.use_ssh else repo.clone_url
            proc = _git(self.st.path, "remote", "add", "origin", url)
            if proc.returncode != 0:
                lines.append(proc.stderr.strip() or "git remote add failed")
                self.signals.done.emit(self.st.name, lines, False)
                return
            lines.append(f"git remote add origin {url}")
            if self.push and self.st.head:
                branch = self.st.branch if not self.st.branch.startswith("(") else "HEAD"
                proc = _git(self.st.path, "push", "-u", "origin", branch, timeout=300)
                lines.extend((proc.stdout + proc.stderr).strip().splitlines() or [f"pushed {branch}"])
                if proc.returncode != 0:
                    self.signals.done.emit(self.st.name, lines, False)
                    return
            elif self.push:
                lines.append("nothing to push yet: the repo has no commits")
            self.signals.done.emit(self.st.name, lines, True)
        except (GitHubError, OSError, subprocess.TimeoutExpired) as exc:
            lines.append(str(exc))
            self.signals.done.emit(self.st.name, lines, False)


class CreateRemoteDialog(QDialog):
    def __init__(self, main, st: RepoStatus):
        super().__init__(main)
        self.main, self.st = main, st
        self.login = ""
        self.setWindowTitle(f"Create GitHub repository for {st.name}")
        self.setMinimumWidth(560)
        self.signals = _Signals()
        self.signals.identity.connect(self._identity)
        self.signals.failed.connect(self._failed)
        self.signals.done.connect(self._done)

        layout = QVBoxLayout(self)
        self.status = QLabel("Asking GitHub who you are…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.owner_box = QGroupBox("Create the repository owned by")
        self.owner_layout = QVBoxLayout(self.owner_box)
        self.owner_group = QButtonGroup(self)
        self.owner_group.buttonClicked.connect(self._validate)
        layout.addWidget(self.owner_box)

        form = QFormLayout()
        self.name = QLineEdit(st.name)
        self.name.textChanged.connect(self._validate)
        form.addRow("Repository name", self.name)
        self.description = QLineEdit()
        form.addRow("Description", self.description)
        self.vis_private = QRadioButton("Private")
        self.vis_private.setToolTip("Only you, the organisation and collaborators can see it")
        self.vis_public = QRadioButton("Public")
        self.vis_public.setToolTip("Anyone can see it")
        self.vis_private.setChecked(True)
        vis_row = QHBoxLayout(); vis_row.addWidget(self.vis_private); vis_row.addWidget(self.vis_public); vis_row.addStretch(1)
        form.addRow("Visibility", vis_row)
        self.push = QCheckBox(f"Push branch '{st.branch}' after creating" if st.head else "Push after creating (no commits yet)")
        self.push.setChecked(bool(st.head))
        self.push.setEnabled(bool(st.head))
        form.addRow("", self.push)
        proto = "SSH" if main.settings.value("github_ssh", True, type=bool) else "HTTPS"
        form.addRow("Remote URL", QLabel(f"{proto} (change in Settings > GitHub)"))
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        self.buttons.accepted.connect(self.create)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._set_ready(False)
        main.pool.start(_IdentityTask(self.signals, main.settings.value("github_token", "")))

    # ------------------------------------------------------------ identity
    def _set_ready(self, ready: bool):
        self.owner_box.setEnabled(ready)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready and self._valid())

    def _identity(self, login, source, orgs):
        self.login = login
        self.status.setText(f"Signed in as <b>{login}</b> via {source}. Pick the owner: your account or one of your organisations.")
        me = QRadioButton(f"{login}  (your account)")
        me.setProperty("owner", login); me.setProperty("is_org", False)
        self.owner_group.addButton(me); self.owner_layout.addWidget(me)
        for org in sorted(orgs, key=str.lower):
            b = QRadioButton(f"{org}  (organisation)")
            b.setProperty("owner", org); b.setProperty("is_org", True)
            self.owner_group.addButton(b); self.owner_layout.addWidget(b)
        if not orgs:
            note = QLabel("You are not a member of any organisation that this token can see.")
            note.setStyleSheet(f"color: {C['muted']};")
            self.owner_layout.addWidget(note)
        self._set_ready(True)

    def _failed(self, message):
        self.status.setText(f"<span style='color:{C['bad']}'>{message}</span>")
        self.main.log(message, "ERR")

    def _valid(self) -> bool:
        return bool(NAME_RE.match(self.name.text().strip())) and self.owner_group.checkedButton() is not None

    def _validate(self, *_):
        ok = self._valid()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok and self.owner_box.isEnabled())
        bad_name = self.name.text().strip() and not NAME_RE.match(self.name.text().strip())
        self.name.setStyleSheet(f"border-color: {C['bad']};" if bad_name else "")

    # ------------------------------------------------------------ create
    def create(self):
        btn = self.owner_group.checkedButton()
        if btn is None or not self._valid():
            return
        owner, is_org = btn.property("owner"), bool(btn.property("is_org"))
        name = self.name.text().strip()
        self._set_ready(False)
        self.status.setText(f"Creating {owner}/{name}…")
        self.main.log(f"{self.st.name}: creating GitHub repo {owner}/{name}", "GH")
        self.main.pool.start(_CreateTask(
            self.signals, self.main.settings.value("github_token", ""), self.st, owner, is_org, name,
            self.description.text().strip(), self.vis_private.isChecked(),
            self.main.settings.value("github_ssh", True, type=bool), self.push.isChecked()))

    def _done(self, repo_name, lines, ok):
        for line in lines:
            self.main.log(f"{repo_name}: {line}", "GH" if ok else "ERR")
        if ok:
            self.main.rescan_path(self.st.path)
            self.main.note_visibility(self.st.path, "private" if self.vis_private.isChecked() else "public")
            self.accept()
        else:
            self.status.setText(f"<span style='color:{C['bad']}'>{lines[-1] if lines else 'failed'}</span>")
            self._set_ready(True)
