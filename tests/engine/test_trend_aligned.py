"""TrendAlignedORB unit tests (research-engine candidate, spec 08, 2026-06-14).

Two layers: (1) the pure ``ema_slope_sign`` trend-direction helper, and (2) the strategy's
``evaluate`` veto over shared session fixtures — the key invariants being that an ALIGNED
break is byte-for-byte the incumbent (strictly-subtractive, never adds/alters a trade) while a
MIS-aligned break is vetoed to ``NoSignal``.

Summer dates: the default London window 13:00-16:00 maps to 12:00-15:00 UTC, so the 30-min
opening range is the 12:00/12:15 UTC bars (start 08:00 UTC + 16 warmup bars) and the post-OR
break runs from 12:30 UTC. The test config uses a SHORT trend EMA (window 12 / lookback 4) so a
compact fixture can carry an unambiguous slope.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.indicators import ema_slope_sign
from src.engine.registry import build_strategy
from src.engine.strategy import SessionBreakoutER
from src.engine.strategy_trend_aligned import TrendAlignedORB
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001


# ============================ pure indicator: ema_slope_sign ============================
def test_slope_up_is_plus_one():
    vals = [1.0 + 0.01 * i for i in range(40)]
    assert ema_slope_sign(vals, 12, 4) == 1


def test_slope_down_is_minus_one():
    vals = [1.0 - 0.01 * i for i in range(40)]
    assert ema_slope_sign(vals, 12, 4) == -1


def test_slope_flat_is_zero():
    vals = [1.2345] * 40
    assert ema_slope_sign(vals, 12, 4) == 0


def test_insufficient_history_is_zero():
    assert ema_slope_sign([1.0, 1.1, 1.2], 12, 4) == 0


def test_degenerate_params_fail_safe():
    vals = [1.0 + 0.01 * i for i in range(40)]
    assert ema_slope_sign(vals, 0, 4) == 0
    assert ema_slope_sign(vals, 12, 0) == 0


# ============================ strategy: evaluate veto ============================
CFG = {
    "instrument": "EURUSD", "pip_size": PIP, "timeframe_minutes": 15,
    "session": {"tz": "Europe/London", "window_start": "13:00", "window_end": "16:00",
                "opening_range_minutes": 30, "one_shot_per_side": True},
    "breakout": {"buffer_pips": 1.5},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.10, "atr_high_pct": 0.95},
    "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
    "trend_filter": {"ema_window": 12, "slope_lookback": 4},
}


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def _make(warmup_dir: int, break_dir: int, n_warmup: int = 16, step: float = 0.0004):
    """Build (warmup trending in ``warmup_dir``) -> flat opening range -> break in ``break_dir``.

    warmup_dir sets the slow-EMA slope (the trend); break_dir sets which side the incumbent
    fires. Decoupling them lets us construct an aligned case (same sign) and a mis-aligned case
    (opposite sign) while the regime gate (driven by the clean warmup trend) passes in both.
    Returns (bars_including_break, now, level).
    """
    start = datetime(2025, 6, 17, 8, 0, tzinfo=timezone.utc)
    bars = []
    base = 1.1000
    for i in range(n_warmup):                                # clean trend -> high ER
        o = base + warmup_dir * step * i
        c = o + warmup_dir * 0.0003
        hi = max(o, c) + 0.0002
        lo = min(o, c) - 0.0002
        bars.append(_bar(start + timedelta(minutes=15 * i), o, hi, lo, c))
    p = bars[-1].close                                       # session opens at the warmup's end
    or0 = start + timedelta(minutes=15 * n_warmup)           # 12:00 UTC -> 13:00 London
    # two flat opening-range bars around p (range ~ +/-4 pip)
    bars.append(_bar(or0, p, p + 4 * PIP, p - 4 * PIP, p))
    bars.append(_bar(or0 + timedelta(minutes=15), p, p + 4 * PIP, p - 4 * PIP, p))
    buf = 1.5 * PIP
    if break_dir > 0:
        lvl = (p + 4 * PIP) + buf
        bk = _bar(or0 + timedelta(minutes=30), p, p + 9 * PIP, p - 1 * PIP, p + 7 * PIP)
    else:
        lvl = (p - 4 * PIP) - buf
        bk = _bar(or0 + timedelta(minutes=30), p, p + 1 * PIP, p - 9 * PIP, p - 7 * PIP)
    bars.append(bk)
    now = bk.ts_open_utc + timedelta(minutes=10)
    return bars, now, lvl


def test_aligned_long_passes_through_identical_to_incumbent():
    """Up-trend warmup + long break: filter is aligned -> the incumbent signal, byte-for-byte."""
    bars, now, lvl = _make(warmup_dir=+1, break_dir=+1)
    base = SessionBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    cand = TrendAlignedORB(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(base, Signal) and base.direction is Direction.LONG   # fixture sanity
    assert isinstance(cand, Signal)
    assert cand.direction is base.direction
    assert cand.entry_price == base.entry_price == lvl
    assert cand.exit_plan.initial_sl_price == base.exit_plan.initial_sl_price
    assert cand.exit_plan.initial_sl_pips == base.exit_plan.initial_sl_pips
    assert cand.exit_plan.targets == base.exit_plan.targets


def test_aligned_short_passes_through_identical_to_incumbent():
    """Down-trend warmup + short break: aligned -> identical incumbent short signal."""
    bars, now, lvl = _make(warmup_dir=-1, break_dir=-1)
    base = SessionBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    cand = TrendAlignedORB(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(base, Signal) and base.direction is Direction.SHORT  # fixture sanity
    assert isinstance(cand, Signal)
    assert cand.direction is base.direction
    assert cand.entry_price == base.entry_price == lvl


def test_misaligned_long_break_in_downtrend_is_vetoed():
    """Down-trend warmup but a LONG break: incumbent fires, the filter vetoes it."""
    bars, now, _ = _make(warmup_dir=-1, break_dir=+1)
    base = SessionBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    cand = TrendAlignedORB(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(base, Signal) and base.direction is Direction.LONG   # incumbent WOULD fire
    assert isinstance(cand, NoSignal)
    assert cand.reason == "trend_misaligned"


def test_misaligned_short_break_in_uptrend_is_vetoed():
    """Up-trend warmup but a SHORT break: incumbent fires, the filter vetoes it."""
    bars, now, _ = _make(warmup_dir=+1, break_dir=-1)
    base = SessionBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    cand = TrendAlignedORB(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(base, Signal) and base.direction is Direction.SHORT
    assert isinstance(cand, NoSignal)
    assert cand.reason == "trend_misaligned"


def test_subset_invariant_never_adds_a_trade():
    """Across all four warmup/break combos, the candidate is silent whenever the incumbent is."""
    for wd in (+1, -1):
        for bd in (+1, -1):
            bars, now, _ = _make(warmup_dir=wd, break_dir=bd)
            base = SessionBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
            cand = TrendAlignedORB(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
            if isinstance(base, NoSignal):
                assert isinstance(cand, NoSignal)          # never adds a trade the incumbent skips
            if isinstance(cand, Signal):
                assert isinstance(base, Signal)            # only ever a subset
                assert cand.direction is base.direction
                assert cand.entry_price == base.entry_price


def test_warmup_bars_extended_for_slow_ema():
    strat = TrendAlignedORB(CFG)
    assert strat.warmup_bars() >= 12 + 4 + 2
    assert strat.warmup_bars() >= SessionBreakoutER(CFG).warmup_bars()


def test_stand_down_no_signal():
    bars, now, _ = _make(warmup_dir=+1, break_dir=+1)
    sig = TrendAlignedORB(CFG).evaluate(bars, now, ContextBias.STAND_DOWN, None)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "stand_down"


def test_outside_session_no_signal():
    bars, now, _ = _make(warmup_dir=+1, break_dir=+1)
    late = now.replace(hour=22)
    sig = TrendAlignedORB(CFG).evaluate(bars, late, ContextBias.NORMAL, None)
    assert isinstance(sig, NoSignal)


def test_registry_builds_by_name():
    strat = build_strategy({**CFG, "name": "TrendAlignedORB"})
    assert isinstance(strat, TrendAlignedORB)
    assert strat.name == "TrendAlignedORB"
