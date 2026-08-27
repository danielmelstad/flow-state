"""Dataclasses shared across tempo_log modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

Mode = str  # "actual" | "pack" | "fit"
MODES = ("actual", "pack", "fit")


@dataclass(frozen=True)
class RawEvent:
    """An observation from a source before ticket attribution."""

    ts: datetime  # timezone-aware UTC
    source: str  # "claude" | "git"
    session: str | None  # Claude sessionId, or None for git
    cwd: str | None
    branch: str | None
    paths: tuple[str, ...]  # file paths mentioned by tool calls
    text: str  # user message text or commit subject


@dataclass(frozen=True)
class Event:
    ts: datetime
    ticket: str | None
    source: str
    session: str | None


@dataclass
class Block:
    day: date  # local date in the configured timezone
    ticket: str | None
    start: datetime  # UTC
    end: datetime  # UTC
    events: int
    sources: dict[str, int] = field(default_factory=dict)  # source -> event count


@dataclass
class Entry:
    ticket: str  # "" means unattributed
    seconds: int
    start: time | None  # local time; None until placed (pack/fit)
    description: str
    sources: list[str]
    first_activity: datetime  # UTC
    original_seconds: int | None = None  # set by fit when scaled


@dataclass(frozen=True)
class Slot:
    """An occupied interval on the local day (existing Tempo worklog)."""

    start: time
    end: time
    ticket: str


@dataclass
class Draft:
    day: date
    mode: Mode
    window: str | None
    timezone: str
    entries: list[Entry]
    occupied: list[Slot]
    warnings: list[str]


@dataclass(frozen=True)
class Window:
    start: time
    end: time

    @classmethod
    def parse(cls, text: str) -> "Window":
        try:
            a, b = text.split("-")
            start = time.fromisoformat(a.strip())
            end = time.fromisoformat(b.strip())
        except ValueError as exc:
            raise ValueError(f"window must look like 08:00-16:00, got {text!r}") from exc
        if end <= start:
            raise ValueError(f"window end must be after start, got {text!r}")
        return cls(start, end)

    @property
    def seconds(self) -> int:
        return _secs(self.end) - _secs(self.start)


def _secs(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def time_from_secs(s: int) -> time:
    """Seconds after midnight to time; values >= 86400 clamp to 23:59:59."""
    s = min(s, 86399)
    return time(s // 3600, (s % 3600) // 60, s % 60)
