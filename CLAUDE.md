# CLAUDE.md

This file provides context to Claude Code about this multi-project workspace.
It describes the generic workflow only; everything specific to this
machine/team (which repositories, which issue tracker, per-repo conventions)
lives in the untracked `CLAUDE.local.md`, imported here:

@CLAUDE.local.md

If that import is missing, copy `CLAUDE.local.md.example` to `CLAUDE.local.md`
and fill it in.

## Workspace Overview

This workspace (the directory containing this file, e.g. `~/projects/`)
orchestrates work across multiple git repositories. Tasks are identified by
issue tracker ticket IDs (e.g. `TASK-123`) and frequently span several repos.
To recreate the workspace on a new machine: clone this repo, then run
`/workspace-setup` (interactive, recommended) or `.bin/workspace-bootstrap`
(clone repos only). If `CLAUDE.local.md` is missing or still has template
placeholders, offer to run `/workspace-setup`.

## Quick Start: Working on a Task

```
# See all active tasks
task-status

# Get context for a specific task
task-status TASK-123

# Set up worktrees for a task (isolated working directories)
task-switch TASK-123

# Start a new cross-repo task (creates branches + worktrees)
task-start TASK-124 repo-a repo-b

# Finish a ticket: validate, push, create cross-linked PRs (hands-off)
#   -> posts PR links as a tracker comment; sets local status cache to in-review; worktrees are kept
/finish-task TASK-123

# After the PRs merge: transition the ticket to done, mark completed, remove worktrees
task-finish TASK-123 --cleanup
```

When a user says "work on TASK-123":
1. Read the ticket + its comments in the issue tracker (via its MCP connection;
   see CLAUDE.local.md) for scope and the latest session handoff; read the
   manifest `.tasks/TASK-123.yaml` for the repo/branch list
2. Run `task-switch TASK-123` to create/verify worktrees
3. Work in `.worktrees/TASK-123/<repo>/` directories (NOT the main repo dirs)
4. At session end, post a tracker comment: what was done, what remains,
   decisions made
5. If the tracker is unreachable (MCP not connected, headless session), fall
   back to the manifest `notes` field and say so; sync the note to the tracker
   next connected session

**Worktree workflow:** Each task gets isolated working directories at
`.worktrees/<ticket>/<repo>/`. Multiple tasks can be active simultaneously with
no checkout conflicts. Main repos stay on their default branch.

**Task state lives in the issue tracker:** the tracker is the source of truth
for ticket status, scope, and progress; comments are the cross-session handoff.
The local manifest holds only machine state (repo/branch mapping for the
scripts) plus a `status` field that is a **local cache** of the tracker for
offline display. Update both together on transitions; the tracker wins on
conflict. The concrete status mapping is defined in CLAUDE.local.md.

**Ticket lifecycle:** `active` (work in progress) -> `in-review` (PRs delivered
via `/finish-task`, which posts the PR links as a tracker comment) ->
`completed` (PRs merged, `task-finish` run, ticket transitioned to done);
`paused` for parked work. `/finish-task` runs a validation gate (review, test,
docs, lint) before pushing when one is installed; `task-prs` remains as the
manual fallback.

## Workspace Structure

```
~/projects/
├── CLAUDE.md                      # This file (generic workflow)
├── CLAUDE.local.md                # Machine/team specifics (untracked)
├── repos.list                     # Child repos (name|url), untracked; see repos.list.example
├── .tasks/                        # Task manifests (one per ticket), untracked
│   ├── TASK-123.yaml
│   └── schema.json
├── .bin/                          # Multi-repo task scripts (in PATH)
│   ├── task-lib                   # Shared library (sourced, not executable)
│   ├── workspace-bootstrap        # Clone repos.list on a new machine / --snapshot
│   ├── task-start
│   ├── task-status
│   ├── task-switch
│   ├── task-finish
│   ├── task-detect
│   ├── task-prs
│   ├── task-pr-status
│   └── task-clean
├── .worktrees/                    # Git worktrees per task (auto-managed)
│   ├── TASK-123/
│   │   ├── repo-a/                # Independent worktree
│   │   └── repo-b/
│   └── TASK-200/
│       └── repo-b/                # Separate worktree, same repo, no conflict
├── .claude/agents/                # Specialist agents
├── .docs/                         # Central documentation hub
└── <repo>/                        # Main git repositories (stay on default branch)
```

