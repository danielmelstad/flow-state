#!/usr/bin/env sh
# Deterministic checks for the validation gate; also usable directly by developers.
# Bootstraps a private venv on first run and reuses it until pyproject.toml changes.
set -eu
cd "$(dirname "$0")/.."

VENV=".venv-gate"
STAMP="$VENV/.pyproject.stamp"
if [ ! -x "$VENV/bin/python" ] || ! cmp -s pyproject.toml "$STAMP"; then
    rm -rf "$VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --editable ".[dev]"
    cp pyproject.toml "$STAMP"
fi

case "${1:-}" in
    test)   exec "$VENV/bin/python" -m pytest ;;
    lint)   exec "$VENV/bin/ruff" check . ;;
    format) exec "$VENV/bin/ruff" format . ;;
    *)      echo "usage: $0 test|lint|format" >&2; exit 2 ;;
esac
