"""Bar cleaning & validation (spec 05 §3) — pure.

Intraday breakout edges are fragile to bad data, so the pipeline is defensive: dedupe,
drop weekend/closed bars, clip absurd outliers, and DETECT (never silently interpolate)
gaps. Data quality is itself tested (a fixture with known gaps/dupes -> a known-good
series)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from src.backtest.types import BTBar
from src.common.timeutil import ensure_utc


@dataclass
class CleanReport:
    input_count: int = 0
    output_count: int = 0
    duplicates_removed: int = 0
    weekend_dropped: int = 0
    outliers_dropped: int = 0
    gaps: list = field(default_factory=list)   # (prev_ts_iso, next_ts_iso, minutes)


def sort_bars(bars: list[BTBar]) -> list[BTBar]:
    return sorted(bars, key=lambda b: ensure_utc(b.ts_open_utc))


def dedupe_bars(bars: list[BTBar]) -> tuple[list[BTBar], int]:
    """Keep the LAST bar for any duplicated open timestamp (later export wins)."""
    by_ts: dict = {}
    for b in bars:
        by_ts[ensure_utc(b.ts_open_utc)] = b
    out = [by_ts[ts] for ts in sorted(by_ts)]
    return out, len(bars) - len(out)


def is_weekend_closed(ts) -> bool:
    """FX is closed from ~Fri 21:00 UTC to ~Sun 21:00 UTC. Conservative drop window."""
    ts = ensure_utc(ts)
    wd = ts.weekday()  # Mon=0 .. Sun=6
    if wd == 5:                       # Saturday
        return True
    if wd == 4 and ts.hour >= 21:     # Friday evening
        return True
    if wd == 6 and ts.hour < 21:      # Sunday before the open
        return True
    return False


def drop_weekend(bars: list[BTBar]) -> tuple[list[BTBar], int]:
    kept = [b for b in bars if not is_weekend_closed(b.ts_open_utc)]
    return kept, len(bars) - len(kept)


def clip_outliers(bars: list[BTBar], max_bar_range_pips: float, pip_size: float
                  ) -> tuple[list[BTBar], int]:
    """Drop bars whose high-low range is implausibly large (bad ticks / feed errors)."""
    kept = []
    dropped = 0
    for b in bars:
        rng_pips = (b.high - b.low) / pip_size
        if rng_pips > max_bar_range_pips or b.high < b.low or b.high <= 0:
            dropped += 1
            continue
        kept.append(b)
    return kept, dropped


def detect_gaps(bars: list[BTBar], tf_min: int) -> list:
    """Report (prev, next, minutes) where the spacing exceeds 1.5x the timeframe and the
    gap is NOT a weekend close. Gaps are surfaced, never interpolated."""
    gaps = []
    step = timedelta(minutes=tf_min)
    for i in range(1, len(bars)):
        prev = ensure_utc(bars[i - 1].ts_open_utc)
        cur = ensure_utc(bars[i].ts_open_utc)
        delta = cur - prev
        if delta > step * 1.5:
            # Skip if the prev bar sits right before a weekend close (expected gap).
            if is_weekend_closed(prev + step):
                continue
            gaps.append((prev.isoformat(), cur.isoformat(),
                         round(delta.total_seconds() / 60.0, 1)))
    return gaps


def clean_bars(bars: list[BTBar], *, tf_min: int = 15, pip_size: float = 0.0001,
               max_bar_range_pips: float = 500.0) -> tuple[list[BTBar], CleanReport]:
    rep = CleanReport(input_count=len(bars))
    bars = sort_bars(bars)
    bars, rep.duplicates_removed = dedupe_bars(bars)
    bars, rep.weekend_dropped = drop_weekend(bars)
    bars, rep.outliers_dropped = clip_outliers(bars, max_bar_range_pips, pip_size)
    rep.gaps = detect_gaps(bars, tf_min)
    rep.output_count = len(bars)
    return bars, rep
