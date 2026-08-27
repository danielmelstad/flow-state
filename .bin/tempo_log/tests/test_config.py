import re
from pathlib import Path

import pytest

from tempo_log.config import ConfigError, encode_claude_project_dir, load_config

MINIMAL = """
[tempo]
base_url = "https://api.eu.tempo.io"
[jira]
site = "https://example.atlassian.net"
email = "dev@example.com"
account_id = "712020:abc"
"""


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / ".tempo-log.toml"
    p.write_text(text)
    return p


def test_defaults_applied(tmp_path):
    cfg = load_config(write(tmp_path, MINIMAL))
    assert cfg.tempo.token_env == "TEMPO_API_TOKEN"
    assert cfg.jira.token_env == "JIRA_API_TOKEN"
    assert cfg.rules.rounding_minutes == 30
    assert cfg.rules.idle_gap_minutes == 15
    assert cfg.rules.ticket_pattern.pattern == "[A-Z][A-Z0-9]+-[0-9]+"
    assert cfg.placement.mode == "actual"
    assert cfg.placement.window.seconds == 8 * 3600
    assert str(cfg.placement.timezone) == "UTC"
    assert cfg.sources.repos == "auto"
    assert cfg.sources.git_authors == ["dev@example.com"]
    assert cfg.hub_root == tmp_path
    assert cfg.state_dir == tmp_path / ".tempo-log"


def test_claude_projects_dir_defaults_to_encoded_hub(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = load_config(write(tmp_path, MINIMAL))
    assert cfg.sources.claude_projects_dir == encode_claude_project_dir(tmp_path)
    assert cfg.sources.claude_projects_dir.parent == tmp_path / "home" / ".claude" / "projects"


def test_encode_replaces_separators():
    assert encode_claude_project_dir(Path("/home/dev/projects")).name == "-home-dev-projects"


def test_invalid_mode_rejected(tmp_path):
    with pytest.raises(ConfigError, match="placement.mode"):
        load_config(write(tmp_path, MINIMAL + '[placement]\nmode = "squash"\n'))


def test_missing_required_key(tmp_path):
    with pytest.raises(ConfigError, match="jira.account_id"):
        load_config(write(tmp_path, MINIMAL.replace('account_id = "712020:abc"', "")))


def test_explicit_repos_and_authors(tmp_path):
    text = MINIMAL + '[sources]\nrepos = ["a", "b"]\ngit_authors = ["x@y.z"]\n'
    cfg = load_config(write(tmp_path, text))
    assert cfg.sources.repos == [tmp_path / "a", tmp_path / "b"]
    assert cfg.sources.git_authors == ["x@y.z"]


def test_bad_ticket_pattern(tmp_path):
    with pytest.raises(ConfigError, match="ticket_pattern"):
        load_config(write(tmp_path, MINIMAL + '[rules]\nticket_pattern = "["\n'))
