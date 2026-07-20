---
name: finish-task
description: Use when a ticket's work is committed and ready to ship. Validates, pushes, and creates PRs for every repo in a task via the no-mistakes pipeline, cross-links the PRs, posts the PR links to the issue tracker, and updates the local status cache. Invoke as /finish-task <TICKET-ID>.
---

# Finish Task

Deliver PRs for every repo in a task, fully hands-off. The pipeline delivers a PR; the user reviews on GitHub afterwards.

## Inputs

- `TICKET-ID`, e.g. `TASK-123`. If omitted, use the ticket from session context; if ambiguous, ask before doing anything.

## Phase 1: Preflight (abort before any push)

1. Manifest must exist: `.tasks/<TICKET>.yaml`. Read `description` and the repo list with branches.
2. For every repo in the manifest:
   - The worktree `.worktrees/<TICKET>/<repo>/` must exist (run `task-switch <TICKET>` if missing).
   - The worktree must be on the ticket branch and have NO uncommitted changes (`git status --porcelain` empty).
3. If any repo fails preflight: STOP. Print a per-repo table of problems. Push nothing.

## Phase 2: Per-repo gate (continue past failures)

For each repo in the manifest, working inside `.worktrees/<TICKET>/<repo>/`:

1. Skip-if-done: if a PR for the ticket branch already exists (`gh-axi pr list --head <branch> --state all` returns a result; `gh-axi pr view` only accepts a numeric PR id, not a branch), record its URL and skip to the next repo. Never create a duplicate PR.
2. Ensure the gate is configured: if `git remote get-url no-mistakes` fails, run `no-mistakes init`.
3. Run the no-mistakes pipeline for the branch (use the /no-mistakes skill, which drives `no-mistakes axi`). It runs review, tests, lint, docs, then pushes, creates the PR, and watches CI. Let it apply mechanical fixes; commit any fixes it makes with a `<TICKET>: ` prefixed message.
4. If the gate fails for this repo: record the failure reason and CONTINUE with the remaining repos.

## Phase 3: Normalize PR titles and bodies

For each PR created (or pre-existing), set the final title and body with `gh-axi pr edit` (fallback: `gh pr edit`):

- Title: `<TICKET>: <manifest description>` unless a more specific one-line summary of this repo's diff is clearly better; then `<TICKET>: <specific summary>`.
- Body, written from the repo's actual history (`git log origin/<base>..<branch> --oneline` and `git diff origin/<base>...<branch> --stat`), in this structure:

```markdown
## Summary

<2-4 sentences: what changed in THIS repo and why, derived from the commits and diff, not the manifest boilerplate>

## Changes

<bullet list of the significant changes, grouped by area>

## Testing

<what the no-mistakes gate ran and any manual verification>

Part of <TICKET>.
```

- No agent attribution anywhere in titles or bodies.

## Phase 4: Cross-link sibling PRs

After all repos are processed, if the task produced 2+ PRs: append to each PR body a section

```markdown
## Related PRs

- <repo>: <PR URL>
```

listing every OTHER PR in the task. Use `gh-axi pr edit` to update bodies. Skip this phase for single-repo tasks.

## Phase 5: Wrap-up

1. Post a comment on the ticket in the issue tracker (via its MCP connection; tracker and status mapping are documented in CLAUDE.local.md): dated entry with the PR links and a one-line summary per repo. This comment marks the review phase. Transition the ticket per the CLAUDE.local.md status mapping for `in-review`.
2. Set the local status cache: `sed -i "s/^status: .*/status: in-review/" .tasks/<TICKET>.yaml`
3. If the tracker is unreachable (MCP not connected, headless session): append the same dated entry to the manifest `notes` field instead, and flag in the final summary that the tracker comment is owed.
4. Do NOT remove worktrees (review feedback may need fixes on the branch). Cleanup happens after merge via `task-finish <TICKET> --cleanup` (transition the ticket to its done status at that point).
5. Print a final summary table: repo, branch, PR URL or failure reason.

## Failure handling

- Per-repo failures never abort the other repos; they appear in the final summary.
- Re-invoking `/finish-task <TICKET>` is safe: repos with an existing PR are skipped in Phase 2 but still get Phases 3-4.
- Never force-push.
- If no-mistakes itself is broken or unavailable, tell the user and offer the fallback: `task-prs <TICKET> --title "<TICKET>: <description>"` followed by manual Phase 3/4 via gh-axi.
