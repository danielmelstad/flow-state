import json
import pytest
from datetime import date

from tempo_log.ledger import Ledger


def test_record_saves_immediately_and_lists(tmp_path):
    path = tmp_path / "ledger.json"
    led = Ledger.load(path)
    assert led.posted(date(2026, 8, 25)) == []
    led.record(date(2026, 8, 25), 101, "ADA-1", 1800, "09:00")
    led.record(date(2026, 8, 25), 102, "ADA-2", 3600, "09:30")
    again = Ledger.load(path)
    assert [p["worklog_id"] for p in again.posted(date(2026, 8, 25))] == [101, 102]
    assert again.posted(date(2026, 8, 26)) == []


def test_clear_removes_only_that_day(tmp_path):
    led = Ledger.load(tmp_path / "l.json")
    led.record(date(2026, 8, 25), 1, "A", 1, "08:00")
    led.record(date(2026, 8, 26), 2, "A", 1, "08:00")
    led.clear(date(2026, 8, 25))
    again = Ledger.load(tmp_path / "l.json")
    assert again.posted(date(2026, 8, 25)) == [] and len(again.posted(date(2026, 8, 26))) == 1


def test_issue_cache(tmp_path):
    led = Ledger.load(tmp_path / "l.json")
    assert led.issue_id("ADA-1") is None
    led.remember_issue("ADA-1", 12345, "Do the thing")
    again = Ledger.load(tmp_path / "l.json")
    assert again.issue_id("ADA-1") == 12345 and again.issue_summary("ADA-1") == "Do the thing"


def test_corrupt_file_is_an_error(tmp_path):
    p = tmp_path / "l.json"
    p.write_text("{not json")

    with pytest.raises(ValueError):
        Ledger.load(p)
