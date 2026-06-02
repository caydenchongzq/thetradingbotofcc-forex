"""Tick -> OHLC bar resampling (spec 05 §3) — pure.

Bid/ask ticks are required because spread + slippage make or break an intraday breakout
edge. We build OHLC on the mid price and record the mean spread per bar (in pips)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from src.backtest.types import BTBar
from src.common.timeutil import ensure_utc


def _floor_to_bucket(ts: datetime, tf_min: int) -> datetime:
    ts = ensure_utc(ts)
    epoch = int(ts.timestamp())
    bucket = epoch - (epoch % (tf_min * 60))
    return datetime.fromtimestamp(bucket, tz=timezone.utc)


def ticks_to_bars(ticks: Sequence[tuple], tf_min: int, pip_size: float = 0.0001
                  ) -> list[BTBar]:
    """``ticks`` = iterable of (ts_utc, bid, ask), chronological. Returns OHLC(mid) bars
    with ``spread_pips`` = mean (ask-bid)/pip over the bar."""
    buckets: dict = {}
    for ts, bid, ask in ticks:
        mid = (bid + ask) / 2.0
        key = _floor_to_bucket(ts, tf_min)
        b = buckets.get(key)
        spread = (ask - bid) / pip_size
        if b is None:
            buckets[key] = {"o": mid, "h": mid, "l": mid, "c": mid,
                            "spread_sum": spread, "n": 1}
        else:
            b["h"] = max(b["h"], mid)
            b["l"] = min(b["l"], mid)
            b["c"] = mid
            b["spread_sum"] += spread
            b["n"] += 1
    out = []
    for key in sorted(buckets):
        b = buckets[key]
        out.append(BTBar(ts_open_utc=key, open=b["o"], high=b["h"], low=b["l"],
                         close=b["c"], volume=float(b["n"]),
                         spread_pips=round(b["spread_sum"] / b["n"], 3)))
    return out
