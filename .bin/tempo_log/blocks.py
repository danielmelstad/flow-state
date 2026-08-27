"""Cluster events into blocks per local day and ticket; derive entry candidates."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from tempo_log.models import Block, Entry, Event


def round_seconds(seconds: int, rounding_minutes: int) -> int:
    unit = rounding_minutes * 60
    if seconds <= 0:
        return 0
    rounded = ((seconds + unit // 2) // unit) * unit
    return max(rounded, unit)


def cluster(events: list[Event], tz: ZoneInfo, idle_gap_minutes: int) -> list[Block]:
    gap = timedelta(minutes=idle_gap_minutes)
    by_key: dict[tuple[date, str | None], list[Event]] = defaultdict(list)
    for e in sorted(events, key=lambda e: e.ts):
        by_key[(e.ts.astimezone(tz).date(), e.ticket)].append(e)

    blocks: list[Block] = []
    for (day, ticket), evs in by_key.items():
        current: Block | None = None
        for e in evs:
            if current is None or e.ts - current.end > gap:
                current = Block(day=day, ticket=ticket, start=e.ts, end=e.ts, events=0)
                blocks.append(current)
            current.end = e.ts
            current.events += 1
            current.sources[e.source] = current.sources.get(e.source, 0) + 1
    blocks.sort(key=lambda b: (b.start, b.ticket or ""))
    return blocks


def _source_labels(sources: dict[str, int], block_count: int) -> list[str]:
    labels = []
    if block_count and sources.get("claude"):
        labels.append(f"claude:{block_count} blocks")
    if sources.get("git"):
        labels.append(f"git:{sources['git']} commits")
    return labels


def entries_for_day(blocks: list[Block], day: date, mode: str, rounding_minutes: int, tz: ZoneInfo) -> list[Entry]:
    todays = [b for b in blocks if b.day == day]
    entries: list[Entry] = []
    if mode == "actual":
        for b in todays:
            seconds = round_seconds(int((b.end - b.start).total_seconds()), rounding_minutes)
            local_start = b.start.astimezone(tz).time().replace(second=0, microsecond=0)
            claude_blocks = 1 if b.sources.get("claude") else 0
            entries.append(Entry(ticket=b.ticket or "", seconds=seconds, start=local_start,
                                 description="", sources=_source_labels(b.sources, claude_blocks),
                                 first_activity=b.start))
        return entries

    grouped: dict[str | None, list[Block]] = defaultdict(list)
    for b in todays:
        grouped[b.ticket].append(b)
    for ticket, group in grouped.items():
        total = sum(max(1, int((b.end - b.start).total_seconds())) for b in group)
        sources: dict[str, int] = defaultdict(int)
        for b in group:
            for k, v in b.sources.items():
                sources[k] += v
        claude_blocks = sum(1 for b in group if b.sources.get("claude"))
        entries.append(Entry(ticket=ticket or "", seconds=round_seconds(total, rounding_minutes),
                             start=None, description="",
                             sources=_source_labels(dict(sources), claude_blocks),
                             first_activity=min(b.start for b in group)))
    entries.sort(key=lambda e: e.first_activity)
    return entries