## Task Manifests

Each active ticket has a YAML manifest at `.tasks/<TICKET-ID>.yaml`. The
manifest is a thin machine-state file; scope, checklists, and session logs live
in the tracker (description + comments):

```yaml
task: TASK-123
created: 2025-08-18T10:00:00+00:00
status: active          # LOCAL CACHE of the tracker: active | in-review | paused | completed
repos:
  - name: repo-a
    branch: TASK-123
  - name: repo-b
    branch: TASK-123
description: "Short task summary"   # used for PR titles/bodies by task-prs
notes: |
  Scope, dependencies, and progress: see TASK-123 in the tracker.
  Session handoff = tracker comments. Use this field only as an offline fallback.
```

The `status` field mirrors the tracker so `task-status`/`task-clean` work
offline; when transitioning a ticket, update the tracker (source of truth) and
the cache together.

## Task Scripts (.bin/)

| Script | Purpose | Usage |
|--------|---------|-------|
| `workspace-bootstrap` | Clone all repos in repos.list; `--snapshot` regenerates the list | `.bin/workspace-bootstrap` |
| `task-start` | Create branches + worktrees + manifest | `task-start TASK-124 repo-a repo-b` |
| `task-status` | Show git state for a task or all tasks | `task-status TASK-123` or `task-status` |
| `task-switch` | Create/verify worktrees for a task | `task-switch TASK-123` |
| `task-finish` | Check uncommitted work, mark complete | `task-finish TASK-123 [--cleanup]` |
| `task-detect` | Scan repos + worktrees for ticket branches | `task-detect` |
| `task-prs` | Create PRs across repos (requires `gh`) | `task-prs TASK-123` |
| `task-pr-status` | Check PR status across repos (requires `gh`) | `task-pr-status TASK-123` |
| `task-clean` | Remove worktrees for tasks | `task-clean TASK-123` or `task-clean --list` |

## Commit Convention

Always prefix commits with the ticket ID:
```
TASK-123: Add deployment workflow
TASK-124: Update chart values for new pipeline
```

## Specialist Agents

| Agent | Use Case | Invocation |
|-------|----------|------------|
| `planner` | Implementation plans before coding (runs on Fable, cross-repo aware) | "Use planner on TASK-123" |
| `code-reviewer` | Code quality, PR reviews (cross-repo aware) | "Use code-reviewer on TASK-123" |
| `security-reviewer` | Security audits, vulnerability detection | "Use security-reviewer on repo-a/auth" |
| `test-writer` | Writing unit/integration tests | "Use test-writer for repo-b" |
| `performance-analyzer` | Finding bottlenecks, optimization | "Use performance-analyzer on repo-a" |
| `refactorer` | Code cleanup, reducing duplication | "Use refactorer on repo-b" |
| `documentation-writer` | READMEs, API docs, code comments | "Use documentation-writer for repo-a" |

**Plan mode uses `planner`, not the generic planning agent.** Before writing a
plan file for any non-trivial or multi-repo task, dispatch the `planner` agent
(which runs on Fable) on the ticket and reconcile its plan into the final one.
The harness's own plan-mode workflow suggests the generic `Explore` and `Plan`
agent types; those do not substitute for `planner`, which is cross-repo aware,
reads the task manifest and the tracker, and knows the workspace rules
(ticket-prefixed commits, the no-mistakes gate, `/finish-task`). Skip it only
for genuinely trivial work: a typo, a one-line change, a rename.

Agents can be chained:
```
"First use code-reviewer on TASK-123, then use security-reviewer on repo-a"
```

## Documentation

All generated documentation goes to `.docs/<project>/`:
```
.docs/
├── README.md                      # Index of all project docs
├── <project>/
│   ├── managers/                  # Non-technical stakeholder docs
│   ├── developers/                # Technical documentation
│   └── reference/                 # API/schema reference
└── ...
```
