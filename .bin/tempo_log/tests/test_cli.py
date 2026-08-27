import json
import zlib
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from tempo_log import cli
from tempo_log.draft import draft_path, dumps, loads
from tempo_log.ledger import Ledger
from tempo_log.models import Draft, Entry

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
            return 200, {"id": str(zlib.crc32(key.encode()) % 100000 + 1), "fields": {"summary": f"Summary of {key}"}}
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
    # one entry per ticket, first-activity order (07:12Z, 09:00Z, 12:00Z); s9 is unattributed
    assert [(e.ticket, e.seconds, e.start) for e in draft.entries] == [
        ("ADA-486", 1800, time(7, 12)), ("WI-100", 1800, time(9, 0)), ("", 1800, time(12, 0)),
    ]
    assert not any(w.startswith("overlap") for w in draft.warnings)
    ada = next(e for e in draft.entries if e.ticket == "ADA-486")
    assert ada.description == "ADA-486: Summary of ADA-486"
    assert ada.start is not None
    assert "ADA-486" in capsys.readouterr().out


def test_scan_mode_override_pack(hub):
    code, _ = run(hub, "scan", "2026-08-25", "--mode", "pack")
    draft = loads(draft_path(hub / ".tempo-log", date(2026, 8, 25)).read_text())
    assert draft.mode == "pack" and draft.window == "08:00-16:00"
    assert draft.entries[0].start.hour == 8 and draft.entries[0].start.minute == 30  # after 08:00-08:30 occupied


def test_day_bounds_spans_a_25_hour_dst_day():
    # 2026-10-25 is when Europe/Oslo falls back out of summer time, so the local
    # day is 25 hours long; start + timedelta(days=1) would get this wrong.
    cfg = SimpleNamespace(placement=SimpleNamespace(timezone=ZoneInfo("Europe/Oslo")))
    start, end = cli._day_bounds(date(2026, 10, 25), cfg)
    assert end - start == timedelta(hours=25)


def test_scan_range_writes_one_draft_per_day(hub):
    run(hub, "scan", "2026-08-25..2026-08-26")
    assert draft_path(hub / ".tempo-log", date(2026, 8, 25)).exists()
    assert draft_path(hub / ".tempo-log", date(2026, 8, 26)).exists()


def test_scan_excludes_own_posted_worklogs(hub):
    ledger = Ledger.load(hub / ".tempo-log" / "ledger.json")
    ledger.record(date(2026, 8, 25), 9, "EXIST-1", 1800, "08:00")

    code, _ = run(hub, "scan", "2026-08-25")
    assert code == 0
    draft = loads(draft_path(hub / ".tempo-log", date(2026, 8, 25)).read_text())
    assert draft.occupied == []


class RaisingTransport:
    def request(self, method, url, headers, body):
        raise AssertionError(f"unexpected call {method} {url}")


def test_scan_offline_makes_no_http_calls(hub):
    code, _ = run(hub, "scan", "2026-08-25", "--offline", transport=RaisingTransport())
    assert code == 0
    draft = loads(draft_path(hub / ".tempo-log", date(2026, 8, 25)).read_text())
    assert draft.occupied == []


def test_missing_token_is_a_clear_error(hub, capsys):
    code, _ = run(hub, "scan", "2026-08-25", env={})
    assert code == 4
    assert "TEMPO_API_TOKEN" in capsys.readouterr().err


def test_post_refuses_unattributed_and_dry_run_posts_nothing(hub, capsys):
    run(hub, "scan", "2026-08-25")
    code, t = run(hub, "post", "2026-08-25", "--dry-run")
    assert code == 1 and "unattributed" in capsys.readouterr().err
    assert not any(m == "POST" for m, _, _ in t.calls)


def test_dry_run_posts_nothing_on_valid_draft(hub, capsys):
    run(hub, "scan", "2026-08-25")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    p.write_text(_drop_unattributed_entry(p.read_text()))
    code, t = run(hub, "post", "2026-08-25", "--dry-run")
    out = capsys.readouterr().out
    assert code == 0
    assert not any(m == "POST" for m, _, _ in t.calls)
    assert "dry run" in out
    ledger_path = hub / ".tempo-log" / "ledger.json"
    posted = json.loads(ledger_path.read_text())["posted"] if ledger_path.exists() else {}
    assert "2026-08-25" not in posted


