# Source this file to set up (and activate) the Repo Numbat environment:
#     source scripts/env.sh
# It is also used by the launcher scripts.  Variables set: PROJECT, VENV, VENV_PY.
# Override the interpreter with REPO_NUMBAT_PYTHON=/path/to/python3.

_rn_here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT="$(cd "$_rn_here/.." && pwd)"
VENV="${REPO_NUMBAT_VENV:-$PROJECT/.venv}"
VENV_PY="$VENV/bin/python"

_rn_find_python() {
    if [ -n "${REPO_NUMBAT_PYTHON:-}" ]; then echo "$REPO_NUMBAT_PYTHON"; return; fi
    for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$c"; return
        fi
    done
    echo "repo-numbat: no Python >= 3.10 found on PATH (set REPO_NUMBAT_PYTHON)" >&2
    return 1
}

if [ ! -x "$VENV_PY" ]; then
    _rn_py="$(_rn_find_python)" || return 1 2>/dev/null || exit 1
    echo "repo-numbat: creating virtualenv in $VENV with $_rn_py"
    if command -v uv >/dev/null 2>&1; then
        uv venv --python "$_rn_py" "$VENV"
    else
        "$_rn_py" -m venv "$VENV"
    fi
fi

if ! "$VENV_PY" -c 'import PySide6' 2>/dev/null; then
    echo "repo-numbat: installing requirements into $VENV"
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$VENV_PY" -r "$PROJECT/requirements.txt"
    else
        "$VENV_PY" -m pip install --upgrade pip >/dev/null
        "$VENV_PY" -m pip install -r "$PROJECT/requirements.txt"
    fi
fi

export PYTHONPATH="$PROJECT${PYTHONPATH:+:$PYTHONPATH}"
# Activate when sourced interactively so `python -m repo_numbat` just works.
if [ -f "$VENV/bin/activate" ] && [ "${BASH_SOURCE[0]:-}" != "$0" ]; then
    # shellcheck disable=SC1091
    . "$VENV/bin/activate"
fi
