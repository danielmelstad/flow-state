"""Persistent record of posted worklogs and cached Jira issue ids."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path


class Ledger:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self._data = data
        self._data.setdefault("posted", {})
        self._data.setdefault("issues", {})

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(f"ledger {path} is not valid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError(f"ledger {path} must contain a JSON object")
        else:
            data = {}
        return cls(path, data)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, self.path)

    def posted(self, day: date) -> list[dict]:
        return list(self._data["posted"].get(day.isoformat(), []))

    def record(self, day: date, worklog_id: int, ticket: str, seconds: int, start: str) -> None:
        self._data["posted"].setdefault(day.isoformat(), []).append(
            {"worklog_id": worklog_id, "ticket": ticket, "seconds": seconds, "start": start}
        )
        self.save()

    def clear(self, day: date) -> None:
        self._data["posted"].pop(day.isoformat(), None)
        self.save()

    def issue_id(self, key: str) -> int | None:
        entry = self._data["issues"].get(key)
        return int(entry["id"]) if entry else None

    def issue_summary(self, key: str) -> str | None:
        entry = self._data["issues"].get(key)
        return entry.get("summary") if entry else None

    def remember_issue(self, key: str, issue_id: int, summary: str) -> None:
        self._data["issues"][key] = {"id": issue_id, "summary": summary}
        self.save()
