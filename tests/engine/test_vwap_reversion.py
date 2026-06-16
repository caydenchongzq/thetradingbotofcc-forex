"""VWAPStretchReversion unit tests (research-engine candidate, spec 08, 2026-06-16).

Fixtures use a WINTER date (London == UTC) so London session times map 1:1 to UTC.
Bars chop (oscillating closes) so ER stays low (the inverted ranging gate passes); the true
ranges cycle so the ATR percentile lands mid-band (vol NORMAL). The bar immediately before the
stretch is forced to close OPPOSITE the stretch direction, so the stretch reads as a reversal
(keeps ER low for both sides). The final bar is pushed N pips beyond the session VWAP.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from src.engine.indicators import session_vwap
from src.engine.registry import build_strategy
from src.engine.strategy_vwap_reversion import VWAPStretchReversion
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001
CENTER = 1.1000

CFG = {
    "name": "VWAPStretchReversion",
    "pip_size": PIP,
    "timeframe_minutes": 15,
    "instrument": "EURUSD",
    "vwap": {"anchor": "08:00", "window_start": "08:00", "window_end": "16:00",
             "min_session_bars": 8, "stretch_atr_mult": 1.0},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.20, "atr_high_pct": 0.90},
    "exits": {"atr_mult_sl": 1.0, "target_r_multiples": [1.5],
              "partial_fractions": [1.0], "move_be_after_r": None},
}

DAY = datetime(2026, 1, 15, tzinfo=timezone.utc)  # winter: London == UTC


def _bar(ts, o, h, l, c, vol=1000.0):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=vol, is_closed=True)


def chop_bars(n, start_hour=4, center=CENTER):
    """n M15 chop bars from ``start_hour``:00 UTC. Closes oscillate +/-2 pips (low ER); the
    true ranges cycle 16/8/14/10 pips so the smoothed ATR (~12 pips) lands MID-band
    (percentile inside [0.20, 0.90] => vol NORMAL); typical price stays ~center => VWAP~center."""
    tr_cycle = [0.0020, 0.0012, 0.0018, 0.0014]
    bars = []
    base = DAY + timedelta(hours=start_hour)
    for i in range(n):
        ts = base + timedelta(minutes=15 * i)
        c = center + (0.0005 if i % 2 == 0 else -0.0005)
        half = tr_cycle[i % len(tr_cycle)] / 2.0
        bars.append(_bar(ts, center, center + half, center - half, c))
    return bars


def build(stretch_pips, side="up", n_pre=16, n_sess=10, vol=1000.0, prev_stretched=False):
    """Pre-session chop + ``n_sess`` session chop bars from 08:00, then a final bar pushed
    ``stretch_pips`` beyond the session VWAP on ``side``. Returns (bars, now, vwap)."""
    pre = chop_bars(n_pre, start_hour=4)
    sess = chop_bars(n_sess, start_hour=8)
    bars = pre + sess
    vwap = session_vwap([b.high for b in sess], [b.low for b in sess],
                        [b.close for b in sess], [b.volume for b in sess])
    last_ts = bars[-1].ts_open_utc + timedelta(minutes=15)
    if side == "up":
        c = vwap + stretch_pips * PIP
        h, l = c + 0.0001, vwap - 0.0001
        opp_close = vwap - 0.0002
    else:
        c = vwap - stretch_pips * PIP
        h, l = vwap + 0.0001, c - 0.0001
        opp_close = vwap + 0.0002
    p = bars[-1]
    if prev_stretched:
        # prior in-window bar ALREADY beyond the band (same side) => current is not fresh
        if side == "up":
            bars[-1] = _bar(p.ts_open_utc, p.open, c + 0.0001, p.low, c, vol)
        else:
            bars[-1] = _bar(p.ts_open_utc, p.open, p.high, c - 0.0001, c, vol)
    else:
        # prior bar closes OPPOSITE the stretch (a reversal) => keeps ER low for both sides
        bars[-1] = _bar(p.ts_open_utc, p.open, p.high, p.low, opp_close, vol)
    bars.append(_bar(last_ts, vwap, h, l, c, vol))
    now = last_ts + timedelta(minutes=15)
    return bars, now, vwap


# ---------------------------------------------------------------- indicator
def test_session_vwap_basic():
    h = [1.1010, 1.1030]
    l = [1.0990, 1.1010]
    c = [1.1000, 1.1020]
    v = [100.0, 100.0]
    tp0, tp1 = (sum(x) / 3 for x in zip(h, l, c))
    expect = (tp0 + tp1) / 2
    assert session_vwap(h, l, c, v) == pytest.approx(expect)


def test_session_vwap_volume_weighting():
    h, l, c = [1.10, 1.20], [1.10, 1.20], [1.10, 1.20]
    assert session_vwap(h, l, c, [3.0, 1.0]) == pytest.approx((1.10 * 3 + 1.20 * 1) / 4)


def test_session_vwap_degenerate():
    assert math.isnan(session_vwap([], [], [], []))
    assert math.isnan(session_vwap([1.1], [1.1], [1.1], [0.0]))
    assert math.isnan(session_vwap([1.1, 1.2], [1.1], [1.1], [1.0]))


# ---------------------------------------------------------------- entries
def test_fires_short_on_up_stretch():
    bars, now, vwap = build(stretch_pips=20, side="up")
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.SHORT
    assert sig.entry_type == "market"
    assert sig.entry_price == pytest.approx(bars[-1].close)
    assert sig.entry_price > vwap


def test_fires_long_on_down_stretch():
    bars, now, vwap = build(stretch_pips=20, side="down")
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.entry_price == pytest.approx(bars[-1].close)
    assert sig.entry_price < vwap


def test_no_signal_when_not_stretched():
    bars, now, _ = build(stretch_pips=3, side="up")
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "no_stretch"


def test_fresh_trigger_only():
    bars, now, _ = build(stretch_pips=20, side="up", prev_stretched=True)
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "stretch_not_fresh"


def test_regime_gate_blocks_when_trending():
    bars = []
    base = DAY + timedelta(hours=4)
    for i in range(28):
        ts = base + timedelta(minutes=15 * i)
        o = 1.1000 + 0.0004 * i
        bars.append(_bar(ts, o, o + 0.0005, o - 0.0001, o + 0.0004))
    now = bars[-1].ts_open_utc + timedelta(minutes=15)
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "regime_gate_failed"


def test_outside_session():
    bars, _, _ = build(stretch_pips=20, side="up")
    now = DAY + timedelta(hours=20)
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "outside_session"


def test_building_session_vwap():
    bars, now, _ = build(stretch_pips=20, side="up", n_sess=3)
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "building_session_vwap"


def test_stand_down():
    bars, now, _ = build(stretch_pips=20, side="up")
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.STAND_DOWN)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "stand_down"


def test_insufficient_history():
    bars = chop_bars(4, start_hour=8)
    now = bars[-1].ts_open_utc + timedelta(minutes=15)
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "insufficient_history"


# ---------------------------------------------------------------- exit geometry
def test_exit_geometry_short():
    bars, now, vwap = build(stretch_pips=20, side="up")
    sig = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(sig, Signal)
    plan = sig.exit_plan
    entry = sig.entry_price
    assert plan.initial_sl_price > entry
    atr_pips = sig.regime.atr_pips
    struct_pips = (bars[-1].high - entry) / PIP
    assert plan.initial_sl_pips == pytest.approx(max(struct_pips, 1.0 * atr_pips))
    assert plan.target_r_multiples == (1.5,)
    assert len(plan.targets) == 1 and plan.targets[0] < entry
    rr = (entry - plan.targets[0]) / (plan.initial_sl_price - entry)
    assert rr == pytest.approx(1.5, rel=1e-6)


def test_registry_build():
    strat = build_strategy(CFG)
    assert isinstance(strat, VWAPStretchReversion)
    assert strat.name == "VWAPStretchReversion"
    assert build_strategy({"name": "VWAPStretchReversion", "pip_size": PIP}).stretch_atr_mult == 1.5
