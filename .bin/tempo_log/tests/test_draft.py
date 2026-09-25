import os
import time as time_module
import tomllib
from datetime import date, time
from pathlib import Path

import pytest

from tempo_log.draft import DraftError, draft_path, dumps, loads, render_table, validate_for_post
from tempo_log.models import Draft, Entry, Slot


def sample(utc, mode="actual"):
    return Draft(
        day=date(2026, 8, 25), mode=mode, window=None if mode == "actual" else "08:00-16:00",
        timezone="Atlantic/Reykjavik",
        entries=[
            Entry("ADA-486", 5400, time(9, 0), 'ADA-486: Fix "quotes"', ["claude:2 blocks"], utc(2026, 8, 25, 9)),
            Entry("", 1800, time(11, 30), "", ["claude:1 blocks"], utc(2026, 8, 25, 11, 30)),
        ],
        occupied=[Slot(time(8, 0), time(9, 0), "ADA-470")],
        warnings=[],
    )


def test_dumps_is_valid_toml_and_roundtrips(utc):
    text = dumps(sample(utc))
    tomllib.loads(text)
    back = loads(text)
    assert back == sample(utc)


def test_roundtrip_window_mode_with_original_seconds(utc):
    d = sample(utc, "fit")
    d.entries[0].original_seconds = 7200
    d.warnings = ["window_overflow"]
    back = loads(dumps(d))
    assert back.window == "08:00-16:00"
    assert back.entries[0].original_seconds == 7200
    assert back.warnings == ["window_overflow"]


def test_roundtrip_nudged_from(utc):
    d = sample(utc)
    d.entries[0].nudged_from = time(8, 30)
    back = loads(dumps(d))
    assert back.entries[0].nudged_from == time(8, 30)
    out = render_table(back)
    assert "<" in out
    assert "nudged forward" in out


def test_loads_accepts_user_edits_and_omissions():
    text = """
date = "2026-08-25"
mode = "actual"
timezone = "UTC"

[[entries]]
ticket = "ADA-1"
seconds = 1800
start = "09:00"
"""
    d = loads(text)
    assert d.entries[0].ticket == "ADA-1"
    assert d.entries[0].description == ""
    assert d.entries[0].start == time(9, 0)
    assert d.occupied == [] and d.warnings == []


def test_validate_rejects_empty_ticket(utc):
    with pytest.raises(DraftError, match="unattributed"):
        validate_for_post(sample(utc), 30)


def test_validate_rejects_missing_start_in_actual(utc):
    d = sample(utc)
    d.entries = [Entry("ADA-1", 1800, None, "", [], utc(2026, 8, 25, 9))]
    with pytest.raises(DraftError, match="start"):
        validate_for_post(d, 30)


def test_validate_rejects_missing_start_in_pack(utc):
    # pack/fit drafts normally get start assigned by placement before post, but a
    # hand-edited draft (or --keep-start with a start stripped by hand) can still
    # reach validate_for_post with start=None; every mode requires it.
    d = sample(utc, "pack")
    d.entries = [Entry("ADA-1", 1800, None, "", [], utc(2026, 8, 25, 9))]
    with pytest.raises(DraftError, match="start"):
        validate_for_post(d, 30)


def test_validate_rejects_overlap_warning(utc):
    d = sample(utc)
    d.entries = d.entries[:1]
    d.warnings = ["overlap: ADA-486 09:00 with occupied ADA-470 08:00-09:00"]
    with pytest.raises(DraftError, match="overlap"):
        validate_for_post(d, 30)


def test_validate_warns_on_unrounded_seconds(utc):
    d = sample(utc)
    d.entries = [Entry("ADA-1", 1000, time(9, 0), "", [], utc(2026, 8, 25, 9))]
    assert validate_for_post(d, 30) == ["ADA-1: 1000 seconds is not a multiple of 30 minutes"]


def test_draft_path():
    assert draft_path(Path("/s"), date(2026, 8, 25)) == Path("/s/drafts/2026-08-25.toml")


def test_render_table_mentions_unattributed_and_totals(utc):
    out = render_table(sample(utc))
    assert "UNATTRIBUTED" in out
    assert "2h00m" in out  # total 5400 + 1800


def test_render_table_sorts_rows_by_start(utc):
    d = sample(utc)
    d.entries = [
        Entry("A-1", 1800, time(10, 0), "later", [], utc(2026, 8, 25, 9)),
        Entry("B-2", 1800, time(9, 30), "earlier", [], utc(2026, 8, 25, 9, 30)),
    ]
    d.entries[0].nudged_from = time(9, 0)
    out = render_table(d)
    assert out.index("B-2") < out.index("A-1")


def test_dumps_escapes_control_characters(utc):
    d = sample(utc)
    d.entries[0].description = 'has "quote", back\\slash, new\nline, tab\tand \x7f del'
    text = dumps(d)
    tomllib.loads(text)
    back = loads(text)
    assert back.entries[0].description == d.entries[0].description


def test_loads_naive_first_activity_is_utc(monkeypatch, utc):
    original_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "America/New_York")
    time_module.tzset()
    try:
        text = """
date = "2026-08-25"
mode = "actual"
timezone = "UTC"

[[entries]]
ticket = "ADA-1"
seconds = 1800
start = "09:00"
first_activity = "2026-08-25T09:00:00"
"""
        d = loads(text)
        assert d.entries[0].first_activity == utc(2026, 8, 25, 9)
    finally:
        if original_tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_tz)
        time_module.tzset()


def test_loads_rejects_non_table_entries():
    text = """
date = "2026-08-25"
mode = "actual"
timezone = "UTC"
entries = "foo"
"""
    with pytest.raises(DraftError):
        loads(text)
