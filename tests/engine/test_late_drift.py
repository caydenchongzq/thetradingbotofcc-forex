"""LateSessionDrift unit tests (research-engine candidate, spec 08, 2026-06-09).

Winter date (London == UTC) so the 21:00 London entry bar maps 1:1 to 21:00 UTC. The
pre-entry bars alternate two TR shapes so the ATR percentile lands mid-band (vol NORMAL)
rather than degenerate, exactly like the AsianSweepFade fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.registry import build_strategy
from src.engine.strategy_late_drift import LateSessionDrift
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001

CFG = {
    "name": "LateSessionDrift",
    "pip_size": PIP,
    "timeframe_minutes": 15,
    "drift": {"entry_time": "21:00", "hold_bars": 12,
              "atr_mult_sl": 1.5, "target_r": 1.0},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.20, "atr_high_pct": 0.90},
    "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
}

ENTRY_TS = datetime(2026, 1, 15, 21, 0, tzinfo=timezone.utc)   # 21:00 London (winter)


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def drift_bars(n_pre=20, entry_ts=ENTRY_TS):
    """`n_pre` alternating-TR bars then the entry bar that OPENS at `entry_ts` (21:00)."""
    bars = []
    start = entry_ts - timedelta(minutes=15 * n_pre)
    for i in range(n_pre):
        ts = start + timedelta(minutes=15 * i)
        if i % 2 == 0:                                   # TR ~12 pips
            bars.append(_bar(ts, 1.1000, 1.1004, 1.0992, 1.0996))
        else:                                            # TR ~8 pips
            bars.append(_bar(ts, 1.0996, 1.1002, 1.0994, 1.1000))
    bars.append(_bar(entry_ts, 1.1000, 1.1004, 1.0994, 1.1001))   # the 21:00 entry bar
    return bars


def _eval(bars, now, cfg=CFG):
    return LateSessionDrift(cfg).evaluate(bars, now, ContextBias.NORMAL, None)


# ---------------------------------------------------------------- signals
def test_long_drift_signal_geometry():
    bars = drift_bars()
    strat = LateSessionDrift(CFG)
    sig = strat.evaluate(bars, ENTRY_TS, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.entry_type == "market"
    assert sig.entry_price == bars[-1].close
    # stop is 1.5×ATR BELOW entry; single 1R target ABOVE; R:R == 1:1
    regime = strat._drift_regime(bars)
    assert sig.exit_plan.initial_sl_price < sig.entry_price
    assert abs(sig.exit_plan.initial_sl_pips - 1.5 * regime.atr_pips) < 1e-6
    assert len(sig.exit_plan.targets) == 1
    assert sig.exit_plan.targets[0] > sig.entry_price
    rr = (sig.exit_plan.targets[0] - sig.entry_price) / PIP
    assert abs(rr - sig.exit_plan.initial_sl_pips) < 1e-6
    assert sig.regime.regime_gate_passed


def test_stop_is_not_the_inherited_1_2_atr():
    """Exit geometry is this strategy's own (1.5×ATR), NOT the incumbent's 1.2×ATR."""
    bars = drift_bars()
    strat = LateSessionDrift(CFG)
    sig = strat.evaluate(bars, ENTRY_TS, ContextBias.NORMAL, None)
    regime = strat._drift_regime(bars)
    assert abs(sig.exit_plan.initial_sl_pips - 1.2 * regime.atr_pips) > 1e-6


# ---------------------------------------------------------------- rejections
def test_outside_entry_bar_no_signal():
    bars = drift_bars()
    # a bar one slot earlier (20:45) must not fire
    early = bars[:-1]
    ns = _eval(early, early[-1].ts_open_utc)
    assert isinstance(ns, NoSignal) and ns.reason == "outside_entry_bar"


def test_stand_down_blocks():
    bars = drift_bars()
    ns = LateSessionDrift(CFG).evaluate(bars, ENTRY_TS, ContextBias.STAND_DOWN, None)
    assert isinstance(ns, NoSignal) and ns.reason == "stand_down"


def test_degenerate_regime_blocks():
    """Flat (zero-TR) bars => ATR degenerate => regime gate fails (fail safe)."""
    bars = [_bar(ENTRY_TS - timedelta(minutes=15 * (20 - i)), 1.1000, 1.1000, 1.1000, 1.1000)
            for i in range(20)]
    bars.append(_bar(ENTRY_TS, 1.1000, 1.1000, 1.1000, 1.1000))
    ns = _eval(bars, ENTRY_TS)
    assert isinstance(ns, NoSignal) and ns.reason == "regime_gate_failed"


def test_insufficient_history_blocks():
    bars = drift_bars(n_pre=4)
    ns = _eval(bars, bars[-1].ts_open_utc)
    assert isinstance(ns, NoSignal) and ns.reason == "insufficient_history"


# ---------------------------------------------------------------- manage / time-box
class _T:
    def __init__(self, held):
        self.bars_held = held
        self.direction = "long"
        self.entry_price = 1.1001
        self.sl_price = 1.0986


def test_manage_time_box_closes_at_hold_bars():
    strat = LateSessionDrift(CFG)
    md = strat.manage(_T(12), drift_bars(), ENTRY_TS + timedelta(hours=3))
    assert md.kind == "close_all"


def test_manage_holds_within_night_window():
    strat = LateSessionDrift(CFG)
    md = strat.manage(_T(5), drift_bars(), ENTRY_TS + timedelta(hours=1))   # 22:00, still night
    assert md.kind == "hold"


def test_manage_backstop_closes_past_window():
    """Even below hold_bars, leaving the 21:00-23:59 night window forces a close."""
    strat = LateSessionDrift(CFG)
    md = strat.manage(_T(3), drift_bars(), ENTRY_TS + timedelta(hours=3))   # 00:00 London
    assert md.kind == "close_all"


def test_manage_no_bars_held_holds():
    strat = LateSessionDrift(CFG)
    class Bare:
        direction = "long"; entry_price = 1.10; sl_price = 1.098
    assert strat.manage(Bare(), drift_bars(), ENTRY_TS).kind == "hold"


# ---------------------------------------------------------------- wiring
def test_registry_builds_late_session_drift():
    s = build_strategy({"name": "LateSessionDrift"})
    assert isinstance(s, LateSessionDrift) and s.name == "LateSessionDrift"
