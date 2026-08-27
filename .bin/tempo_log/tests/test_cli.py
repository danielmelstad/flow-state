import json
import os
from datetime import date
from pathlib import Path

import pytest

from tempo_log import cli
from tempo_log.draft import draft_path, loads

CONFIG = """
[tempo]
base_url = "https://api.eu.tempo.io"
[jira]
site = "https://x.atlassian.net"
email = "me@x"
account_id = "712020:abc"
[placement]
mode = "{mode}"
window = "08:00-16:00"
timezone = "UTC"
[sources]
claude_projects_dir = "{fixtures}"
repos = []
"""


class ScriptedTransport:
    """Routes by (method, url prefix); records calls."""

    def __init__(self):
        self.calls = []
        self.created = 0

    def request(self, method, url, headers, body):
        self.calls.append((method, url, body))
        if method == "GET" and "/rest/api/3/issue/" in url:
            key = url.rsplit("/", 1)[1].split("?")[0]
            return 200, {"id": str(abs(hash(key)) % 100000 + 1), "fields": {"summary": f"Summary of {key}"}}
        if method == "GET" and "/4/worklogs/user/" in url:
            return 200, {"results": [{"tempoWorklogId": 9, "startDate": "2026-08-25", "startTime": "08:00:00",
                                      "timeSpentSeconds": 1800, "issue": {"id": 1}, "description": "EXIST-1: meeting"}],
                         "metadata": {}}
        if method == "POST" and url.endswith("/4/worklogs"):
            self.created += 1
            return 200, {"tempoWorklogId": 100 + self.created}
        if method == "DELETE":
            return 204, None
        raise AssertionError(f"unexpected call {method} {url}")


@pytest.fixture
def hub(tmp_path):
    fixtures = Path(__file__).parent / "fixtures"
    (tmp_path / ".tempo-log.toml").write_text(CONFIG.format(mode="actual", fixtures=fixtures))
    return tmp_path


ENV = {"TEMPO_API_TOKEN": "t", "JIRA_API_TOKEN": "j"}


def run(hub, *args, transport=None, env=ENV):
    transport = transport or ScriptedTransport()
    code = cli.main(["--config", str(hub / ".tempo-log.toml"), *args], transport=transport, env=env)
    return code, transport


def _drop_unattributed_entry(text: str) -> str:
    """Remove the [[entries]] block whose ticket = "" (the s9 unattributed entry)."""
    parts = text.split("\n\n[[entries]]\n")
    kept = [block for block in parts[1:] if not block.startswith('ticket = ""')]
    result = parts[0]
    for block in kept:
        result += "\n\n[[entries]]\n" + block
    return result


def test_scan_writes_draft_with_occupied_and_entries(hub, capsys):
    code, t = run(hub, "scan", "2026-08-25")
    assert code == 0
    draft = loads(draft_path(hub / ".tempo-log", date(2026, 8, 25)).read_text())
    assert draft.mode == "actual"
    assert [s.ticket for s in draft.occupied] == ["EXIST-1: meeting"]
    tickets = [e.ticket for e in draft.entries]
    assert "ADA-486" in tickets and "WI-100" in tickets and "" in tickets  # s9 entry is unattributed
    ada = next(e for e in draft.entries if e.ticket == "ADA-486")
    assert ada.description == "ADA-486: Summary of ADA-486"
    assert ada.start is not None
    assert "ADA-486" in capsys.readouterr().out


def test_scan_mode_override_pack(hub):
    code, _ = run(hub, "scan", "2026-08-25", "--mode", "pack")
    draft = loads(draft_path(hub / ".tempo-log", date(2026, 8, 25)).read_text())
    assert draft.mode == "pack" and draft.window == "08:00-16:00"
    assert draft.entries[0].start.hour == 8 and draft.entries[0].start.minute == 30  # after 08:00-08:30 occupied


def test_scan_range_writes_one_draft_per_day(hub):
    run(hub, "scan", "2026-08-25..2026-08-26")
    assert draft_path(hub / ".tempo-log", date(2026, 8, 25)).exists()
    assert draft_path(hub / ".tempo-log", date(2026, 8, 26)).exists()


def test_missing_token_is_a_clear_error(hub, capsys):
    code, _ = run(hub, "scan", "2026-08-25", env={})
    assert code == 2
    assert "TEMPO_API_TOKEN" in capsys.readouterr().err


def test_post_refuses_unattributed_and_dry_run_posts_nothing(hub, capsys):
    run(hub, "scan", "2026-08-25")
    code, t = run(hub, "post", "2026-08-25", "--dry-run")
    assert code == 1 and "unattributed" in capsys.readouterr().err
    assert not any(m == "POST" for m, _, _ in t.calls)


def test_post_then_refuse_then_replace_then_undo(hub, capsys):
    run(hub, "scan", "2026-08-25")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    p.write_text(_drop_unattributed_entry(p.read_text()))
    code, t = run(hub, "post", "2026-08-25")
    assert code == 0
    posts = [b for m, _, b in t.calls if m == "POST"]
    assert posts and all(b["authorAccountId"] == "712020:abc" for b in posts)
    assert all(set(b) >= {"issueId", "startDate", "startTime", "timeSpentSeconds", "description"} for b in posts)
    ledger = json.loads((hub / ".tempo-log" / "ledger.json").read_text())
    assert len(ledger["posted"]["2026-08-25"]) == len(posts)

    code, _ = run(hub, "post", "2026-08-25")
    assert code == 1 and "--replace" in capsys.readouterr().err

    code, t = run(hub, "post", "2026-08-25", "--replace")
    assert code == 0
    deletes = [u for m, u, _ in t.calls if m == "DELETE"]
    assert len(deletes) == len(posts)

    code, t = run(hub, "undo", "2026-08-25")
    assert code == 0
    assert len([1 for m, _, _ in t.calls if m == "DELETE"]) == len(posts)
    assert "2026-08-25" not in json.loads((hub / ".tempo-log" / "ledger.json").read_text())["posted"]


def test_show_prints_table(hub, capsys):
    run(hub, "scan", "2026-08-25")
    capsys.readouterr()
    code, _ = run(hub, "show", "2026-08-25")
    out = capsys.readouterr().out
    assert code == 0 and "total" in out and "EXIST-1" in out


def test_resolve_me_and_key(hub, capsys):
    t = ScriptedTransport()
    orig = t.request

    def req(method, url, headers, body):
        if url.endswith("/rest/api/3/myself"):
            return 200, {"accountId": "712020:zzz", "displayName": "Dev"}
        return orig(method, url, headers, body)

    t.request = req
    assert run(hub, "resolve", "me", transport=t)[0] == 0
    assert 'account_id = "712020:zzz"' in capsys.readouterr().out
    assert run(hub, "resolve", "ADA-1", transport=t)[0] == 0
    assert "Summary of ADA-1" in capsys.readouterr().out
