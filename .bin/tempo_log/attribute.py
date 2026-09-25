"""Assign a ticket to each raw event; first matching rule wins, then session stickiness."""

from __future__ import annotations

import re

from tempo_log.models import Event, RawEvent


def _worktree_ticket(path: str, pattern: re.Pattern) -> str | None:
    marker = "/.worktrees/"
    idx = path.find(marker)
    if idx == -1:
        return None
    segment = path[idx + len(marker):].split("/", 1)[0]
    return segment if pattern.fullmatch(segment) else None


def ticket_from_raw(raw: RawEvent, pattern: re.Pattern) -> str | None:
    for candidate in ((raw.cwd,) if raw.cwd else ()) + raw.paths:
        ticket = _worktree_ticket(candidate, pattern)
        if ticket:
            return ticket
    if raw.branch:
        m = pattern.search(raw.branch)
        if m:
            return m.group(0)
    if raw.source == "git":
        m = pattern.match(raw.text)
        if m and raw.text[m.end():m.end() + 1] == ":":
            return m.group(0)
        return None
    m = pattern.search(raw.text)
    return m.group(0) if m else None


def attribute(raw_events: list[RawEvent], pattern: re.Pattern) -> list[Event]:
    ordered = sorted(raw_events, key=lambda e: e.ts)
    last_by_session: dict[str, str] = {}
    out: list[Event] = []
    for raw in ordered:
        ticket = ticket_from_raw(raw, pattern)
        if raw.session is not None:
            if ticket:
                last_by_session[raw.session] = ticket
            else:
                ticket = last_by_session.get(raw.session)
        out.append(Event(ts=raw.ts, ticket=ticket, source=raw.source, session=raw.session))
    return out