def test_post_keep_start_refuses_overlap_in_actual(hub, capsys):
    run(hub, "scan", "2026-08-25")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    # ADA-486 real start is 07:12; force it onto WI-100's 09:00 start to collide.
    text = p.read_text().replace('start = "07:12"', 'start = "09:00"', 1)
    p.write_text(text)

    code, t = run(hub, "post", "2026-08-25", "--dry-run", "--keep-start")
    assert code == 1
    assert "overlap" in capsys.readouterr().err
    assert not any(m == "POST" for m, _, _ in t.calls)

    p.write_text(_drop_unattributed_entry(text))
    code, t = run(hub, "post", "2026-08-25", "--dry-run")
    assert code == 0
    assert not any(m == "POST" for m, _, _ in t.calls)
    out = capsys.readouterr().out
    assert "nudged:" in out
    wi_line = next(l for l in out.splitlines() if "WI-100" in l and "POST" in l)
    assert "'startTime': '09:30:00'" in wi_line


def test_post_keep_start_refuses_overlap_in_pack(hub, capsys):
    run(hub, "scan", "2026-08-25", "--mode", "pack")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    text = _drop_unattributed_entry(p.read_text())
    # ADA-486 is packed to 08:30 (right after the 08:00-08:30 occupied slot);
    # force it back onto the occupied slot itself to collide.
    assert 'start = "08:30"' in text
    text = text.replace('start = "08:30"', 'start = "08:00"', 1)
    p.write_text(text)

    code, t = run(hub, "post", "2026-08-25", "--dry-run", "--keep-start")
    assert code == 1
    assert "overlap" in capsys.readouterr().err
    assert not any(m == "POST" for m, _, _ in t.calls)


def test_post_fit_refuses_when_total_exceeds_capacity(hub, capsys):
    run(hub, "scan", "2026-08-25", "--mode", "fit")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    text = _drop_unattributed_entry(p.read_text())
    # ADA-486 and WI-100 both start at 1800s each; bump both past the 7h30 free
    # capacity (8h window minus the scripted 30-min occupied slot).
    text = text.replace('ticket = "ADA-486"\nseconds = 1800', 'ticket = "ADA-486"\nseconds = 14400', 1)
    text = text.replace('ticket = "WI-100"\nseconds = 1800', 'ticket = "WI-100"\nseconds = 14400', 1)
    p.write_text(text)

    code, t = run(hub, "post", "2026-08-25", "--dry-run")
    assert code == 1
    err = capsys.readouterr().err
    assert "fit mode" in err
    assert not any(m == "POST" for m, _, _ in t.calls)


def test_post_fit_within_capacity_still_dry_runs(hub, capsys):
    run(hub, "scan", "2026-08-25", "--mode", "fit")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    p.write_text(_drop_unattributed_entry(p.read_text()))

    code, t = run(hub, "post", "2026-08-25", "--dry-run")
    assert code == 0
    assert not any(m == "POST" for m, _, _ in t.calls)


def test_post_keeps_edited_start_when_nudged_from_removed(hub, capsys):
    class NoOccupiedTransport(ScriptedTransport):
        def request(self, method, url, headers, body):
            if method == "GET" and "/4/worklogs/user/" in url:
                self.calls.append((method, url, body))
                return 200, {"results": [], "metadata": {}}
            return super().request(method, url, headers, body)

    day = date(2026, 8, 25)
    entry = Entry(ticket="ADA-486", seconds=1800, start=time(9, 30), description="ADA-486: work",
                  sources=[], first_activity=datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc))
    draft = Draft(day=day, mode="actual", window=None, timezone="UTC", entries=[entry], occupied=[], warnings=[])
    p = draft_path(hub / ".tempo-log", day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(draft))

    code, t = run(hub, "post", day.isoformat(), "--dry-run", transport=NoOccupiedTransport())
    assert code == 0
    out = capsys.readouterr().out
    ada_line = next(l for l in out.splitlines() if "ADA-486: work" in l and "POST" in l)
    assert "'startTime': '09:30:00'" in ada_line


