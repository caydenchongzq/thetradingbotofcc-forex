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


def compression_pct(highs: Sequence[float], lows: Sequence[float],
                    closes: Sequence[float], recent_n: int, baseline_n: int) -> float:
    """Volatility-compression percentile (Crabel-style narrow-range concept).

    Mean true range of the LAST `recent_n` bars, ranked within the distribution of the
    `baseline_n` single-bar true ranges immediately PRECEDING those recent bars.
    ~0.0 = recent vol far below baseline (compressed); ~1.0 = far above (expanded).

    FAIL-SAFE: any degenerate input (insufficient history, bad lengths, non-finite)
    returns 1.0 — callers that treat low values as a green light therefore block.
    Pure function: no state, no clock, no I/O.
    """
    if recent_n <= 0 or baseline_n <= 0:
        return 1.0
    n = len(highs)
    if n != len(lows) or n != len(closes) or n < recent_n + baseline_n + 1:
        return 1.0
    trs = true_ranges(highs, lows, closes)          # aligned to bars[1:]
    recent = trs[-recent_n:]
    baseline = trs[-(recent_n + baseline_n):-recent_n]
    if len(recent) < recent_n or len(baseline) < baseline_n:
        return 1.0
    mean_recent = sum(recent) / len(recent)
    if not math.isfinite(mean_recent):
        return 1.0
    return percentile_rank(mean_recent, baseline)


def ema_series(values: Sequence[float], window: int) -> list[float]:
    """Exponential moving average series (Wilder-independent, alpha = 2/(window+1)).

    Seeded with the simple average of the FIRST ``window`` values, then smoothed forward.
    The returned list is *right-aligned* to ``values``: ``out[-1]`` is the EMA at the last
    bar, ``out[-1-k]`` the EMA at the bar ``k`` slots before it. Length is
    ``len(values) - window + 1``.

    FAIL-SAFE: insufficient history or a non-positive window returns ``[]`` (callers must
    treat the empty result as "no signal"). Pure function: no state, no clock, no I/O.
    """
    if window <= 0 or len(values) < window:
        return []
    alpha = 2.0 / (window + 1.0)
    seed = sum(values[:window]) / window
    out = [seed]
    for v in values[window:]:
        seed = alpha * v + (1.0 - alpha) * seed
        out.append(seed)
    return [x if math.isfinite(x) else 0.0 for x in out]


def breakout_retest_trigger(highs: Sequence[float], lows: Sequence[float],
                            closes: Sequence[float], level: float,
                            direction: str) -> bool:
    """Break -> retest -> resume entry trigger for an opening-range breakout level.

    Walks the time-ordered post-opening-range bars (last element = current bar) through a
    three-state machine and returns ``True`` only when the CURRENT (last) bar completes a
    valid break-and-retest entry that has not already fired earlier in the sequence:

      LONG  : a bar CLOSES above ``level`` (break) -> a later bar's LOW returns to/through
              ``level`` (retest of broken resistance-as-support) -> a bar CLOSES back above
              ``level`` (resume). SHORT is the mirror (close below, high back to level, close
              below).

    One-shot: if the first valid entry occurs on an EARLIER bar, the function returns
    ``False`` (that trade was already taken; never re-enter the same side this session). The
    break bar itself can never be the retest/entry bar. A retest wick that closes back beyond
    the level on the SAME bar is a valid immediate entry.

    Pure function: no state, no clock, no I/O. Degenerate/empty input -> ``False`` (fail
    safe: no trade)."""
    n = len(closes)
    if n == 0 or len(highs) != n or len(lows) != n:
        return False
    long_ = direction == "long"
    state = 0  # 0 = wait-break, 1 = wait-retest, 2 = armed
    for i in range(n):
        is_last = i == n - 1
        c, h, l = closes[i], highs[i], lows[i]
        if state == 0:                                  # waiting for the break
            if (c > level) if long_ else (c < level):
                state = 1
            continue                                    # break bar is never the entry bar
        if state == 1:                                  # waiting for the retest of the level
            if (l <= level) if long_ else (h >= level):
                state = 2                               # may resume on this same bar below
        if state == 2:                                  # armed: enter on a resume close
            if (c > level) if long_ else (c < level):
                return is_last                          # True only on the current bar (1-shot)
    return False
