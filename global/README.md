# Global Claude Code setup

The workspace covers project- and workspace-level Claude Code configuration,
but a working environment has one more layer: the user-global `~/.claude/`
directory, which does not travel with any repo. This directory holds templates
and guidance for it.

## The four configuration layers

| Layer | Location | Travels via | Holds |
|-------|----------|-------------|-------|
| Global (user) | `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/skills/` | this `global/` directory (seed once per machine) | personal rules that apply in every project, enabled plugins, hooks, personal skills |
| Workspace, generic | `CLAUDE.md` (tracked) | the workspace repo | the multi-repo task workflow itself |
| Workspace, specific | `CLAUDE.local.md` (untracked) | `CLAUDE.local.md.example` | your repos, issue tracker connection, team conventions |
| Project | `<repo>/CLAUDE.md` | each project repo | commands, structure, per-repo conventions (see `examples/example-service/`) |

Rule of thumb: a rule belongs at the highest layer where it is true everywhere
below it. Personal style and git discipline are global; the task workflow is
workspace; build commands are project.

## Seeding a new machine

```bash
# Personal global rules (skip if you already have one; then merge by hand)
cp -n global/CLAUDE.md.example ~/.claude/CLAUDE.md

# Plugins and hooks: merge the relevant parts into ~/.claude/settings.json
# (do not overwrite an existing file; settings.json holds unrelated state)
cat global/settings.json.example
```

`/workspace-setup` offers this step automatically when `~/.claude/CLAUDE.md`
is missing.

## Plugins

Enable via `/plugin` in Claude Code or the `enabledPlugins` map in
`~/.claude/settings.json` (see `settings.json.example`). Workflow-relevant:

- **Issue tracker connection**: the Atlassian plugin for Jira, a Linear MCP
  server, or nothing if you use `gh` for GitHub Issues. Authenticate via
  `/mcp` after enabling.
- **superpowers**: process skills (brainstorming, TDD, debugging) the
  workflow's specialist agents pair well with.
- **code-review**: PR review skill used alongside `/finish-task`.
- Anything else is personal preference; plugins are orthogonal to the
  workflow.

## User-level skills

`~/.claude/skills/` holds skills that follow the developer, not a repo. The
notable one for this workflow: a **validation-gate pipeline** skill/tool (a
`no-mistakes`-style runner) that `/finish-task` invokes per repo. The
workspace defines the contract for it (`.no-mistakes.yaml` +
`scripts/gate.sh`, see `examples/example-service/`), but the runner itself is
user tooling; without one, `/finish-task` falls back to `task-prs`.

## Hooks

`settings.json.example` shows a `SessionStart` hook slot: a command whose
output is injected as context at session start (repo status, open PRs, a CLI
wrapper announcing itself). Optional; delete the block if unused.