def test_post_rewinds_to_real_start_when_collision_gone(hub, capsys):
    class NoOccupiedTransport(ScriptedTransport):
        def request(self, method, url, headers, body):
            if method == "GET" and "/4/worklogs/user/" in url:
                self.calls.append((method, url, body))
                return 200, {"results": [], "metadata": {}}
            return super().request(method, url, headers, body)

    day = date(2026, 8, 25)
    entry = Entry(ticket="ADA-486", seconds=1800, start=time(9, 30), description="ADA-486: work",
                  sources=[], first_activity=datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc))
    entry.nudged_from = time(9, 0)
    draft = Draft(day=day, mode="actual", window=None, timezone="UTC", entries=[entry], occupied=[], warnings=[])
    p = draft_path(hub / ".tempo-log", day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(draft))

    code, t = run(hub, "post", day.isoformat(), "--dry-run", transport=NoOccupiedTransport())
    assert code == 0
    out = capsys.readouterr().out
    ada_line = next(l for l in out.splitlines() if "ADA-486: work" in l and "POST" in l)
    assert "'startTime': '09:00:00'" in ada_line


def test_replace_does_not_nudge_past_own_worklogs(hub, capsys):
    class SelfCollisionTransport(ScriptedTransport):
        def __init__(self):
            super().__init__()
            self.extra_worklogs = []

        def request(self, method, url, headers, body):
            if method == "GET" and "/4/worklogs/user/" in url:
                self.calls.append((method, url, body))
                return 200, {"results": [
                    {"tempoWorklogId": 9, "startDate": "2026-08-25", "startTime": "08:00:00",
                     "timeSpentSeconds": 1800, "issue": {"id": 1}, "description": "EXIST-1: meeting"},
                    *self.extra_worklogs,
                ], "metadata": {}}
            return super().request(method, url, headers, body)

    t = SelfCollisionTransport()
    run(hub, "scan", "2026-08-25", transport=t)
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    p.write_text(_drop_unattributed_entry(p.read_text()))
    code, _ = run(hub, "post", "2026-08-25", transport=t)
    assert code == 0
    ledger = json.loads((hub / ".tempo-log" / "ledger.json").read_text())
    ada_id = next(int(r["worklog_id"]) for r in ledger["posted"]["2026-08-25"] if r["ticket"] == "ADA-486")

    # Tempo now reports ADA-486's own just-posted worklog as an occupied slot at the
    # same start; without excluding it by id, ADA-486 would get nudged past itself.
    t.extra_worklogs = [{"tempoWorklogId": ada_id, "startDate": "2026-08-25", "startTime": "07:12:00",
                          "timeSpentSeconds": 1800, "issue": {"id": 2}, "description": "ADA-486: prior"}]

    code, _ = run(hub, "post", "2026-08-25", "--replace", "--dry-run", transport=t)
    assert code == 0
    out = capsys.readouterr().out
    ada_line = next(l for l in out.splitlines() if "ADA-486: Summary of ADA-486" in l and "POST" in l)
    assert "'startTime': '07:12:00'" in ada_line


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


def test_undo_survives_a_404_delete(hub, capsys):
    run(hub, "scan", "2026-08-25")
    p = draft_path(hub / ".tempo-log", date(2026, 8, 25))
    p.write_text(_drop_unattributed_entry(p.read_text()))
    run(hub, "post", "2026-08-25")
    posted_before = json.loads((hub / ".tempo-log" / "ledger.json").read_text())["posted"]["2026-08-25"]
    assert len(posted_before) == 2

    # Simulate a prior undo that deleted the first worklog in Tempo but crashed
    # before the ledger was updated: the first DELETE now 404s (already gone),
    # the second still succeeds.
    t = ScriptedTransport()
    orig = t.request
    seen_deletes = {"n": 0}

    def req(method, url, headers, body):
        if method == "DELETE":
            seen_deletes["n"] += 1
            if seen_deletes["n"] == 1:
                return 404, {"errorMessages": ["not found"]}
            return 204, None
        return orig(method, url, headers, body)

    t.request = req
    code, _ = run(hub, "undo", "2026-08-25", transport=t)
    assert code == 0
    assert seen_deletes["n"] == 2
    ledger_after = json.loads((hub / ".tempo-log" / "ledger.json").read_text())
    assert "2026-08-25" not in ledger_after["posted"]


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
