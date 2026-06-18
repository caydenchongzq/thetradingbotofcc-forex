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


def is_narrow_range(highs: Sequence[float], lows: Sequence[float], lookback: int) -> bool:
    """Crabel NR-k narrow-range flag: True iff the LAST bar's high-low range is *strictly*
    the narrowest of the last ``lookback`` bars (``lookback=7`` => the classic NR7).

    The economic premise (Toby Crabel, *Day Trading with Short Term Price Patterns & Opening
    Range Breakout*, 1990): an extreme single-bar volatility *contraction* tends to precede a
    volatility *expansion* (the Bollinger-squeeze intuition). The narrowest range in k bars is a
    coiled spring; the subsequent break of that bar's extreme has follow-through. We require the
    *strict* minimum (ties excluded) so the flag marks a genuine contraction, not a plateau.

    Pure function: no state, no clock, no I/O. FAIL-SAFE: a lookback < 2, length mismatch,
    insufficient history, or any non-finite/negative range -> ``False`` (callers treat False as
    "no setup" -> no trade)."""
    n = len(highs)
    if lookback < 2 or n < lookback or len(lows) != n:
        return False
    ranges = [highs[i] - lows[i] for i in range(n - lookback, n)]
    last = ranges[-1]
    if not math.isfinite(last) or last < 0:
        return False
    for r in ranges[:-1]:
        if not math.isfinite(r) or last >= r:
            return False
    return True


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


def second_entry_breakout_trigger(closes: Sequence[float], level: float,
                                  direction: str, max_entries: int) -> bool:
    """Re-break ("second attempt") opening-range breakout trigger — purely close-based.

    An *episode* is a maximal run of consecutive bars CLOSING beyond ``level`` (above for
    long, below for short); it *starts* on the first such bar (one preceded by a bar NOT
    beyond, or the very first bar). The incumbent fires on episode 1 only (one-shot per
    side). This trigger returns ``True`` when the CURRENT (last) bar *starts* a new episode
    whose ordinal index is within ``max_entries`` — i.e. it ADDS a re-break entry after price
    has closed back inside the range between episodes, without ever removing the incumbent's
    first-break entry (``max_entries = 1`` reproduces the incumbent exactly).

    Strictly additive to trade count: a later episode can only fire if an earlier one already
    did and then price closed back inside (the first attempt "failed"). Fires at most once per
    episode (on its first beyond-close), matching the incumbent's close-entry semantics.

    Pure function: no state, no clock, no I/O. Degenerate/empty input or ``max_entries < 1``
    -> ``False`` (fail safe: no trade)."""
    n = len(closes)
    if n == 0 or max_entries < 1:
        return False
    long_ = direction == "long"

    def beyond(c: float) -> bool:
        return c > level if long_ else c < level

    if not beyond(closes[-1]):
        return False                              # current bar is not a break
    if n >= 2 and beyond(closes[-2]):
        return False                              # mid-run continuation, not an episode start
    episodes = 0                                  # count episode starts up to & incl. current
    for i in range(n):
        if beyond(closes[i]) and (i == 0 or not beyond(closes[i - 1])):
            episodes += 1
    return episodes <= max_entries


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


def ema_slope_sign(values: Sequence[float], window: int, lookback: int) -> int:
    """Sign of the EMA(``window``) slope, measured over the last ``lookback`` bars.

    Returns +1 if the EMA is higher now than ``lookback`` bars ago (up-trend), -1 if lower
    (down-trend), and 0 if flat OR there is not enough history to form the comparison. Used as
    a *higher-timeframe trend* proxy on the M15 series: a slow EMA's slope over a multi-hour
    lookback summarises the prevailing drift, independent of the intraday opening-range level.

    Pure function: no state, no clock, no I/O. FAIL-SAFE: a non-positive ``lookback``/``window``
    or insufficient history -> 0 (callers treat 0 as "trend unconfirmed" -> no trade).
    """
    if window <= 0 or lookback < 1:
        return 0
    ema = ema_series(values, window)
    if len(ema) <= lookback:
        return 0
    slope = ema[-1] - ema[-1 - lookback]
    if not math.isfinite(slope):
        return 0
    if slope > 0:
        return 1
    if slope < 0:
        return -1
    return 0


def session_vwap(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
                 volumes: Sequence[float]) -> float:
    """Volume-weighted average price of the supplied (intraday session) bars.

    VWAP = sum(typical_price_i * volume_i) / sum(volume_i), with the typical price taken as
    (high + low + close) / 3. The caller passes ONLY the bars that belong to the current
    session window (anchored at the session open), so this is a cumulative *session* VWAP —
    the institutional intraday "fair value" reference that benchmarked execution flow leans
    against. Used by VWAPStretchReversion as the mean a stretched price is faded back toward.

    Pure function: no state, no clock, no I/O. FAIL-SAFE: empty input, length mismatch, or a
    non-positive total volume (e.g. a tick-volume gap) -> ``nan`` (callers treat a non-finite
    VWAP as "no usable anchor" -> NoSignal). Falling back to an unweighted mean would silently
    change the anchor's meaning, so we surface the degeneracy instead.
    """
    n = len(closes)
    if n == 0 or len(highs) != n or len(lows) != n or len(volumes) != n:
        return float("nan")
    num = 0.0
    den = 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        vol = v if (v is not None and math.isfinite(v) and v > 0) else 0.0
        typical = (h + l + c) / 3.0
        num += typical * vol
        den += vol
    if den <= 0:
        return float("nan")
    vwap = num / den
    return vwap if math.isfinite(vwap) else float("nan")
