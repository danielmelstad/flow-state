# example-service

A minimal reference project showing how a repository in this workspace is set
up for the task workflow and the validation gate. It is a tracked example
inside the workspace repo; real projects are separate git repos cloned to the
workspace root via `repos.list`, each carrying these same files.

What it demonstrates:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project-level context: commands, structure, conventions. Claude Code loads it whenever working inside this project |
| `.no-mistakes.yaml` | Gate configuration: pins the exact test/lint/format commands and the documentation placement policy |
| `scripts/gate.sh` | The pinned commands, self-bootstrapping and runnable by developers and CI alike |
| `pyproject.toml` | Exact-pinned dev dependencies so the gate is deterministic |

Try it:

```bash
cd examples/example-service
scripts/gate.sh test      # bootstraps a private venv on first run, then pytest
scripts/gate.sh lint      # ruff check
scripts/gate.sh format    # ruff format
```

The gate contract: whatever validation pipeline drives `/finish-task` reads
`.no-mistakes.yaml` and runs these commands before anything is pushed. Repos
without such a file fall back to the pipeline's auto-detection; pinning the
commands makes the gate deterministic and identical for humans, Claude, and CI.
