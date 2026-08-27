"""Place entries on the day: actual (check only), pack, fit."""

from __future__ import annotations

from datetime import time

from tempo_log.blocks import round_seconds
from tempo_log.models import Entry, Slot, Window, time_from_secs


class PlacementError(Exception):
    pass


def _secs(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def _fmt(t: time) -> str:
    return t.strftime("%H:%M")


def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def check_actual(entries: list[Entry], occupied: list[Slot]) -> list[str]:
    warnings: list[str] = []
    spans = []
    for e in entries:
        if e.start is None:
            raise PlacementError(f"entry {e.ticket or '(unattributed)'} has no start time")
        spans.append((e, _secs(e.start), _secs(e.start) + e.seconds))
    for e, s0, s1 in spans:
        for slot in occupied:
            if _overlaps(s0, s1, _secs(slot.start), _secs(slot.end)):
                warnings.append(
                    f"overlap: {e.ticket or '(unattributed)'} {_fmt(e.start)} with occupied "
                    f"{slot.ticket} {_fmt(slot.start)}-{_fmt(slot.end)}"
                )
    for i, (a, a0, a1) in enumerate(spans):
        for b, b0, b1 in spans[i + 1:]:
            if _overlaps(a0, a1, b0, b1):
                warnings.append(
                    f"overlap: {a.ticket or '(unattributed)'} {_fmt(a.start)} with "
                    f"{b.ticket or '(unattributed)'} {_fmt(b.start)}"
                )
    return warnings


def _free_capacity(occupied: list[Slot], window: Window) -> int:
    w0, w1 = _secs(window.start), _secs(window.end)
    used = 0
    for slot in occupied:
        s0, s1 = max(_secs(slot.start), w0), min(_secs(slot.end), w1)
        used += max(0, s1 - s0)
    return window.seconds - used


def _fit(entries: list[Entry], capacity: int, rounding_minutes: int) -> None:
    unit = rounding_minutes * 60
    capacity -= capacity % unit
    total = sum(e.seconds for e in entries)
    if total <= capacity:
        return
    if capacity < unit * len(entries):
        raise PlacementError(
            f"fit mode: free window capacity ({capacity // 60} min) is below one "
            f"{rounding_minutes}-minute unit per entry ({len(entries)} entries)"
        )
    for e in entries:
        e.original_seconds = e.seconds
        e.seconds = round_seconds(e.seconds * capacity // total, rounding_minutes)
    residual = capacity - sum(e.seconds for e in entries)
    for _ in range(len(entries) * 4):
        if residual == 0:
            break
        step = unit if residual > 0 else -unit
        target = max(entries, key=lambda e: e.seconds)
        if target.seconds + step < unit:
            raise PlacementError("fit mode: cannot distribute residual without dropping an entry below one unit")
        target.seconds += step
        residual -= step
    if residual != 0:
        raise PlacementError("fit mode: could not distribute the rounding residual")


def _place_sequential(entries: list[Entry], occupied: list[Slot], window: Window, mode: str) -> list[str]:
    slots = sorted((_secs(s.start), _secs(s.end)) for s in occupied)
    cursor = _secs(window.start)
    end_limit = _secs(window.end)
    warnings: list[str] = []
    for e in entries:
        while True:
            collision = next((s for s in slots if _overlaps(cursor, cursor + e.seconds, s[0], s[1])), None)
            if collision is None:
                break
            cursor = collision[1]
        if cursor + e.seconds > 86400:
            raise PlacementError(
                f"{e.ticket or '(unattributed)'} cannot be placed before midnight in {mode} mode; "
                f"use --mode actual or shorten the day"
            )
        e.start = time_from_secs(cursor)
        cursor += e.seconds
    if entries and cursor > end_limit and "window_overflow" not in warnings:
        warnings.append("window_overflow")
    return warnings


def place_window(entries: list[Entry], occupied: list[Slot], window: Window, mode: str, rounding_minutes: int) -> list[str]:
    if mode not in ("pack", "fit"):
        raise PlacementError(f"place_window called with mode {mode!r}")
    if mode == "fit":
        _fit(entries, _free_capacity(occupied, window), rounding_minutes)
    return _place_sequential(entries, occupied, window, mode)
