from datetime import time

import pytest

from tempo_log.models import Entry, Slot, Window
from tempo_log.place import PlacementError, check_actual, place_window

W = Window.parse("08:00-16:00")


def entry(utc, ticket, minutes, start=None, h=9):
    return Entry(ticket=ticket, seconds=minutes * 60, start=start, description="",
                 sources=[], first_activity=utc(2026, 8, 25, h))


def test_actual_no_overlap(utc):
    es = [entry(utc, "A-1", 30, time(9, 0)), entry(utc, "A-1", 30, time(9, 30))]
    assert check_actual(es, [Slot(time(10, 0), time(11, 0), "B-2")]) == []


def test_actual_overlap_with_occupied_and_neighbour(utc):
    es = [entry(utc, "A-1", 60, time(9, 30)), entry(utc, "A-1", 30, time(10, 0))]
    warnings = check_actual(es, [Slot(time(10, 0), time(11, 0), "B-2")])
    assert "overlap: A-1 09:30 with occupied B-2 10:00-11:00" in warnings
    assert "overlap: A-1 09:30 with A-1 10:00" in warnings
    assert "overlap: A-1 10:00 with occupied B-2 10:00-11:00" in warnings


def test_pack_sequential_from_window_start(utc):
    es = [entry(utc, "A-1", 90), entry(utc, "B-2", 30)]
    assert place_window(es, [], W, "pack", 30) == []
    assert [e.start for e in es] == [time(8, 0), time(9, 30)]


def test_pack_skips_occupied_slots(utc):
    es = [entry(utc, "A-1", 90), entry(utc, "B-2", 60)]
    occupied = [Slot(time(8, 0), time(9, 0), "X-9"), Slot(time(10, 0), time(10, 30), "X-9")]
    place_window(es, occupied, W, "pack", 30)
    # 09:00-10:30 would collide with 10:00; an entry never straddles a slot, so it moves after it
    assert [e.start for e in es] == [time(10, 30), time(12, 0)]


def test_pack_overflow_warning(utc):
    es = [entry(utc, "A-1", 8 * 60), entry(utc, "B-2", 60)]
    assert place_window(es, [], W, "pack", 30) == ["window_overflow"]
    assert es[1].start == time(16, 0)


def test_fit_scales_to_capacity_and_records_original(utc):
    es = [entry(utc, "A-1", 6 * 60), entry(utc, "B-2", 4 * 60)]  # 10h into 8h
    assert place_window(es, [], W, "fit", 30) == []
    # scale 0.8: 4.8h (288 min) rounds half-up to 5h, 3.2h (192 min) to 3h; sums to 8h, no residual
    assert [e.seconds for e in es] == [5 * 3600, 3 * 3600]
    assert sum(e.seconds for e in es) == 8 * 3600
    assert [e.original_seconds for e in es] == [6 * 3600, 4 * 3600]
    assert [e.start for e in es] == [time(8, 0), time(13, 0)]


def test_fit_residual_goes_to_largest(utc):
    es = [entry(utc, "A-1", 5 * 60), entry(utc, "B-2", 5 * 60), entry(utc, "C-3", 2 * 60)]  # 12h
    place_window(es, [], W, "fit", 30)
    # scaled: 3.33h, 3.33h, 1.33h -> rounded 3.5, 3.5, 1.5 = 8.5h; largest loses 30 min
    assert [e.seconds for e in es] == [3 * 3600, 3 * 3600 + 1800, 3600 + 1800]
    assert sum(e.seconds for e in es) == 8 * 3600


def test_fit_leaves_short_days_alone(utc):
    es = [entry(utc, "A-1", 120)]
    place_window(es, [], W, "fit", 30)
    assert es[0].seconds == 7200 and es[0].original_seconds is None


def test_fit_capacity_accounts_for_occupied(utc):
    es = [entry(utc, "A-1", 8 * 60)]
    place_window(es, [Slot(time(8, 0), time(10, 0), "X")], W, "fit", 30)
    assert es[0].seconds == 6 * 3600 and es[0].start == time(10, 0)


def test_fit_too_little_capacity(utc):
    es = [entry(utc, "A-1", 60), entry(utc, "B-2", 60)]
    with pytest.raises(PlacementError):
        place_window(es, [Slot(time(8, 0), time(15, 30), "X")], W, "fit", 30)
