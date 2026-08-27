"""tempo-log command line: scan, show, post, undo, resolve."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, TextIO

from tempo_log import __version__, attribute, blocks, place
from tempo_log.config import Config, ConfigError, load_config
from tempo_log.draft import DraftError, Draft, draft_path, dumps, loads, render_table, validate_for_post
from tempo_log.http import HttpError, TokenError, Transport, UrllibTransport
from tempo_log.jira import JiraClient
from tempo_log.ledger import Ledger
from tempo_log.models import MODES, Entry, Slot
from tempo_log.sources import claude_sessions, git_commits
from tempo_log.tempo import TempoClient, slots_from_worklogs

HUB_ROOT = Path(__file__).resolve().parents[2]


def parse_days(text: str, today: date) -> list[date]:
    if text == "today":
        return [today]
    if text == "yesterday":
        return [today - timedelta(days=1)]
    if ".." in text:
        a, b = text.split("..", 1)
        start, end = date.fromisoformat(a), date.fromisoformat(b)
        if end < start:
            raise ValueError("range end is before start")
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return [date.fromisoformat(text)]


def _day_bounds(day: date, cfg: Config) -> tuple[datetime, datetime]:
    # Compute the end bound from midnight of the next local day, not start + 24h:
    # on a DST transition day the local day is 23 or 25 hours long, and start +
    # timedelta(days=1) would cut off or duplicate an hour of events.
    tz = cfg.placement.timezone
    start = datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz).astimezone(timezone.utc)
    return start, end


def _repos(cfg: Config) -> list[Path]:
    return git_commits.discover_repos(cfg.hub_root) if cfg.sources.repos == "auto" else list(cfg.sources.repos)


def build_draft(cfg: Config, day: date, mode: str, occupied: list[Slot],
                describe: Callable[[str], str]) -> Draft:
    start, end = _day_bounds(day, cfg)
    raw = claude_sessions.read_events(cfg.sources.claude_projects_dir, start, end)
    raw += git_commits.read_events(_repos(cfg), cfg.sources.git_authors, start, end)
    events = attribute.attribute(raw, cfg.rules.ticket_pattern)
    clustered = blocks.cluster(events, cfg.placement.timezone, cfg.rules.idle_gap_minutes)
    entries = blocks.entries_for_day(clustered, day, mode, cfg.rules.rounding_minutes, cfg.placement.timezone)
    for e in entries:
        e.description = describe(e.ticket) if e.ticket else ""
    if mode == "actual":
        warnings = place.place_actual(entries, occupied)
        window = None
    else:
        warnings = place.place_window(entries, occupied, cfg.placement.window, mode, cfg.rules.rounding_minutes)
        window = f"{cfg.placement.window.start:%H:%M}-{cfg.placement.window.end:%H:%M}"
    return Draft(day=day, mode=mode, window=window, timezone=str(cfg.placement.timezone),
                 entries=entries, occupied=occupied, warnings=warnings)


class Services:
    """Lazily built clients so offline commands never need tokens."""

    def __init__(self, cfg: Config, transport: Transport, env: dict[str, str], ledger: Ledger):
        self.cfg, self.transport, self.env, self.ledger = cfg, transport, env, ledger
        self._tempo: TempoClient | None = None
        self._jira: JiraClient | None = None

    def _token(self, name: str) -> str:
        value = self.env.get(name, "")
        if not value:
            raise TokenError(f"environment variable {name} is not set; export it before running tempo-log")
        return value

    @property
    def tempo(self) -> TempoClient:
        if self._tempo is None:
            self._tempo = TempoClient(self.cfg.tempo.base_url, self._token(self.cfg.tempo.token_env), self.transport)
        return self._tempo

    @property
    def jira(self) -> JiraClient:
        if self._jira is None:
            self._jira = JiraClient(self.cfg.jira.site, self.cfg.jira.email, self._token(self.cfg.jira.token_env), self.transport)
        return self._jira

    def issue(self, key: str) -> tuple[int, str]:
        cached = self.ledger.issue_id(key)
        if cached is not None:
            return cached, self.ledger.issue_summary(key) or ""
        issue_id, summary = self.jira.issue(key)
        self.ledger.remember_issue(key, issue_id, summary)
        return issue_id, summary

    def describe(self, key: str) -> str:
        try:
            _, summary = self.issue(key)
        except HttpError as exc:
            if exc.status == 404:
                return key
            raise
        return f"{key}: {summary}" if summary else key

    def occupied(self, day: date) -> list[Slot]:
        results = self.tempo.worklogs_for_user(self.cfg.jira.account_id, day)
        return slots_from_worklogs(results, self.cfg.placement.timezone, day)


def cmd_scan(args, cfg: Config, svc: Services, out: TextIO) -> int:
    mode = args.mode or cfg.placement.mode
    for day in args.days:
        occupied = [] if args.offline else svc.occupied(day)
        describe = (lambda k: (f"{k}: {svc.ledger.issue_summary(k)}" if svc.ledger.issue_summary(k) else k)) if args.offline else svc.describe
        draft = build_draft(cfg, day, mode, occupied, describe)
        path = draft_path(cfg.state_dir, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(draft))
        out.write(render_table(draft) + f"\n\ndraft: {path}\n\n")
    return 0


def cmd_show(args, cfg: Config, svc: Services, out: TextIO) -> int:
    for day in args.days:
        path = draft_path(cfg.state_dir, day)
        if not path.is_file():
            raise DraftError(f"no draft for {day}; run: tempo-log scan {day}")
        out.write(render_table(loads(path.read_text())) + "\n\n")
    return 0


def _worklog_payload(cfg: Config, day: date, e: Entry, issue_id: int) -> dict:
    if e.start is None:
        # validate_for_post should have caught this already; this is a defensive
        # fallback, not the primary check.
        raise DraftError(f"{e.ticket or '(unattributed)'}: entry has no start time; run scan again or add start")
    return {
        "authorAccountId": cfg.jira.account_id,
        "issueId": issue_id,
        "startDate": day.isoformat(),
        "startTime": e.start.strftime("%H:%M:%S"),
        "timeSpentSeconds": e.seconds,
        "description": e.description or e.ticket,
    }


def cmd_post(args, cfg: Config, svc: Services, out: TextIO) -> int:
    for day in args.days:
        path = draft_path(cfg.state_dir, day)
        if not path.is_file():
            raise DraftError(f"no draft for {day}; run: tempo-log scan {day}")
        draft = loads(path.read_text())
        if draft.day != day:
            raise DraftError(f"draft {path} is for {draft.day}, not {day}")

        occupied = svc.occupied(day)
        draft.occupied = occupied
        if draft.mode == "actual":
            if args.keep_start:
                draft.warnings = place.check_actual(draft.entries, occupied)
            else:
                for e in draft.entries:
                    e.nudged_from = None
                draft.warnings = place.place_actual(draft.entries, occupied)
        elif not args.keep_start:
            draft.entries.sort(key=lambda e: e.first_activity)
            draft.warnings = place.place_window(draft.entries, occupied, cfg.placement.window, draft.mode, cfg.rules.rounding_minutes)
        warnings = validate_for_post(draft, cfg.rules.rounding_minutes)
        for w in warnings + [w for w in draft.warnings if w == "window_overflow"]:
            out.write(f"warning: {w}\n")

        previous = svc.ledger.posted(day)
        if previous and not args.replace:
            raise DraftError(f"{day} already has {len(previous)} posted worklog(s) in the ledger; use --replace to delete and re-post, or undo first")

        payloads = [(e, _worklog_payload(cfg, day, e, svc.issue(e.ticket)[0])) for e in draft.entries]
        if args.dry_run:
            out.write(f"dry run for {day}: would post {len(payloads)} worklog(s)\n")
            for _, p in payloads:
                out.write(f"  POST /4/worklogs {p}\n")
            if previous:
                out.write(f"  and delete {len(previous)} previously posted worklog(s) first\n")
            continue

        if previous:
            for rec in previous:
                _delete_and_forget(svc, day, int(rec["worklog_id"]))
        for e, p in payloads:
            worklog_id = svc.tempo.create_worklog(p)
            svc.ledger.record(day, worklog_id, e.ticket, e.seconds, p["startTime"][:5])
            out.write(f"posted {e.ticket} {p['startTime'][:5]} {e.seconds // 60} min -> tempo worklog {worklog_id}\n")
        path.write_text(dumps(draft))
        out.write(f"{day}: {len(payloads)} worklog(s) posted, total {sum(e.seconds for e in draft.entries) // 60} min\n")
    return 0


def _delete_and_forget(svc: Services, day: date, worklog_id: int) -> None:
    """Delete a worklog and remove its ledger record; a 404 means it is already
    gone (a previous run deleted it before a partial failure), so treat that as
    success rather than aborting with earlier records already deleted and later
    ones still live and unrecorded-as-deleted."""
    try:
        svc.tempo.delete_worklog(worklog_id)
    except HttpError as exc:
        if exc.status != 404:
            raise
    svc.ledger.forget(day, worklog_id)


def cmd_undo(args, cfg: Config, svc: Services, out: TextIO) -> int:
    for day in args.days:
        records = svc.ledger.posted(day)
        if not records:
            out.write(f"{day}: nothing recorded in the ledger\n")
            continue
        for rec in records:
            _delete_and_forget(svc, day, int(rec["worklog_id"]))
            out.write(f"deleted tempo worklog {rec['worklog_id']} ({rec['ticket']}, {rec['start']})\n")
    return 0


def cmd_resolve(args, cfg: Config, svc: Services, out: TextIO) -> int:
    if args.what == "me":
        account_id, name = svc.jira.myself()
        out.write(f"# {name}\naccount_id = \"{account_id}\"\n")
        return 0
    issue_id, summary = svc.issue(args.what)
    out.write(f"{args.what} -> issue id {issue_id}: {summary}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tempo-log", description="Derive time from activity, review, post to Tempo.")
    p.add_argument("--config", type=Path, default=HUB_ROOT / ".tempo-log.toml")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    # "days" is kept as the raw string here and resolved to actual dates in main,
    # after the config (and its timezone) is loaded, so "today"/"yesterday" are
    # computed in the configured timezone rather than UTC.

    s = sub.add_parser("scan", help="build a reviewable draft for a day or range")
    s.add_argument("days", metavar="DATE|FROM..TO|today|yesterday")
    s.add_argument("--mode", choices=MODES)
    s.add_argument("--offline", action="store_true", help="skip Tempo/Jira lookups")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("show", help="print a draft")
    s.add_argument("days")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("post", help="validate a draft and post it to Tempo")
    s.add_argument("days")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--replace", action="store_true", help="delete previously posted worklogs for the day first")
    s.add_argument("--keep-start", action="store_true",
                    help="keep start times from the draft (actual: refuse on overlap; pack/fit: skip re-placement)")
    s.set_defaults(func=cmd_post)

    s = sub.add_parser("undo", help="delete worklogs the ledger recorded for a day")
    s.add_argument("days")
    s.set_defaults(func=cmd_undo)

    s = sub.add_parser("resolve", help="'me' prints your account id; a key prints its issue id")
    s.add_argument("what")
    s.set_defaults(func=cmd_resolve)
    return p


def main(argv: list[str] | None = None, *, transport: Transport | None = None,
         env: dict[str, str] | None = None, out: TextIO | None = None, err: TextIO | None = None) -> int:
    # out/err default to sys.stdout/sys.stderr looked up at call time (not at def time), so
    # capsys and similar stream-swapping test fixtures see everything written here.
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        # Resolve "today"/"yesterday"/ranges only once the configured timezone is
        # known, so they mean the user's local day rather than the UTC day.
        if args.command != "resolve":
            args.days = parse_days(args.days, datetime.now(cfg.placement.timezone).date())
        ledger = Ledger.load(cfg.state_dir / "ledger.json")
        svc = Services(cfg, transport or UrllibTransport(), dict(os.environ) if env is None else env, ledger)
        return args.func(args, cfg, svc, out)
    except TokenError as exc:
        err.write(f"error: {exc}\n")
        return 2
    except (ConfigError, DraftError, place.PlacementError, ValueError) as exc:
        err.write(f"error: {exc}\n")
        return 1
    except HttpError as exc:
        err.write(f"error: {exc}\n")
        return 3
