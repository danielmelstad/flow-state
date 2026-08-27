"""Ticket-prefixed commits as activity events."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tempo_log.models import RawEvent

_SEP = "\x1f"


def discover_repos(hub_root: Path) -> list[Path]:
    """Git repos directly under the hub plus every .worktrees/<ticket>/<repo>."""
    found: list[Path] = []
    for child in sorted(hub_root.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and (child / ".git").exists():
            found.append(child)
    worktrees = hub_root / ".worktrees"
    if worktrees.is_dir():
        for ticket_dir in sorted(worktrees.iterdir()):
            if not ticket_dir.is_dir():
                continue
            for repo in sorted(ticket_dir.iterdir()):
                if repo.is_dir() and (repo / ".git").exists():
                    found.append(repo)
    return found


def read_events(repos: list[Path], authors: list[str], start: datetime, end: datetime) -> list[RawEvent]:
    events: list[RawEvent] = []
    wanted = {a.lower() for a in authors}
    for repo in repos:
        if not (repo / ".git").exists():
            continue
        cmd = [
            "git", "-C", str(repo), "log", "--all", "--no-merges",
            f"--since={start.isoformat()}", f"--until={end.isoformat()}",
            f"--format=%aI{_SEP}%ae{_SEP}%s",
        ]
        try:
            out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        for line in out.splitlines():
            parts = line.split(_SEP, 2)
            if len(parts) != 3:
                continue
            when, email, subject = parts
            if email.lower() not in wanted:
                continue
            ts = datetime.fromisoformat(when).astimezone(timezone.utc)
            if not (start <= ts < end):
                continue
            events.append(RawEvent(ts=ts, source="git", session=None, cwd=str(repo),
                                   branch=None, paths=(), text=subject))
    events.sort(key=lambda e: e.ts)
    return events
