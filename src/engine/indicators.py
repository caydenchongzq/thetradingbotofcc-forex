"""Deterministic indicators for the regime gate (spec 01 §3.3) — pure functions.

Efficiency Ratio (Kaufman) measures directional efficiency: high = clean/trending,
low = chop. Wilder ATR measures volatility. Both feed the regime gate that decides
whether a breakout is worth trading.
"""

from __future__ import annotations

import math
from typing import Sequence


def efficiency_ratio(closes: Sequence[float], window: int) -> float:
    """ER = |net change over window| / sum(|bar-to-bar change|) over the window. 0..1.

    A pure trend -> ~1; pure chop -> ~0. Degenerate (no movement) -> 0 (guarded)."""
    if len(closes) < window + 1:
        return 0.0
    seg = closes[-(window + 1):]
    net = abs(seg[-1] - seg[0])
    path = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
    if path <= 0:
        return 0.0
    er = net / path
    return er if math.isfinite(er) else 0.0


def true_ranges(highs: Sequence[float], lows: Sequence[float],
                closes: Sequence[float]) -> list[float]:
    trs: list[float] = []
    for i in range(1, len(highs)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return trs


def wilder_atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
               window: int) -> float:
    """Wilder's ATR (price units). Returns 0.0 if there is not enough history."""
    trs = true_ranges(highs, lows, closes)
    if len(trs) < window:
        return 0.0
    atr = sum(trs[:window]) / window           # seed with simple average
    for tr in trs[window:]:                    # Wilder smoothing
        atr = (atr * (window - 1) + tr) / window
    return atr if math.isfinite(atr) else 0.0


def percentile_rank(value: float, series: Sequence[float]) -> float:
    """Fraction of `series` <= `value`, in [0,1]. Empty series -> 0.5 (neutral)."""
    if not series:
        return 0.5
    return sum(1 for x in series if x <= value) / len(series)
