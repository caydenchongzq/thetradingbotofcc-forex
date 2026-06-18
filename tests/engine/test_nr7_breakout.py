"""NR7VolatilityBreakout unit tests (research-engine candidate, spec 08, 2026-06-18).

Fixtures use a WINTER date (London == UTC) so London session times map 1:1 to UTC. Lead-in
bars chop with a cyclical true range so ATR lands MID-band (vol NORMAL); the final bar is a
*strict NR7* (its high-low range is narrower than each of the previous six). The strategy ARMS a
two-sided resting-stop OCO on that bar (``ArmSignal``), so ``evaluate`` returns an ``ArmSignal``
(not a directional ``Signal``) on the setup bar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.engine.indicators import is_narrow_range
from src.engine.registry import build_strategy
from src.engine.strategy_nr7_breakout import NR7VolatilityBreakout
from src.engine.types import ArmSignal, Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001
CENTER = 1.1000
DAY = datetime(2026, 1, 15, tzinfo=timezone.utc)  # winter: London == UTC

CFG = {
    "name": "NR7VolatilityBreakout",
    "pip_size": PIP,
    "timeframe_minutes": 15,
    "instrument": "EURUSD",
    "session": {"tz": "Europe/London", "window_start": "08:00", "window_end": "18:00"},
    "breakout": {"buffer_pips": 1.5},
    "nr7": {"lookback": 7, "entry_valid_bars": 4, "require_trend": False},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.20, "atr_high_pct": 0.90},
    "exits": {"atr_mult_sl": 1.0, "target_r_multiples": [2.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
}


def _bar(ts, o, h, l, c, vol=1000.0):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=vol, is_closed=True)


def lead_bars(n=20, start_hour=8, center=CENTER, scale=1.0):
    """``n`` M15 chop bars from ``start_hour``:00 UTC. Closes oscillate +/-3 pips (low ER); the
    high-low ranges cycle 20/12/18/14 pips (x ``scale``) so the smoothed ATR lands mid-band
    (NORMAL) at scale 1.0, or below the 4-pip floor (LOW) at a small scale."""
    range_cycle = [0.0020, 0.0012, 0.0018, 0.0014]
    bars = []
    base = DAY + timedelta(hours=start_hour)
    for i in range(n):
        ts = base + timedelta(minutes=15 * i)
        c = center + (0.0003 if i % 2 == 0 else -0.0003) * scale
        half = (range_cycle[i % len(range_cycle)] * scale) / 2.0
        bars.append(_bar(ts, center, center + half, center - half, c))
    return bars


def build_nr7(nr_range_pips=6.0, n=20, scale=1.0, center=CENTER):
    """Lead-in chop + a final STRICT NR7 bar (range ``nr_range_pips`` < every prior-6 range).
    Returns (bars, now) with ``now`` == the NR7 bar's open (matches the harness: now=bar.open)."""
    bars = lead_bars(n, scale=scale)
    last_ts = bars[-1].ts_open_utc + timedelta(minutes=15)
    half = (nr_range_pips * PIP) / 2.0
    bars.append(_bar(last_ts, center, center + half, center - half, center))
    return bars, last_ts


# ---------------------------------------------------------------- indicator
def test_is_narrow_range_true_when_strict_narrowest():
    highs = [1.10 + 0.0010] * 7
    lows = [1.10] * 6 + [1.10 + 0.0009]   # ranges: six of 10 pips, last 1 pip
    assert is_narrow_range(highs, lows, 7) is True


def test_is_narrow_range_false_on_tie():
    highs = [1.10 + 0.0010] * 7
    lows = [1.10] * 7                       # all ranges 10 pips -> last not STRICTLY narrowest
    assert is_narrow_range(highs, lows, 7) is False


def test_is_narrow_range_false_when_not_narrowest():
    highs = [1.10 + 0.0010] * 7
    lows = [1.10, 1.10, 1.10, 1.10, 1.10, 1.10 + 0.0007, 1.10 + 0.0005]  # prior 3-pip < last 5-pip
    assert is_narrow_range(highs, lows, 7) is False


def test_is_narrow_range_fail_safe():
    assert is_narrow_range([1.1], [1.0], 7) is False          # insufficient history
    assert is_narrow_range([1.1, 1.2], [1.0], 2) is False     # length mismatch
    assert is_narrow_range([1.1, 1.2, 1.3], [1.0, 1.1, 1.2], 1) is False  # lookback < 2


