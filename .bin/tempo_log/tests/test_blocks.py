from datetime import date, time
from zoneinfo import ZoneInfo

from tempo_log.blocks import cluster, entries_for_day, round_seconds
from tempo_log.models import Event

TZ = ZoneInfo("Atlantic/Reykjavik")  # UTC+0 all year, keeps arithmetic obvious
OSLO = ZoneInfo("Europe/Oslo")


def ev(utc, h, m, ticket="A-1", source="claude", session="s"):
    return Event(utc(2026, 8, 25, h, m), ticket, source, session)


def test_round_half_up_and_floor():
    assert round_seconds(0, 30) == 0
    assert round_seconds(1, 30) == 1800
    assert round_seconds(44 * 60, 30) == 1800
    assert round_seconds(45 * 60, 30) == 3600
    assert round_seconds(46 * 60, 30) == 3600
    assert round_seconds(7 * 60, 15) == 900


def test_cluster_splits_on_gap_and_ticket(utc):
    blocks = cluster([
        ev(utc, 9, 0), ev(utc, 9, 10), ev(utc, 9, 20),
        ev(utc, 9, 36),                 # 16 min gap > 15 -> new block
        ev(utc, 9, 37, ticket="B-2"),  # other ticket, own block
        ev(utc, 9, 38, ticket=None),   # unattributed
    ], TZ, 15)
    keyed = [(b.ticket, b.start.minute, b.end.minute, b.events) for b in blocks]
    assert keyed == [("A-1", 0, 20, 3), ("A-1", 36, 36, 1), ("B-2", 37, 37, 1), (None, 38, 38, 1)]
    assert blocks[0].day == date(2026, 8, 25)
    assert blocks[0].sources == {"claude": 3}


def test_cluster_buckets_by_local_day(utc):
    # 23:30Z on the 25th is 01:30 on the 26th in Oslo (UTC+2 in August)
    blocks = cluster([ev(utc, 23, 30)], OSLO, 15)
    assert blocks[0].day == date(2026, 8, 26)


def test_entries_actual_mode_one_per_block(utc):
    blocks = cluster([
        # block 1: 09:00-09:40 (40 min) -> 30 min after rounding
        ev(utc, 9, 0), ev(utc, 9, 10), ev(utc, 9, 20), ev(utc, 9, 30), ev(utc, 9, 40),
        # block 2: 13:02-13:50 (48 min) -> 60 min; starts with a commit
        ev(utc, 13, 2, source="git", session=None), ev(utc, 13, 14), ev(utc, 13, 26),
        ev(utc, 13, 38), ev(utc, 13, 50),
    ], TZ, 15)
    entries = entries_for_day(blocks, date(2026, 8, 25), "actual", 30, TZ)
    assert [(e.ticket, e.seconds, e.start) for e in entries] == [
        ("A-1", 1800, time(9, 0)), ("A-1", 3600, time(13, 2)),
    ]
    assert entries[0].sources == ["claude:1 blocks"]
    assert entries[1].sources == ["claude:1 blocks", "git:1 commits"]
    assert entries[0].first_activity == utc(2026, 8, 25, 9, 0)


def test_entries_window_mode_one_per_ticket(utc):
    blocks = cluster([
        ev(utc, 9, 0), ev(utc, 9, 10), ev(utc, 9, 20), ev(utc, 9, 30), ev(utc, 9, 40),   # 40 min
        ev(utc, 13, 0), ev(utc, 13, 10), ev(utc, 13, 20), ev(utc, 13, 30), ev(utc, 13, 40), ev(utc, 13, 50),  # 50 min
        ev(utc, 11, 0, ticket=None),
    ], TZ, 15)
    entries = entries_for_day(blocks, date(2026, 8, 25), "pack", 30, TZ)
    assert [(e.ticket, e.seconds, e.start) for e in entries] == [
        ("A-1", 5400, None),   # 40 + 50 = 90 min, already a multiple of 30
        ("", 1800, None),      # single event -> one unit floor
    ]
    assert entries[0].sources == ["claude:2 blocks"]


def test_entries_only_for_requested_day(utc):
    blocks = cluster([ev(utc, 9, 0), Event(utc(2026, 8, 26, 9, 0), "A-1", "claude", "s")], TZ, 15)
    assert len(entries_for_day(blocks, date(2026, 8, 26), "actual", 30, TZ)) == 1


def test_entries_actual_mode_single_event_block_gets_one_unit(utc):
    blocks = cluster([ev(utc, 9, 0)], TZ, 15)
    entries = entries_for_day(blocks, date(2026, 8, 25), "actual", 30, TZ)
    assert [(e.ticket, e.seconds, e.start) for e in entries] == [
        ("A-1", 1800, time(9, 0)),
    ]


def test_entries_window_mode_git_only_sources(utc):
    blocks = cluster([
        ev(utc, 9, 0, source="git", session=None),
        ev(utc, 9, 10, source="git", session=None),
    ], TZ, 15)
    entries = entries_for_day(blocks, date(2026, 8, 25), "pack", 30, TZ)
    assert len(entries) == 1
    assert entries[0].sources == ["git:2 commits"]
