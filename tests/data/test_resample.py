"""Tick -> OHLC resample with spread (spec 05 §3)."""

from datetime import datetime, timedelta, timezone

from src.data.resample import ticks_to_bars


def test_ticks_resample_to_15m_ohlc_and_spread():
    base = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    # Three ticks in the 12:00 bucket, one in 12:15. bid/ask spread = 1 pip.
    ticks = [
        (base + timedelta(seconds=1), 1.1000, 1.1001),
        (base + timedelta(minutes=5), 1.1010, 1.1011),   # high
        (base + timedelta(minutes=10), 1.0995, 1.0996),  # low
        (base + timedelta(minutes=16), 1.1002, 1.1003),  # next bucket
    ]
    bars = ticks_to_bars(ticks, tf_min=15, pip_size=0.0001)
    assert len(bars) == 2
    b0 = bars[0]
    assert round(b0.open, 5) == 1.10005     # mid of first tick
    assert round(b0.high, 5) == 1.10105
    assert round(b0.low, 5) == 1.09955
    assert round(b0.close, 5) == 1.09955
    assert abs(b0.spread_pips - 1.0) < 1e-6  # 1-pip spread
