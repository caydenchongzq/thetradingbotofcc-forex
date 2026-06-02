"""Watchdog backoff + freshness (spec 07 §3/§12)."""

from src.ops.watchdog import backoff_delay, backoff_schedule, data_is_fresh


def test_backoff_doubles_and_caps():
    assert backoff_delay(0, base_s=2, max_s=60) == 2
    assert backoff_delay(1, base_s=2, max_s=60) == 4
    assert backoff_delay(3, base_s=2, max_s=60) == 16
    assert backoff_delay(10, base_s=2, max_s=60) == 60   # capped
    assert backoff_schedule(4, 2, 60) == [2, 4, 8, 16]


def test_stale_data_triggers_failsafe():
    # tick 200s old vs 90s tolerance -> not fresh -> fail-safe (no new trade)
    assert data_is_fresh(1000.0, 1200.0, tolerance_s=90) is False
    assert data_is_fresh(1000.0, 1050.0, tolerance_s=90) is True
    assert data_is_fresh(None, 1050.0, tolerance_s=90) is False


def test_future_tick_from_server_offset_is_fresh():
    # broker clock ahead -> negative age -> still fresh (only OLD ticks fail)
    assert data_is_fresh(1_000_000.0, 990_000.0, tolerance_s=90) is True
