"""AsianSweepFadeRR unit tests (research-engine candidate, spec 08, 2026-06-10).

The asymmetric-R:R variant of AsianSweepFade: same sweep entry + inverted-ER gate (reused
fixtures from test_asian_sweep), but a TIGHT wick stop (1.0xATR floor) + single 2.0R target.
Tests assert the differentiated exit geometry; entry/regime behaviour is covered by the
parent's suite (inherited unchanged)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.registry import build_strategy
from src.engine.strategy_asian_sweep_rr import AsianSweepFadeRR
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

# Reuse the parent's fixtures (Asian range + window-bar helpers + sweep bars).
from tests.engine.test_asian_sweep import (
    ASIAN_HIGH, ASIAN_LOW, SWEEP_LONG, SWEEP_SHORT, with_window_bars,
)

PIP = 0.0001

CFG_RR = {
    "name": "AsianSweepFadeRR",
    "pip_size": PIP,
    "timeframe_minutes": 15,
    "fade": {"asian_start": "00:00", "asian_end": "08:00",
             "window_start": "08:00", "window_end": "12:00",
             "sweep_buffer_pips": 1.5, "wick_buffer_pips": 0.5,
             "min_asian_bars": 16, "one_shot_per_side": True},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.20, "atr_high_pct": 0.90},
    "exits": {"atr_mult_sl": 1.0, "target_r_multiples": [2.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
}


def _eval(bars, now, cfg=CFG_RR):
    return AsianSweepFadeRR(cfg).evaluate(bars, now, ContextBias.NORMAL, None)


# ---------------------------------------------------------------- exit geometry
def test_short_sweep_asymmetric_geometry():
    """SHORT fade: stop just BEYOND the sweep extreme, single target at 2R of that stop."""
    bars, now = with_window_bars([SWEEP_SHORT])
    sig = _eval(bars, now)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.SHORT
    assert sig.entry_type == "market"
    assert sig.entry_price == 1.1000
    # stop sits beyond the sweep high (1.1010) by at least the wick buffer
    assert sig.exit_plan.initial_sl_price >= 1.1010 + 0.5 * PIP - 1e-12
    assert sig.exit_plan.initial_sl_pips >= (1.1010 - 1.1000) / PIP + 0.5 - 1e-9
    # single asymmetric target at exactly 2R of the stop distance
    assert len(sig.exit_plan.targets) == 1
    rr = (sig.entry_price - sig.exit_plan.targets[0]) / PIP / sig.exit_plan.initial_sl_pips
    assert abs(rr - 2.0) < 1e-6
    assert sig.regime.regime_gate_passed and sig.regime.er < 0.30


def test_long_sweep_asymmetric_geometry_mirror():
    bars, now = with_window_bars([SWEEP_LONG])
    sig = _eval(bars, now)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.exit_plan.initial_sl_price <= 1.0984 - 0.5 * PIP + 1e-12
    rr = (sig.exit_plan.targets[0] - sig.entry_price) / PIP / sig.exit_plan.initial_sl_pips
    assert abs(rr - 2.0) < 1e-6


def test_stop_is_tighter_than_symmetric_parent():
    """The whole point: with a 1.0xATR floor (vs the parent's 1.2x) the stop is no wider
    than the parent's on the same bar, while the target is 2x further."""
    from src.engine.strategy_asian_sweep import AsianSweepFade
    parent_cfg = {**CFG_RR, "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0],
                                       "partial_fractions": [1.0], "move_be_after_r": None}}
    bars, now = with_window_bars([SWEEP_SHORT])
    rr = AsianSweepFadeRR(CFG_RR).evaluate(bars, now, ContextBias.NORMAL, None)
    par = AsianSweepFade(parent_cfg).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(rr, Signal) and isinstance(par, Signal)
    # 2R target is strictly further from entry than the parent's 1R target
    assert (rr.entry_price - rr.exit_plan.targets[0]) > (par.entry_price - par.exit_plan.targets[0])


# ---------------------------------------------------------------- inherited behaviour holds
def test_no_sweep_no_signal():
    bars, now = with_window_bars([(495, 1.0998, 1.1002, 1.0994, 1.0996)])
    ns = _eval(bars, now)
    assert isinstance(ns, NoSignal) and ns.reason == "no_sweep"


def test_widened_window_admits_late_sweep():
    """A sweep at 11:30 London is INSIDE the widened 08:00-12:00 window (parent stops 11:00)."""
    day = datetime(2026, 1, 15, tzinfo=timezone.utc)
    late_sweep = (690, 1.0999, 1.1010, 1.0997, 1.1000)   # 11:30
    bars, now = with_window_bars([late_sweep])
    sig = _eval(bars, now)
    assert isinstance(sig, Signal) and sig.direction is Direction.SHORT


def test_trending_er_blocks_fade():
    bars, now = with_window_bars([SWEEP_SHORT], trending=True)
    ns = _eval(bars, now)
    assert isinstance(ns, NoSignal) and ns.reason == "regime_gate_failed"


def test_stand_down_blocks():
    bars, now = with_window_bars([SWEEP_SHORT])
    ns = AsianSweepFadeRR(CFG_RR).evaluate(bars, now, ContextBias.STAND_DOWN, None)
    assert isinstance(ns, NoSignal) and ns.reason == "stand_down"


# ---------------------------------------------------------------- wiring
def test_registry_builds_asian_sweep_fade_rr():
    s = build_strategy({"name": "AsianSweepFadeRR"})
    assert isinstance(s, AsianSweepFadeRR) and s.name == "AsianSweepFadeRR"


def test_manage_inherited_hold_with_null_be():
    bars, now = with_window_bars([SWEEP_SHORT])
    strat = AsianSweepFadeRR(CFG_RR)
    class T:  # minimal open-trade stub
        entry_price = 1.1000; sl_price = 1.10105; direction = "short"
    assert strat.manage(T(), bars, now).kind == "hold"
