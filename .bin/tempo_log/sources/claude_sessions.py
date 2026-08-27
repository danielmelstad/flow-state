"""Turn Claude Code session jsonl records into RawEvents."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tempo_log.models import RawEvent

_PATH_RE = re.compile(r"(?<![\w-])(/[\w.@~+-]+(?:/[\w.@~+-]+)+)")
_PATH_KEYS = ("file_path", "path", "notebook_path", "cwd")


def _parse_ts(text: str) -> datetime:
    ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _collect_paths(value: object, out: list[str]) -> None:
    if isinstance(value, str):
        out.extend(_PATH_RE.findall(value))
    elif isinstance(value, dict):
        for k, v in value.items():
            if k in _PATH_KEYS and isinstance(v, str):
                out.append(v)
            else:
                _collect_paths(v, out)
    elif isinstance(value, list):
        for v in value:
            _collect_paths(v, out)


def parse_record(obj: dict) -> RawEvent | None:
    if obj.get("type") not in ("user", "assistant"):
        return None
    raw_ts = obj.get("timestamp")
    if not isinstance(raw_ts, str):
        return None
    message = obj.get("message")
    if not isinstance(message, dict):
        message = {}
    content = message.get("content")
    text = ""
    paths: list[str] = []
    if obj["type"] == "user" and isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                _collect_paths(block.get("input"), paths)
            elif block.get("type") == "text" and obj["type"] == "user":
                text += str(block.get("text", ""))
    return RawEvent(
        ts=_parse_ts(raw_ts),
        source="claude",
        session=obj.get("sessionId"),
        cwd=obj.get("cwd"),
        branch=obj.get("gitBranch"),
        paths=tuple(dict.fromkeys(paths)),
        text=text,
    )


def read_events(projects_dir: Path, start: datetime, end: datetime) -> list[RawEvent]:
    events: list[RawEvent] = []
    if not projects_dir.is_dir():
        return events
    for path in sorted(projects_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                try:
                    ev = parse_record(obj)
                except (ValueError, TypeError, AttributeError, KeyError):
                    continue
                if ev is not None and start <= ev.ts < end:
                    events.append(ev)
    events.sort(key=lambda e: e.ts)
    return events
