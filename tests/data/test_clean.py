"""Bar cleaning + gap detection (spec 05 §3) — data quality is itself tested."""

from datetime import datetime, timedelta, timezone

from src.backtest.types import BTBar
from src.data.clean import clean_bars, dedupe_bars, detect_gaps, drop_weekend


def _b(ts, o=1.10, h=1.1005, l=1.0995, c=1.10, spread=0.4):
    return BTBar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=10, spread_pips=spread)


def _series(start, n, tf=15):
    return [_b(start + timedelta(minutes=tf * i)) for i in range(n)]


def test_dedupe_keeps_one_per_timestamp():
    t = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    bars = [_b(t, c=1.10), _b(t, c=1.11), _b(t + timedelta(minutes=15))]
    out, removed = dedupe_bars(bars)
    assert removed == 1
    assert len(out) == 2
    assert out[0].close == 1.11   # last write wins


def test_weekend_bars_dropped():
    sat = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)      # Saturday
    fri_late = datetime(2026, 6, 5, 22, 0, tzinfo=timezone.utc)  # Fri 22:00 UTC
    tue = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)       # Tuesday (kept)
    out, dropped = drop_weekend([_b(sat), _b(fri_late), _b(tue)])
    assert dropped == 2
    assert [b.ts_open_utc for b in out] == [tue]


def test_gap_detection_flags_midweek_hole_not_weekend():
    t = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)  # Tuesday
    bars = [_b(t), _b(t + timedelta(minutes=15)), _b(t + timedelta(minutes=120))]
    gaps = detect_gaps(bars, tf_min=15)
    assert len(gaps) == 1
    assert gaps[0][2] == 105.0   # minutes between the 12:15 and 14:00 bars


def test_clean_orchestrator_outlier_and_report():
    t = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    bars = _series(t, 5)
    bars.append(_b(t + timedelta(minutes=75), h=1.20, l=1.10))  # 1000-pip range outlier
    cleaned, rep = clean_bars(bars, tf_min=15, pip_size=0.0001, max_bar_range_pips=500)
    assert rep.outliers_dropped == 1
    assert rep.output_count == 5
    assert all((b.high - b.low) / 0.0001 <= 500 for b in cleaned)