# ---------------------------------------------------------------- arming
def test_arms_two_sided_oco_on_nr7():
    bars, now = build_nr7()
    arm = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(arm, ArmSignal)
    assert isinstance(arm.long, Signal) and isinstance(arm.short, Signal)
    nr = bars[-1]
    buf = 1.5 * PIP
    assert arm.long.direction is Direction.LONG
    assert arm.long.entry_type == "stop"
    assert arm.long.entry_price == pytest.approx(nr.high + buf)
    assert arm.short.direction is Direction.SHORT
    assert arm.short.entry_type == "stop"
    assert arm.short.entry_price == pytest.approx(nr.low - buf)


def test_arm_expiry_is_entry_valid_bars():
    bars, now = build_nr7()
    arm = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(arm, ArmSignal)
    expected = now + timedelta(minutes=(4 + 0.5) * 15)
    assert arm.expire_utc == expected


def test_no_arm_when_not_nr7():
    # Final bar's range (20 pips) is NOT narrower than its neighbours -> no setup.
    bars, now = build_nr7(nr_range_pips=20.0)
    res = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(res, NoSignal)
    assert res.reason == "not_narrow_range"


def test_vol_state_not_normal_blocks():
    # Tiny ranges everywhere -> ATR below the 4-pip floor -> vol LOW (even though NR7 holds).
    bars, now = build_nr7(nr_range_pips=1.0, scale=0.1)
    strat = build_strategy(CFG)
    # sanity: the setup IS a narrow range, so we are blocked by the regime gate, not the NR7 check
    assert is_narrow_range([b.high for b in bars], [b.low for b in bars], 7) is True
    res = strat.evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(res, NoSignal)
    assert res.reason == "vol_state_not_normal"


def test_require_trend_gate_blocks_chop():
    cfg = {**CFG, "nr7": {"lookback": 7, "entry_valid_bars": 4, "require_trend": True}}
    bars, now = build_nr7()
    res = build_strategy(cfg).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(res, NoSignal)
    assert res.reason == "trend_gate_failed"


def test_outside_session():
    bars, _ = build_nr7()
    now = DAY + timedelta(hours=20)   # 20:00 London -> outside the 08:00-18:00 window
    res = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(res, NoSignal)
    assert res.reason == "outside_session"


def test_stand_down():
    bars, now = build_nr7()
    res = build_strategy(CFG).evaluate(bars, now, ContextBias.STAND_DOWN)
    assert isinstance(res, NoSignal)
    assert res.reason == "stand_down"


def test_insufficient_history():
    bars = lead_bars(6, start_hour=8)
    now = bars[-1].ts_open_utc + timedelta(minutes=15)
    res = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(res, NoSignal)
    assert res.reason == "insufficient_history"


# ---------------------------------------------------------------- exit geometry
def test_exit_geometry_long_leg():
    bars, now = build_nr7()
    arm = build_strategy(CFG).evaluate(bars, now, ContextBias.NORMAL)
    assert isinstance(arm, ArmSignal)
    leg = arm.long
    plan = leg.exit_plan
    entry = leg.entry_price
    atr_pips = leg.regime.atr_pips
    nr = bars[-1]
    struct_pips = (entry - nr.low) / PIP            # |long_level - nr_low|
    assert plan.initial_sl_pips == pytest.approx(max(struct_pips, 1.0 * atr_pips))
    # ATR (~16 pips) dominates the narrow NR7 structural stop (~7.5 pips) -> stop ~ 1.0 x ATR.
    assert plan.initial_sl_pips == pytest.approx(1.0 * atr_pips)
    assert plan.initial_sl_price < entry
    assert plan.target_r_multiples == (2.0,)
    assert len(plan.targets) == 1 and plan.targets[0] > entry
    rr = (plan.targets[0] - entry) / (entry - plan.initial_sl_price)
    assert rr == pytest.approx(2.0, rel=1e-6)


def test_registry_build_and_defaults():
    strat = build_strategy(CFG)
    assert isinstance(strat, NR7VolatilityBreakout)
    assert strat.name == "NR7VolatilityBreakout"
    bare = build_strategy({"name": "NR7VolatilityBreakout", "pip_size": PIP})
    assert bare.nr_lookback == 7
    assert bare.entry_valid_bars == 4
    assert bare.require_trend is False
