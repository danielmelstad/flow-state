# Multi-Repo Task Orchestration with Git Worktrees

A lightweight shell-based workflow for managing tasks that span multiple git repositories. Uses git worktrees to isolate each task into its own working directories, so multiple tasks can be active simultaneously without checkout conflicts.

## The Problem

When a single task (bug fix, feature, migration) touches 3-4 repositories at once, you need a way to:

- Track which repos and branches belong to which task
- Switch between tasks without losing context
- Avoid conflicts when two tasks share a repo (e.g., both need `repo-b`)
- Create PRs and check status across all repos at once

The naive approach — `git checkout` in each repo — breaks down as soon as you have overlapping tasks. Checking out task B in a shared repo wipes out task A's working context.

## The Solution

Each task gets **isolated git worktrees**:

```
projects/
├── .worktrees/
│   ├── TASK-100/
│   │   ├── repo-a/       ← git worktree on TASK-100 branch
│   │   └── repo-b/       ← git worktree on TASK-100 branch
│   └── TASK-200/
│       ├── repo-b/       ← independent worktree, same repo
│       └── repo-c/
├── repo-a/                ← main repo (stays on default branch)
├── repo-b/
├── repo-c/
├── .tasks/                ← YAML manifests tracking each task
└── .bin/                  ← task scripts
```

Worktrees share git objects with the main repo — only working tree files are duplicated, keeping disk usage minimal.

## Setup

### Prerequisites

- Bash 4+ (for associative arrays)
- Git 2.15+ (for worktree support)
- `gh` CLI (optional, for PR creation/status)

### Installation

The workspace root is itself a git repo that tracks only the generic orchestration files: the `.bin/` scripts, `.tasks/schema.json`, `.claude/` config, `CLAUDE.md`, and templates. Everything specific to you stays untracked: the child repos themselves, worktrees, task manifests, `repos.list` (your set of repositories), and `CLAUDE.local.md` (your workspace context).

Using Claude Code? After cloning, run `/workspace-setup` and it walks you through everything below interactively (repos, tracker, PATH, verification). The manual steps:

1. Clone the workspace and declare your repositories:

```bash
git clone <workspace-remote-url> ~/projects
cd ~/projects
cp repos.list.example repos.list      # then edit in your repos (name|origin-url per line)
.bin/workspace-bootstrap              # clones every repo listed in repos.list
```

If your repos are already cloned in the workspace root, generate the list from them instead: `workspace-bootstrap --snapshot`.

2. Add `.bin/` to your PATH:

```bash
echo 'export PATH="$HOME/projects/.bin:$PATH"' >> ~/.bashrc
```

`PROJECTS_DIR` is derived from the script location automatically; nothing needs editing.

3. Fill in `CLAUDE.local.md` (bootstrap creates it from `CLAUDE.local.md.example`): your repo map, issue tracker connection, and team conventions. `CLAUDE.md` holds only the generic workflow and imports this file.

4. If using `task-detect` and the default any-`PROJECT-NUMBER` pattern is too broad, set the `TICKET_PATTERN` env var (or edit the default in `.bin/task-detect`):

```bash
# Default: any PROJECT-NUMBER ticket ID (TASK-123, INFRA-42, ...)
TICKET_PATTERN="${TICKET_PATTERN:-^[A-Z][A-Z0-9]*-[0-9]+}"

# Override without editing the script (e.g. in ~/.bashrc):
export TICKET_PATTERN='^(FEAT|BUG|INFRA)-[0-9]+'
```

## Usage

### Starting a new task

```bash
task-start TASK-100 repo-a repo-b repo-c
```

This:
1. Creates a `TASK-100` branch in each repo (from `main` by default)
2. Creates worktrees at `.worktrees/TASK-100/<repo>/`
3. Generates a manifest at `.tasks/TASK-100.yaml`

Options:
- `-d "description"` — add a description to the manifest
- `-b develop` — branch from `develop` instead of `main`
- `--no-worktree` — create branches only, skip worktree creation

### Switching to an existing task

```bash
task-switch TASK-100
```

Creates worktrees if they don't exist yet, or confirms they're ready.

### Working in worktrees

Work in `.worktrees/<task>/<repo>/` just like a normal repo — edit, commit, push:

```bash
cd .worktrees/TASK-100/repo-a/
# edit files
git add -A && git commit -m "TASK-100: Implement feature X"
git push -u origin TASK-100
```

Meanwhile, another task using the same repo works independently:

```bash
cd .worktrees/TASK-200/repo-a/   # different branch, no conflicts
```

### Checking status

```bash
# Overview of all tasks
task-status

# Detailed view: branch status, dirty state, ahead/behind per repo
task-status TASK-100
```

The detail view includes a `LOC` column indicating whether each repo uses a worktree (`wt`) or the main repo directory (`repo`).

### Creating PRs

```bash
task-prs TASK-100              # push + create PRs in all repos
task-prs TASK-100 --draft      # as draft PRs
task-prs TASK-100 --dry-run    # preview without creating

task-pr-status TASK-100        # check PR state, reviews, CI checks
```

