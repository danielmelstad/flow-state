# CLAUDE.md

This file provides context to Claude Code when working in example-service.

## What this project is

A small Python service library (slug generation for URLs). Source in
`src/example_service/`, tests in `tests/`.

## Commands

Quality gate (same commands the `/finish-task` pipeline runs; use these, do
not invent alternatives):

```bash
scripts/gate.sh test      # full pytest suite in the pinned venv
scripts/gate.sh lint      # ruff check
scripts/gate.sh format    # ruff format (apply before committing)
```

The gate bootstraps `.venv-gate/` on first run and rebuilds it whenever
`pyproject.toml` changes; there is nothing else to install.

## Conventions

- Commits are prefixed with the ticket ID: `TASK-123: Add slug length limit`
- Work happens in the task worktree (`.worktrees/<ticket>/example-service/`),
  not in this checkout, when part of a multi-repo task
- Dependencies are exact-pinned in `pyproject.toml`; bump deliberately, run
  the full gate after any bump

## Documentation policy

- `README.md` owns purpose and usage
- Docstrings own per-function behavior; no separate API docs
- This file owns commands and conventions; do not restate them elsewhere
