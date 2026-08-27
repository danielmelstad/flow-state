"""Load and validate .tempo-log.toml."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tempo_log.models import MODES, Window


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class TempoConfig:
    base_url: str
    token_env: str


@dataclass(frozen=True)
class JiraConfig:
    site: str
    email: str
    token_env: str
    account_id: str


@dataclass(frozen=True)
class RulesConfig:
    ticket_pattern: re.Pattern
    admin_ticket: str
    idle_gap_minutes: int
    rounding_minutes: int


@dataclass(frozen=True)
class PlacementConfig:
    mode: str
    window: Window
    timezone: ZoneInfo


@dataclass(frozen=True)
class SourcesConfig:
    claude_projects_dir: Path
    repos: str | list[Path]
    git_authors: list[str]


@dataclass(frozen=True)
class Config:
    hub_root: Path
    tempo: TempoConfig
    jira: JiraConfig
    rules: RulesConfig
    placement: PlacementConfig
    sources: SourcesConfig

    @property
    def state_dir(self) -> Path:
        return self.hub_root / ".tempo-log"


def encode_claude_project_dir(hub_root: Path) -> Path:
    """Claude Code stores session logs under ~/.claude/projects/<path with / and . as ->."""
    encoded = re.sub(r"[/.]", "-", str(hub_root.resolve()))
    return Path(os.path.expanduser("~")) / ".claude" / "projects" / encoded


def _require(table: dict, section: str, key: str) -> object:
    if key not in table:
        raise ConfigError(f"missing required key {section}.{key}")
    return table[key]


def _int(table: dict, section: str, key: str, default: int) -> int:
    value = table.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{section}.{key} must be a positive integer")
    return value


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(
            f"config not found at {path}; copy .tempo-log.toml.example to .tempo-log.toml and fill it in"
        )
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    hub_root = path.parent.resolve()

    t = data.get("tempo", {})
    tempo = TempoConfig(
        base_url=str(_require(t, "tempo", "base_url")).rstrip("/"),
        token_env=str(t.get("token_env", "TEMPO_API_TOKEN")),
    )

    j = data.get("jira", {})
    jira = JiraConfig(
        site=str(_require(j, "jira", "site")).rstrip("/"),
        email=str(_require(j, "jira", "email")),
        token_env=str(j.get("token_env", "JIRA_API_TOKEN")),
        account_id=str(_require(j, "jira", "account_id")),
    )

    r = data.get("rules", {})
    pattern_text = str(r.get("ticket_pattern", "[A-Z][A-Z0-9]+-[0-9]+"))
    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        raise ConfigError(f"rules.ticket_pattern is not a valid regex: {exc}") from exc
    rules = RulesConfig(
        ticket_pattern=pattern,
        admin_ticket=str(r.get("admin_ticket", "")),
        idle_gap_minutes=_int(r, "rules", "idle_gap_minutes", 15),
        rounding_minutes=_int(r, "rules", "rounding_minutes", 30),
    )

    p = data.get("placement", {})
    mode = str(p.get("mode", "actual"))
    if mode not in MODES:
        raise ConfigError(f"placement.mode must be one of {', '.join(MODES)}, got {mode!r}")
    try:
        window = Window.parse(str(p.get("window", "08:00-16:00")))
    except ValueError as exc:
        raise ConfigError(f"placement.window: {exc}") from exc
    tz_name = str(p.get("timezone", "UTC"))
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"placement.timezone unknown: {tz_name}") from exc
    placement = PlacementConfig(mode=mode, window=window, timezone=tz)

    s = data.get("sources", {})
    cpd = str(s.get("claude_projects_dir", "")) or ""
    claude_dir = Path(os.path.expanduser(cpd)) if cpd else encode_claude_project_dir(hub_root)
    repos_raw = s.get("repos", "auto")
    if repos_raw == "auto":
        repos: str | list[Path] = "auto"
    elif isinstance(repos_raw, list) and all(isinstance(x, str) for x in repos_raw):
        repos = [hub_root / x for x in repos_raw]
    else:
        raise ConfigError('sources.repos must be "auto" or a list of paths relative to the hub')
    authors = s.get("git_authors", [])
    if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
        raise ConfigError("sources.git_authors must be a list of email strings")
    sources = SourcesConfig(
        claude_projects_dir=claude_dir,
        repos=repos,
        git_authors=list(authors) or [jira.email],
    )

    return Config(hub_root, tempo, jira, rules, placement, sources)
