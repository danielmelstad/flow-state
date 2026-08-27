from pathlib import Path

from tempo_log.sources.claude_sessions import parse_record, read_events

FIXTURES = Path(__file__).parent / "fixtures"


def test_read_events_filters_range_and_skips_junk(utc):
    events = read_events(FIXTURES, utc(2026, 8, 25), utc(2026, 8, 26))
    assert [e.ts.hour for e in events] == [7, 7, 7, 7, 9, 12]
    assert all(e.source == "claude" for e in events)


def test_user_text_and_cwd_branch(utc):
    events = read_events(FIXTURES, utc(2026, 8, 25), utc(2026, 8, 26))
    first = events[0]
    assert first.session == "s1"
    assert first.text == "work on ADA-486"
    assert first.cwd == "/hub"
    assert first.branch == "main"
    wi_event = next(e for e in events if e.cwd == "/hub/.worktrees/WI-100/svc")
    assert wi_event.branch == "WI-100"


def test_tool_use_paths_extracted(utc):
    events = read_events(FIXTURES, utc(2026, 8, 25), utc(2026, 8, 26))
    read_ev, bash_ev = events[1], events[2]
    assert read_ev.paths == ("/hub/.worktrees/ADA-486/repo/x.py",)
    assert "/hub/.worktrees/ADA-486/repo" in bash_ev.paths
    assert read_ev.text == ""


def test_tool_result_content_is_not_text(utc):
    events = read_events(FIXTURES, utc(2026, 8, 25), utc(2026, 8, 26))
    assert events[3].text == ""


def test_parse_record_ignores_non_message_types():
    assert parse_record({"type": "mode", "sessionId": "x"}) is None
    assert parse_record({"type": "user", "sessionId": "x"}) is None  # no timestamp


def test_missing_dir_yields_nothing(tmp_path, utc):
    assert read_events(tmp_path / "nope", utc(2026, 1, 1), utc(2026, 1, 2)) == []


def test_malformed_records_are_skipped_not_fatal(utc):
    events = read_events(FIXTURES, utc(2026, 8, 25), utc(2026, 8, 26))
    assert len(events) > 0
    assert not any(e.session == "s9" and e.text == "bad ts" for e in events)
    s9_events = [e for e in events if e.session == "s9"]
    assert len(s9_events) == 1
    assert s9_events[0].text == ""
