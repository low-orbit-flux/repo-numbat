# Repo Numbat

A desktop dashboard for all the git repositories in your `~/repos` folder.
One table, one row per repo, showing at a glance what still needs to be
added, committed, pushed or pulled, whether a remote is connected, and who
owns each repo. Written in Python with a Qt (PySide6) fat-client GUI in a dark
olive theme. Runs on Linux, macOS and Windows.

![numbat](repo_numbat/assets/numbat-128.png)

## What the table shows

| Column | Meaning |
| --- | --- |
| dot | green = clean and in sync, amber = needs attention, red = merge conflicts or diverged branch, grey = no remote / not a repo |
| Repo, Branch | folder name and checked-out branch |
| Status | `Clean`, `Uncommitted`, `Unpushed`, `Unpulled`, any combination, or `All of the above` |
| Untracked | files never added to git |
| Modified | tracked files changed in the working tree but not staged |
| Staged | changes added to the index but not committed |
| To push | local commits the remote does not have (`no upstream` if the branch was never pushed) |
| To pull | remote commits not merged locally. Press **Fetch** to make this current |
| Remote | `connected` (hover for the URL) or `not connected` |
| Remote owner | the user or group/organisation segment of the remote URL, e.g. `acme @ github.com` |
| Owner | who owns the directory on this machine: `you (name)`, `your group (name)`, or `user:group` for someone else |
| Size | disk space used by the folder including `.git` (allocated blocks on Linux/macOS, file sizes on Windows) |
| Stashes, Last commit, Remote URL, Path | extra context |

The bottom pane has a **Log** tab (what the tool is doing) and a **Details**
tab with `git status`, recent log and remotes for the selected repo.

Toolbar / right-click actions: Open in file manager, Refresh (F5), Fetch
(Ctrl+F5, runs `git fetch` on every remote), Terminal here, Copy path,
Pull (`--ff-only`) and Push (both ask first). Search filters every column.

**GitHub** (Ctrl+G) asks the GitHub API for every repository you own, collaborate
on or can see through an organisation, and lists the ones that have no clone
under the repos folder (matched by remote URL, then by folder name). Select
rows and press **Clone selected** to clone them into the repos folder, or copy
the URL / open them in the browser. A token is needed for private and
organisation repos; it is taken from Settings, then `$GITHUB_TOKEN` or
`$GH_TOKEN`, then `gh auth token` if the GitHub CLI is logged in. Without a
token only the public repos of the username in Settings (guessed from your
remotes if empty) are listed. A token saved in Settings is stored in plain
text in the QSettings store, so prefer the environment variable or `gh` if
that matters to you.
**View** can hide non-git folders or show only repos that need attention, and
toggle columns. **Settings** changes the repos folder, enables fetch on every
refresh, sets an auto-refresh interval and the number of parallel scans.

## Running it

Requirements: Python 3.10 or newer and `git` on your PATH. The launchers
create a private virtual environment in `.venv` the first time and install
PySide6 into it (about 150 MB), then start the GUI. `uv` is used if present,
otherwise `venv` + `pip`.

Linux / macOS:

```sh
./scripts/repo-numbat            # GUI
./scripts/repo-numbat --cli      # plain text table in the terminal
./scripts/repo-numbat --fetch    # git fetch first so To pull is accurate
./scripts/repo-numbat --root ~/src
```

macOS: double-click `scripts/repo-numbat.command` in Finder.

Windows (cmd or double-click):

```bat
scripts\repo-numbat.bat
scripts\repo-numbat.bat --cli
```

Windows PowerShell:

```powershell
.\scripts\repo-numbat.ps1
```

To work in the environment yourself, source it:

```sh
source scripts/env.sh          # creates/activates .venv, sets PYTHONPATH
python -m repo_numbat
```

Set `REPO_NUMBAT_PYTHON=/path/to/python3.12` to pick the interpreter, or
`REPO_NUMBAT_VENV` to put the environment somewhere else.

Alternatively install it as a package: `pip install .` gives you a
`repo-numbat` command.

### Installing on the machine

`scripts/install.sh` (Linux, macOS) and `scripts\install.ps1` or
`scripts\install.bat` (Windows) install a self-contained copy that does not
depend on this checkout:

```sh
./scripts/install.sh              # Linux/macOS, current user, no root needed
./scripts/install.sh --system     # Linux: /opt/repo-numbat + /usr/local/bin (sudo)
./scripts/install.sh --uninstall
```

```powershell
.\scripts\install.ps1             # Windows, current user (or double-click install.bat)
.\scripts\install.ps1 -Uninstall
```

* Linux, any distro: program files go to `~/.local/share/repo-numbat` with
  their own virtualenv, `~/.local/bin/repo-numbat` is linked, and a menu
  entry plus the numbat icon are installed. GNOME and KDE show that icon in
  the dock for the running window, on Wayland and X11.
* macOS: builds `Repo Numbat.app` and copies it into `/Applications` (or
  `~/Applications`), and links `~/.local/bin/repo-numbat` to it. The numbat
  shows in the Dock and Launchpad.
* Windows: program files go to `%LOCALAPPDATA%\Programs\Repo Numbat` with
  their own virtualenv, a Start Menu shortcut with `numbat.ico` is created,
  and `repo-numbat` is added to the user PATH.

Nothing beyond Python 3.10+ and git is needed on any platform; the installer
downloads PySide6 into the private virtualenv. Settings are kept on uninstall.

### Building a standalone app (macOS `.app`, Windows `.exe`, Linux)

`scripts/build-app.sh` (macOS/Linux) and `scripts\build-app.bat` (Windows)
use PyInstaller with `packaging/repo-numbat.spec`:

```sh
./scripts/build-app.sh          # macOS: dist/Repo Numbat.app, drag into /Applications
./scripts/build-app.sh --dmg    # macOS: also dist/Repo-Numbat.dmg with an Applications link
scripts\build-app.bat           # Windows: dist\Repo Numbat\Repo Numbat.exe
```

The bundle carries its own Python and Qt (about 230 MB) and needs no
virtualenv on the target machine. It must be built on the platform it is for.
The macOS bundle is ad-hoc signed so it opens on the machine that built it;
to give it to other Macs, sign and notarize it with your Developer ID or they
will need to right-click > Open the first time.

## Layout

```
repo_numbat/
  app.py            main window, table model, actions
  gitscan.py        runs git and turns the porcelain output into RepoStatus
  ownership.py      directory owner/group detection (POSIX and Win32)
  cli.py            argument parsing and the --cli text table
  theme.py          colours and Qt stylesheet
  icons.py          toolbar icons drawn with QPainter, status dots
  platform_open.py  open folder / terminal on each OS
  assets/           numbat.svg plus rendered PNG sizes and numbat.ico
scripts/            launchers and environment scripts
tools/make_icon.py  re-renders the PNG/ICO files from numbat.svg
```

Settings are stored with `QSettings`: `~/.config/repo-numbat/` on Linux,
`~/Library/Preferences/` on macOS and the registry on Windows.