### Finishing a task

```bash
task-finish TASK-100             # check for uncommitted work, mark complete
task-finish TASK-100 --cleanup   # also remove worktrees
task-finish TASK-100 --force     # mark complete even with dirty repos
```

### Cleaning up worktrees

```bash
task-clean TASK-100       # remove worktrees for one task
task-clean --list         # show disk usage per task
task-clean --completed    # remove worktrees for all completed tasks
task-clean --stale        # remove worktrees with no manifest
```

### Discovering existing tasks

If repos already have matching branches from prior work:

```bash
task-detect               # scan repos, create manifests for multi-repo tickets
task-detect --dry-run     # preview only
```

## Task Manifests

Each task is tracked by a YAML file at `.tasks/<TICKET-ID>.yaml`:

```yaml
task: TASK-100
created: 2025-08-18T10:00:00+00:00
status: active          # active | in-review | paused | completed
repos:
  - name: repo-a
    branch: TASK-100
  - name: repo-b
    branch: TASK-100
description: "Migrate auth service to new API"
notes: |
  Scope and progress: see TASK-100 in the issue tracker.
```

The manifest is deliberately thin machine state: it maps the ticket to repos and branches so the scripts work offline. The recommended setup keeps the issue tracker (Jira, Linear, GitHub Issues, anything with an API or MCP connection) as the source of truth for scope, status, and session handoff (ticket comments); the manifest `status` is then a local cache of the tracker, and `notes` an offline fallback. Without a tracker, `notes` works fine as a freeform checklist and session log.

## Script Reference

| Script | Purpose |
|--------|---------|
| `task-lib` | Shared library (sourced by all scripts, not executable) |
| `task-start` | Create branches + worktrees + manifest for a new task |
| `task-switch` | Create/verify worktrees for an existing task |
| `task-status` | Show git state for one task or all tasks |
| `task-finish` | Verify clean state and mark task as completed |
| `task-detect` | Scan repos for branch patterns, generate manifests |
| `task-prs` | Push branches and create PRs across repos |
| `task-pr-status` | Show PR state, reviews, and CI checks |
| `task-clean` | Remove worktrees (per-task, completed, stale, or list usage) |

## Claude Code Integration

The workspace ships Claude Code configuration that automates the workflow end to end. Two files split generic from specific:

- **`CLAUDE.md`** (tracked): the generic workflow, i.e. how tasks, manifests, worktrees, and the ticket lifecycle work.
- **`CLAUDE.local.md`** (untracked, from `CLAUDE.local.md.example`): your repositories, your issue tracker connection, your team conventions.

Recommended plugins/connections, all optional and provider-agnostic:

| Capability | Purpose | Examples |
|------------|---------|----------|
| Issue tracker MCP connection | Task state, scope, and session handoff live on the ticket; Claude reads it at session start and comments at session end | Atlassian plugin (Jira), Linear MCP, GitHub Issues via `gh` |
| GitHub CLI (`gh`) | PR creation and status across repos (`task-prs`, `task-pr-status`, `/finish-task`) | `gh auth login`, plus `gh auth refresh -s workflow` if CI files are pushed |
| Validation gate skill | `/finish-task` runs review/test/lint/docs before pushing when a gate is installed | a `no-mistakes`-style pipeline; falls back to `task-prs` without one. See `examples/example-service/` for a repo with a pinned gate |
| Specialist agents | Cross-repo review, testing, docs (in `.claude/agents/`) | included in this repo |

No tracker connected? Everything still works: task state falls back to the manifest `status` and `notes` fields.

## Customization

### Adapting to your project

The scripts make minimal assumptions. To adapt them:

1. **`repos.list`** — your set of repositories (`workspace-bootstrap --snapshot` regenerates it from what is cloned)
2. **`TICKET_PATTERN`** in `task-detect` — regex matching your ticket ID format
3. **Skip list** in `task-detect` — directories to ignore when scanning (default: `.tasks`, `.bin`, `.docs`, `.worktrees`)
4. **`CLAUDE.local.md`** — workspace-specific context for Claude Code
5. **Per-repo setup** — see `examples/example-service/` for the reference shape of a project: project-level `CLAUDE.md`, pinned validation gate (`.no-mistakes.yaml` + `scripts/gate.sh`), exact-pinned dev dependencies

`PROJECTS_DIR` is derived automatically from the script location. Everything else is derived from the manifests, so it works with any set of repositories.

## How Git Worktrees Work

A git worktree is a linked working tree that shares the same `.git` object store as the main repo. This means:

- **Low disk usage** — only working tree files are duplicated, not git history
- **Shared refs** — branches, tags, and remotes are visible from all worktrees
- **Independent state** — each worktree has its own HEAD, index, and working tree
- **One branch per worktree** — git prevents two worktrees from checking out the same branch

When a task script needs to create a worktree for a branch that's currently checked out in the main repo, it automatically switches the main repo to its default branch first.
