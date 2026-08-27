"""The reviewable per-day draft, stored as TOML."""

from __future__ import annotations

import json
import tomllib
from datetime import date, datetime, time, timezone
from pathlib import Path

from tempo_log.models import MODES, Draft, Entry, Slot


class DraftError(Exception):
    pass


def _q(value: str) -> str:
    # JSON string escaping is a valid TOML basic string for our content, except
    # that TOML rejects a literal U+007F (DEL); json.dumps leaves it unescaped.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007F")


def _t(t: time) -> str:
    return t.strftime("%H:%M")


def dumps(draft: Draft) -> str:
    lines = [
        "# tempo-log draft. Edit ticket/seconds/description (and start in actual mode),",
        "# delete entries you do not want, then run: tempo-log post <date>",
        f"date = {_q(draft.day.isoformat())}",
        f"mode = {_q(draft.mode)}",
    ]
    if draft.window:
        lines.append(f"window = {_q(draft.window)}")
    lines.append(f"timezone = {_q(draft.timezone)}")
    lines.append("warnings = [" + ", ".join(_q(w) for w in draft.warnings) + "]")
    for slot in draft.occupied:
        lines += ["", "[[occupied]]  # already in Tempo, read-only",
                  f"start = {_q(_t(slot.start))}", f"end = {_q(_t(slot.end))}", f"ticket = {_q(slot.ticket)}"]
    for e in draft.entries:
        lines += ["", "[[entries]]"]
        lines.append(f"ticket = {_q(e.ticket)}" + ("  # UNATTRIBUTED: fill in or delete" if not e.ticket else ""))
        lines.append(f"seconds = {e.seconds}")
        if e.start is not None:
            lines.append(f"start = {_q(_t(e.start))}")
        lines.append(f"description = {_q(e.description)}")
        lines.append("sources = [" + ", ".join(_q(s) for s in e.sources) + "]")
        if e.original_seconds is not None:
            lines.append(f"original_seconds = {e.original_seconds}")
        lines.append(f"first_activity = {_q(e.first_activity.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))}")
    return "\n".join(lines) + "\n"


def _time(value: object, where: str) -> time:
    try:
        return time.fromisoformat(str(value))
    except ValueError as exc:
        raise DraftError(f"{where}: bad time {value!r}") from exc


def loads(text: str) -> Draft:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise DraftError(f"draft is not valid TOML: {exc}") from exc
    try:
        day = date.fromisoformat(str(data["date"]))
    except (KeyError, ValueError) as exc:
        raise DraftError("draft needs a valid ISO 'date'") from exc
    mode = str(data.get("mode", "actual"))
    if mode not in MODES:
        raise DraftError(f"mode must be one of {', '.join(MODES)}")
    raw_entries = data.get("entries", [])
    if not isinstance(raw_entries, list) or not all(isinstance(r, dict) for r in raw_entries):
        raise DraftError("entries must be an array of tables")
    entries: list[Entry] = []
    for i, raw in enumerate(raw_entries, 1):
        where = f"entries[{i}]"
        try:
            seconds = int(raw.get("seconds", 0))
        except (TypeError, ValueError) as exc:
            raise DraftError(f"{where}: seconds must be an integer") from exc
        fa_raw = raw.get("first_activity")
        if fa_raw:
            first = datetime.fromisoformat(str(fa_raw).replace("Z", "+00:00"))
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            first = first.astimezone(timezone.utc)
        else:
            first = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
        start = _time(raw["start"], where) if raw.get("start") else None
        entries.append(Entry(
            ticket=str(raw.get("ticket", "")).strip(), seconds=seconds, start=start,
            description=str(raw.get("description", "")), sources=[str(s) for s in raw.get("sources", [])],
            first_activity=first,
            original_seconds=int(raw["original_seconds"]) if raw.get("original_seconds") is not None else None,
        ))
    raw_occupied = data.get("occupied", [])
    if not isinstance(raw_occupied, list) or not all(isinstance(o, dict) for o in raw_occupied):
        raise DraftError("occupied must be an array of tables")
    occupied = [Slot(_time(o["start"], "occupied"), _time(o["end"], "occupied"), str(o.get("ticket", "")))
                for o in raw_occupied]
    return Draft(day=day, mode=mode, window=data.get("window"), timezone=str(data.get("timezone", "UTC")),
                 entries=entries, occupied=occupied, warnings=[str(w) for w in data.get("warnings", [])])


def validate_for_post(draft: Draft, rounding_minutes: int) -> list[str]:
    problems: list[str] = []
    warnings: list[str] = []
    if not draft.entries:
        problems.append("draft has no entries")
    for e in draft.entries:
        label = e.ticket or "(unattributed)"
        if not e.ticket:
            problems.append("an entry is still unattributed (ticket = \"\"); assign a ticket or delete it")
        if e.seconds <= 0:
            problems.append(f"{label}: seconds must be positive")
        elif e.seconds % (rounding_minutes * 60):
            warnings.append(f"{label}: {e.seconds} seconds is not a multiple of {rounding_minutes} minutes")
        if e.start is None:
            problems.append(f"{label}: entry has no start time; run scan again or add start")
    problems += [w for w in draft.warnings if w.startswith("overlap")]
    if problems:
        raise DraftError("; ".join(problems))
    return warnings


def draft_path(state_dir: Path, day: date) -> Path:
    return state_dir / "drafts" / f"{day.isoformat()}.toml"


def fmt_duration(seconds: int) -> str:
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def render_table(draft: Draft) -> str:
    head = f"{draft.day}  mode={draft.mode}" + (f"  window={draft.window}" if draft.window else "") + f"  tz={draft.timezone}"
    rows = [head, ""]
    if draft.occupied:
        rows.append("Already in Tempo:")
        for s in draft.occupied:
            rows.append(f"  {_t(s.start)}-{_t(s.end)}  {s.ticket}")
        rows.append("")
    rows.append(f"{'start':<6} {'dur':<7} {'ticket':<12} {'description':<48} sources")
    for e in draft.entries:
        ticket = e.ticket or "UNATTRIBUTED"
        start = _t(e.start) if e.start else "--:--"
        dur = fmt_duration(e.seconds) + ("*" if e.original_seconds is not None else "")
        rows.append(f"{start:<6} {dur:<7} {ticket:<12} {e.description[:48]:<48} {', '.join(e.sources)}")
    total = sum(e.seconds for e in draft.entries)
    rows.append("")
    rows.append(f"total {fmt_duration(total)}" + ("  (* scaled by fit)" if any(e.original_seconds is not None for e in draft.entries) else ""))
    for w in draft.warnings:
        rows.append(f"WARNING: {w}")
    return "\n".join(rows)
