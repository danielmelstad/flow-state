---
name: log-time
description: Use when the user asks to log time, fill Tempo, record hours, or invokes /log-time. Drives the tempo-log CLI (scan, review, post) for a date or range; never posts without an explicit instruction.
---

# /log-time [DATE | FROM..TO | today | yesterday]

Log Tempo time derived from Claude Code sessions and ticket-prefixed git
commits, reviewed by the user before posting. All logic lives in
`.bin/tempo-log`; this skill only drives it.

## Preconditions

- `.tempo-log.toml` exists at the hub root (else point the user at
  `.tempo-log.toml.example`; `tempo-log resolve me` prints the `account_id`
  line to paste into the config).
- `TEMPO_API_TOKEN` and `JIRA_API_TOKEN` are exported in the user's shell.
  Never read, echo, or search for token values. If a command exits 4, tell the
  user which variable is missing and stop. Exit 2 is a usage error: show the
  CLI message.

## Flow

1. Default date: `yesterday`, or `today` if invoked after the configured
   window end; if the user says "today" or gives dates, use those.
2. Run `tempo-log scan <dates>` (add `--mode actual|pack|fit` only if the user
   asks for a different placement than their config default).
3. Present each day's table verbatim, then call out explicitly:
   - entries marked `UNATTRIBUTED` (must be assigned or deleted),
   - `*` scaled entries (fit mode) with their original durations,
   - `<` marked rows (actual mode: nudged forward from their real start),
   - any `WARNING:` lines, including `nudged:` and `crosses midnight:`
     (informational, actual mode) and `window_overflow` (pack/fit only).
   A freshly scanned or shown draft never carries an `overlap:` warning: scan
   resolves collisions itself, by nudging in actual mode and by sequential
   placement in pack/fit. `overlap:` only appears if a later `post --keep-start`
   finds one, and in that case the post fails (see step 5).
   Suggest the configured `admin_ticket` for unattributed time only if one is set.
4. Apply the user's corrections by editing `.tempo-log/drafts/<date>.toml`
   (ticket, seconds, description, start in actual mode; delete or add
   `[[entries]]`). In actual mode, if you change `start` on an entry that has
   `nudged_from`, delete its `nudged_from` line so post keeps your value. Run
   `tempo-log show <date>` and present the result.
5. Post only after the user explicitly says to post. Run
   `tempo-log post <date>`; on "already has posted worklogs" ask whether to
   `--replace`. `post` re-runs placement from the draft: in actual mode it
   rewinds every entry to its real start and re-nudges; in pack/fit it
   re-places entries in the window; both run against freshly fetched occupied
   slots. `--keep-start` keeps the draft's start times exactly as written, in
   any mode, and refuses to post if any entry then overlaps an occupied slot
   or another entry. Report the posted ids and totals from the CLI output.
6. On any non-zero exit, show the CLI's stderr verbatim and stop. Do not retry
   posts. `tempo-log undo <date>` reverts what the ledger recorded.

## Rules

- No time logic in this skill; if the numbers look wrong, fix the CLI, not the draft.
- Never edit `[[occupied]]` blocks; they mirror Tempo.
- `yesterday`/`today` follow `placement.timezone` from the user's config, not
  UTC; near midnight, confirm the intended date or pass an explicit one.
