"""SessionBreakoutERFillAnchored unit tests (research-engine candidate, spec 08, 2026-06-21).

The candidate inherits ``evaluate`` byte-for-byte (so entry SELECTION must match the incumbent
exactly) and overrides only ``_signal`` to anchor the stop and targets to the FILL instead of
the breakout LEVEL, keeping the stop-distance magnitude identical. These tests pin both the
entry identity and the fill-anchored exit geometry against the incumbent.
"""

from __future__ import annotations

from datetime import date

from src.engine.registry import build_strategy
from src.engine.strategy import SessionBreakoutER
from src.engine.strategy_fill_anchored import SessionBreakoutERFillAnchored
from src.engine.types import Direction, NoSignal, Signal
from src.risk.types import ContextBias
from tests.engine.conftest import DEFAULT_CFG, make_series

PIP = 0.0001


# ============================ registry / identity ============================
def test_registered_and_built():
    s = build_strategy({**DEFAULT_CFG, "name": "SessionBreakoutERFillAnchored"})
    assert isinstance(s, SessionBreakoutERFillAnchored)
    assert s.name == "SessionBreakoutERFillAnchored"


def test_entry_selection_matches_incumbent():
    # evaluate is inherited: same direction, same fill, same level, same entry_type, same
    # NoSignal reasons. Only the exit_plan anchor may differ.
    for kind in ("trend_up", "trend_down", "chop"):
        bars, now = make_series(date(2026, 6, 2), kind)
        inc = SessionBreakoutER(DEFAULT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
        cand = SessionBreakoutERFillAnchored(DEFAULT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
        assert type(inc) is type(cand)
        if isinstance(inc, Signal):
            assert inc.direction is cand.direction
            assert inc.entry_price == cand.entry_price
            assert inc.entry_type == cand.entry_type == "market"
            assert inc.breakout_level == cand.breakout_level
            # Same stop-distance MAGNITUDE (only the anchor changes).
            assert abs(inc.exit_plan.initial_sl_pips - cand.exit_plan.initial_sl_pips) < 1e-9
        else:
            assert isinstance(cand, NoSignal) and inc.reason == cand.reason


# ============================ fill-anchored geometry ============================
def _long_signal(cfg=DEFAULT_CFG):
    bars, now = make_series(date(2026, 6, 2), "trend_up")
    sig = SessionBreakoutERFillAnchored(cfg).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal) and sig.direction is Direction.LONG
    return sig


def _short_signal(cfg=DEFAULT_CFG):
    bars, now = make_series(date(2026, 6, 2), "trend_down")
    sig = SessionBreakoutERFillAnchored(cfg).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal) and sig.direction is Direction.SHORT
    return sig


def test_long_stop_and_target_anchor_to_fill():
    sig = _long_signal()
    entry = sig.entry_price
    sl_pips = sig.exit_plan.initial_sl_pips
    # Stop is exactly sl_pips below the FILL (not below the level).
    assert abs(sig.exit_plan.initial_sl_price - (entry - sl_pips * PIP)) < 1e-9
    # Each target is r*sl_pips above the FILL.
    for r, tgt in zip(sig.exit_plan.target_r_multiples, sig.exit_plan.targets):
        assert abs(tgt - (entry + r * sl_pips * PIP)) < 1e-9


def test_short_stop_and_target_anchor_to_fill():
    sig = _short_signal()
    entry = sig.entry_price
    sl_pips = sig.exit_plan.initial_sl_pips
    assert abs(sig.exit_plan.initial_sl_price - (entry + sl_pips * PIP)) < 1e-9
    for r, tgt in zip(sig.exit_plan.target_r_multiples, sig.exit_plan.targets):
        assert abs(tgt - (entry - r * sl_pips * PIP)) < 1e-9


def test_realised_rr_is_symmetric_from_fill():
    # The whole point: a full stop-out is exactly -1R from the fill and the 1R target is +1R
    # from the fill (true 1:1), unlike the incumbent's level-anchored sub-1:1 skew.
    sig = _long_signal()
    entry = sig.entry_price
    risk = entry - sig.exit_plan.initial_sl_price
    one_r_target = sig.exit_plan.targets[0]   # first multiple is 1.0R
    reward = one_r_target - entry
    assert sig.exit_plan.target_r_multiples[0] == 1.0
    assert abs(reward - risk) < 1e-9


def test_differs_from_incumbent_level_anchor():
    # Concrete contrast: on the same fixture the incumbent anchors to the level, the candidate
    # to the fill, so the stop/target prices must actually differ (fill is above the level here).
    bars, now = make_series(date(2026, 6, 2), "trend_up")
    inc = SessionBreakoutER(DEFAULT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    cand = SessionBreakoutERFillAnchored(DEFAULT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert inc.entry_price > inc.breakout_level          # market fill is above the long level
    assert inc.exit_plan.initial_sl_price != cand.exit_plan.initial_sl_price
    assert inc.exit_plan.targets[0] != cand.exit_plan.targets[0]
    # Incumbent's realised reward to its 1R target is SMALLER than its risk (the skew); the
    # candidate's is equal (symmetric).
    inc_risk = inc.entry_price - inc.exit_plan.initial_sl_price
    inc_reward = inc.exit_plan.targets[0] - inc.entry_price
    assert inc_reward < inc_risk
