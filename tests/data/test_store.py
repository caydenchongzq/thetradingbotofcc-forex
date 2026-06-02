"""Parquet round-trip + period filter (spec 05 §3)."""

from datetime import datetime, timedelta, timezone

from src.backtest.types import BTBar
from src.data.store import read_parquet_bars, write_parquet


def _b(ts):
    return BTBar(ts_open_utc=ts, open=1.10, high=1.1005, low=1.0995, close=1.1002,
                 volume=10, spread_pips=0.4)


def test_parquet_roundtrip_and_period_filter(tmp_path):
    base = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    bars = [_b(base + timedelta(minutes=15 * i)) for i in range(10)]
    path = write_parquet(bars, tmp_path / "eurusd_m15.parquet")

    full = read_parquet_bars(path)
    assert len(full) == 10
    assert abs(full[0].close - 1.1002) < 1e-9
    assert full[0].ts_open_utc == base   # tz-aware UTC preserved

    window = read_parquet_bars(path, period=(base, base + timedelta(minutes=45)))
    assert len(window) == 4   # 12:00, 12:15, 12:30, 12:45
