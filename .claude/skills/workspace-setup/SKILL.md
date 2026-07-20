---
name: workspace-setup
description: Use when a developer has freshly cloned this workspace repo and needs to adapt it to their environment, when onboarding to the multi-repo task workflow, or when repos.list / CLAUDE.local.md are missing or still contain template placeholders. Invoke as /workspace-setup.
---

# Workspace Setup

Adapt the generic multi-repo workspace to this developer's environment. The
outcome is a working setup: repos cloned, scripts on PATH, workspace context
filled in, tracker connected (or explicitly skipped), verified end to end.

## Gather these inputs first (ask the user; never guess or use placeholders)

1. **Repositories**: name + origin URL for each. Note: repos whose tooling
   pushes from headless sessions should use HTTPS remotes (gh credential
   helper works without an ssh-agent).
2. **Issue tracker**: which one (Jira, Linear, GitHub Issues, ...), how Claude
   reaches it (MCP plugin, `gh`), and the status mapping for
   `active | in-review | paused | completed`. "No tracker" is valid: manifest
   `status`/`notes` become the source of truth.
3. **Ticket ID format**: the default `TICKET_PATTERN` matches any
   `PROJECT-NUMBER`; ask only if their IDs differ or they want it narrowed
   (env var override, no script edit).
4. **Validation gate** (optional): repos with pinned test/lint commands for
   `/finish-task`; otherwise it falls back to auto-detection.

## Steps

1. Prerequisites: `git --version` (2.15+), `bash --version` (4+), and if PRs
   or GitHub Issues are involved, `gh auth status`.
2. `cp repos.list.example repos.list`, replace the example entries with the
   real ones (`name|origin-url` per line).
3. Run `.bin/workspace-bootstrap`. Confirm every repo cloned; it also creates
   `CLAUDE.local.md` from the template. The script is idempotent, so re-run it
   after fixing any failed URL.
4. PATH: append `export PATH="<workspace>/.bin:$PATH"` to the user's shell rc
   (ask which shell). This is the only step outside the workspace directory,
   so confirm before editing; if declined, tell them the line to add.
5. Fill in every section of `CLAUDE.local.md` from the gathered inputs. Done
   means zero `<...>` template placeholders remain; delete sections that do
   not apply (e.g. gate configuration).
6. Tracker: verify the connection live (fetch one real ticket via the MCP
   connection, or `gh issue list`) and record the status mapping in
   CLAUDE.local.md. If the MCP plugin is not yet installed/authenticated,
   give the user the exact steps (`/plugin`, then `/mcp` to authenticate).
7. Global layer: if `~/.claude/CLAUDE.md` does not exist, offer to seed it
   from `global/CLAUDE.md.example` (this edits the user's home directory, so
   confirm first). Point at `global/README.md` for plugins, hooks, and
   user-level skills. Never modify an existing `~/.claude/CLAUDE.md` or
   `settings.json`; at most show what `global/` suggests merging.
8. Smoke test with a throwaway ticket, then remove ALL traces:

   ```bash
   task-start TEST-1 <first-repo> -d "Setup smoke test"
   task-status TEST-1            # expect: on-branch, clean, wt
   task-clean TEST-1
   git -C <first-repo> branch -D TEST-1
   rm .tasks/TEST-1.yaml
   ```

9. Report a final summary table: input -> where it landed (file/config), plus
   any steps the user still owes (PATH source, MCP auth, gate setup).

## Verification (done looks like this)

- `repos.list` has real entries; every listed repo is cloned at the root
- `CLAUDE.local.md` complete, no template placeholders
- `task-status` runs bare (PATH) and exits 0
- Tracker connection proven with a live read, or "no tracker" recorded
- Global layer seeded from `global/`, or explicitly declined; an existing
  `~/.claude` config left untouched either way
- No smoke-test residue: `.worktrees/` empty, no TEST-1 branch or manifest
- `git status` in the workspace repo is clean (`repos.list`, `CLAUDE.local.md`
  are untracked by design; never commit them)
