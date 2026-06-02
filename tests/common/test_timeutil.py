"""FTMO trading-day boundary, incl. the Europe/Prague DST changes (spec 02 §2/§10)."""

from datetime import datetime, timezone

from src.common.timeutil import ftmo_day_start, is_new_ftmo_day, next_ftmo_day_start


def _utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_winter_offset_is_plus_one():
    # In CET (winter), 00:00 Prague == 23:00 UTC the previous day.
    start = ftmo_day_start(_utc(2026, 1, 15, 12, 0))
    assert start == _utc(2026, 1, 14, 23, 0)


def test_summer_offset_is_plus_two():
    # In CEST (summer), 00:00 Prague == 22:00 UTC the previous day.
    start = ftmo_day_start(_utc(2026, 7, 15, 12, 0))
    assert start == _utc(2026, 7, 14, 22, 0)


def test_spring_forward_dst_boundary():
    # DST starts 2026-03-29 (clocks 02:00->03:00 CET->CEST).
    # A timestamp just after the change resolves to the same Prague calendar day start.
    start = ftmo_day_start(_utc(2026, 3, 29, 10, 0))
    # 00:00 Prague on 2026-03-29 was still CET -> 23:00 UTC on 03-28.
    assert start == _utc(2026, 3, 28, 23, 0)
    assert start.astimezone(timezone.utc) < _utc(2026, 3, 29, 10, 0)


def test_fall_back_dst_boundary():
    # DST ends 2026-10-25 (clocks 03:00->02:00 CEST->CET).
    start = ftmo_day_start(_utc(2026, 10, 25, 12, 0))
    # 00:00 Prague on 2026-10-25 was still CEST -> 22:00 UTC on 10-24.
    assert start == _utc(2026, 10, 24, 22, 0)


def test_is_new_ftmo_day_detects_boundary_crossing():
    last = ftmo_day_start(_utc(2026, 6, 2, 12, 0))
    assert not is_new_ftmo_day(last, _utc(2026, 6, 2, 20, 0))   # same FTMO day
    assert is_new_ftmo_day(last, _utc(2026, 6, 3, 5, 0))         # next FTMO day
    assert is_new_ftmo_day(None, _utc(2026, 6, 2, 12, 0))        # never reset -> True


def test_next_day_start_advances_one_day_across_dst():
    nxt = next_ftmo_day_start(_utc(2026, 3, 28, 12, 0))
    assert nxt == ftmo_day_start(_utc(2026, 3, 29, 12, 0))
