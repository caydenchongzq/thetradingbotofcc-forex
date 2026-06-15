"""LondonOpenBreakoutER unit tests (research-engine candidate, spec 08, 2026-06-15).

Verifies the ONE thing the subclass changes — the session window is forced to the London
open (08:00–11:00 London) regardless of the inherited `session` config — while everything
else (the fixed close-confirmation MARKET entry, exit geometry, degraded-path NoSignal) is
inherited byte-for-byte from SessionBreakoutER.

Summer dates (June -> BST, London = UTC+1): the London-open window 08:00–11:00 maps to
07:00–10:00 UTC, so the 30-min opening range is the 07:00/07:15 UTC bars and post-OR bars
run from 07:30 UTC. The incumbent's overlap window 13:00–16:00 London (12:00–15:00 UTC) is a
DIFFERENT time of day — the candidate must fire in the former and be silent in the latter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.registry import build_strategy
from src.engine.strategy import SessionBreakoutER
from src.engine.strategy_london_open import LondonOpenBreakoutER
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001

# Deliberately carries the HEAD/overlap session block (13:00-16:00) to prove the subclass
# OVERRIDES it to the London-open window in __init__ (isolating the session variable).
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
}


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def _series(or0_utc, n_warmup=16):
    """Trending warmup into the opening range, 2 OR bars, then a post-OR break bar that
    CLOSES above the long level. Returns (bars_incl_break, now_after_break, long_level)."""
    bars = []
    base = 1.1000
    warm_start = or0_utc - timedelta(minutes=15 * n_warmup)
    for i in range(n_warmup):                                   # trending warmup -> high ER
        ts = warm_start + timedelta(minutes=15 * i)
        o = base + 0.0003 * i
        bars.append(_bar(ts, o, o + 0.0005, o - 0.0003, o + 0.0003))
    bars.append(_bar(or0_utc, 1.1050, 1.1054, 1.1046, 1.1050))                  # OR bar 1
    bars.append(_bar(or0_utc + timedelta(minutes=15), 1.1050, 1.1053, 1.1047, 1.1051))  # OR bar 2
    lvl = 1.1054 + 1.5 * PIP                                     # long_level ~1.10555
    brk = _bar(or0_utc + timedelta(minutes=30), 1.1052, 1.1063, 1.1051, 1.1060)  # close-break
    now = brk.ts_open_utc + timedelta(minutes=10)
    return bars + [brk], now, lvl


# 07:00 UTC = 08:00 London (BST) -> inside the forced London-open window.
LONDON_OPEN_OR0 = datetime(2025, 6, 17, 7, 0, tzinfo=timezone.utc)
# 12:00 UTC = 13:00 London -> the incumbent's overlap window (candidate must be SILENT here).
OVERLAP_OR0 = datetime(2025, 6, 17, 12, 0, tzinfo=timezone.utc)


def test_forces_london_open_window():
    """Subclass overrides the inherited 13:00-16:00 session to 08:00-11:00 London."""
    strat = LondonOpenBreakoutER(CFG)
    assert (strat.win_start.hour, strat.win_start.minute) == (8, 0)
    assert (strat.win_end.hour, strat.win_end.minute) == (11, 0)
    assert strat.or_minutes == 30


def test_fires_at_london_open():
    """A close-break inside the London-open window produces a LONG market Signal."""
    bars, now, lvl = _series(LONDON_OPEN_OR0)
    sig = LondonOpenBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    # Inherits the RESTING_STOP_FIX live-faithful fill: MARKET at the confirmed close, not
    # the level (entry_price == break bar close, NOT the breakout level).
    assert sig.entry_type == "market"
    assert sig.entry_price == bars[-1].close
    assert sig.entry_price != lvl


def test_silent_in_overlap_window():
    """The same break pattern during the 13:00-16:00 overlap is OUT of the London-open
    window -> the candidate does not trade it (independent base, not the incumbent's)."""
    bars, now, _ = _series(OVERLAP_OR0)
    sig = LondonOpenBreakoutER(CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "outside_session"


def test_independent_of_incumbent_base():
    """At the London-open break the INCUMBENT (overlap window) is silent, and at the overlap
    break the CANDIDATE is silent: the two trade disjoint times of day."""
    lo_bars, lo_now, _ = _series(LONDON_OPEN_OR0)
    ov_bars, ov_now, _ = _series(OVERLAP_OR0)
    cand_lo = LondonOpenBreakoutER(CFG).evaluate(lo_bars, lo_now, ContextBias.NORMAL, None)
    base_lo = SessionBreakoutER(CFG).evaluate(lo_bars, lo_now, ContextBias.NORMAL, None)
    cand_ov = LondonOpenBreakoutER(CFG).evaluate(ov_bars, ov_now, ContextBias.NORMAL, None)
    base_ov = SessionBreakoutER(CFG).evaluate(ov_bars, ov_now, ContextBias.NORMAL, None)
    assert isinstance(cand_lo, Signal) and isinstance(base_lo, NoSignal)
    assert isinstance(base_ov, Signal) and isinstance(cand_ov, NoSignal)


def test_geometry_inherited():
    """Exit geometry is the incumbent's machinery (max(struct,1.2xATR) / single 1R / be=None)."""
    bars, now, _ = _series(LONDON_OPEN_OR0)
    strat = LondonOpenBreakoutER(CFG)
    sig = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    regime = strat._regime(bars)
    assert sig.exit_plan.initial_sl_pips >= 1.2 * regime.atr_pips - 1e-9
    assert sig.exit_plan.target_r_multiples == (1.0,)
    assert sig.exit_plan.move_be_after_r is None


def test_stand_down_no_signal():
    bars, now, _ = _series(LONDON_OPEN_OR0)
    sig = LondonOpenBreakoutER(CFG).evaluate(bars, now, ContextBias.STAND_DOWN, None)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "stand_down"


def test_tunable_via_london_open_block():
    """A standalone config may still tune the window via the dedicated `london_open` block."""
    cfg = {**CFG, "london_open": {"window_start": "09:00", "window_end": "12:00",
                                  "opening_range_minutes": 15}}
    strat = LondonOpenBreakoutER(cfg)
    assert (strat.win_start.hour, strat.win_end.hour, strat.or_minutes) == (9, 12, 15)


def test_registry_builds_by_name():
    strat = build_strategy({**CFG, "name": "LondonOpenBreakoutER"})
    assert isinstance(strat, LondonOpenBreakoutER)
    assert strat.name == "LondonOpenBreakoutER"
