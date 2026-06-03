"""Full exit model (spec 01 §3.5): scaled partials, break-even, trailing (spec 05).

R-multiple is independent of lot size, so these structural tests assert the blended R,
the leg/exit-reason breakdown, and stop trajectory with a zero-cost model for clean math.
"""

from datetime import datetime, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, WFSpec
from src.common.config import RiskConfig
from src.engine.types import (
    Bar, Direction, ExitPlan, NoSignal, RegimeState, Signal, TrailRule, VolState,
)
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.backtest.conftest import bar

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)
# Zero-cost model: TP fills land exactly on the level, so R math is exact.
ZERO_COST = CostModel(commission_per_lot_per_side_usd=0.0, slippage_pips=0.0,
                      pip_size=0.0001, pip_value_per_lot_usd=10.0)


def _req(trials=1):
    return BacktestRequest(
        strategy_name="MTL", config_version=1, config={}, data_set="fixture",
        period=(datetime(2026, 6, 2, tzinfo=timezone.utc),
                datetime(2026, 6, 3, tzinfo=timezone.utc)),
        walk_forward=WFSpec(1, 1, 1), trial_count=trials, monte_carlo_runs=0)


def _engine(strategy):
    return EventDrivenBacktester(strategy, RiskGovernor(RiskConfig()), SM, ZERO_COST,
                                 initial_balance=100_000.0)


def _regime():
    return RegimeState(er=0.5, er_threshold=0.30, atr_pips=10.0, atr_percentile=0.6,
                       vol_state=VolState.NORMAL, regime_gate_passed=True)


class MultiTargetLong:
    """Fires one long stop-breakout on `entry_idx` with a configurable exit plan."""
    name = "MTL"
    config_version = 1

    def __init__(self, *, entry=1.1000, sl=1.0980, targets, fractions,
                 move_be_after_r=None, trail=None, entry_idx=1):
        self.entry, self.sl = entry, sl
        self.targets, self.fractions = targets, fractions
        self.move_be_after_r, self.trail = move_be_after_r, trail
        self.entry_idx = entry_idx
        self._fired = False

    def warmup_bars(self):
        return 1

    def evaluate(self, bars, now_utc, context_bias, calendar):
        if self._fired or len(bars) - 1 != self.entry_idx:
            return NoSignal(now_utc, "no_setup")
        self._fired = True
        sl_pips = abs(self.entry - self.sl) / 0.0001
        return Signal(
            instrument="EURUSD", ts_decision_utc=now_utc, direction=Direction.LONG,
            entry_type="stop", entry_price=self.entry,
            exit_plan=ExitPlan(
                initial_sl_price=self.sl, initial_sl_pips=sl_pips,
                targets=tuple(self.targets),
                target_r_multiples=tuple(range(1, len(self.targets) + 1)),
                partial_fractions=tuple(self.fractions),
                move_be_after_r=self.move_be_after_r, trail=self.trail),
            regime=_regime(), session="london_ny_overlap", breakout_level=self.entry,
            entry_reason="test", context_bias=context_bias, config_version=1)

    def manage(self, open_trade, bars, now_utc):
        class _Hold:
            kind = "hold"
        return _Hold()


def _one_trade(strategy, bars):
    rep = _engine(strategy).run_on_bars(bars, _req())
    assert rep.metrics["trade_count"] == 1
    assert rep.ftmo["breaches"] == 0
    return rep.artifacts["trades"][0]


def test_partial_at_1r_then_runner_to_2r():
    """0.5 off at 1R (close-based), runner to 2R (broker TP). Blended ~1.55R."""
    s = MultiTargetLong(targets=(1.1020, 1.1040), fractions=(0.5, 0.5), move_be_after_r=1.0)
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),   # entry stop @1.1000
        bar(2, 1.1005, 1.1025, 1.1005, 1.1022),   # closes >1R -> partial 0.5 + BE
        bar(3, 1.1022, 1.1045, 1.1030, 1.1042),   # runner hits 2R @1.1040
    ]
    t = _one_trade(s, bars)
    assert abs(t.r_multiple - 1.55) < 0.1
    assert t.exit_reason.endswith("+p")            # >1 leg
    assert t.exit_reason.startswith("tp")          # final leg was the 2R target


def test_partial_then_runner_scratched_at_breakeven():
    """0.5 off at 1R, then the runner gets stopped at break-even -> small net WIN."""
    s = MultiTargetLong(targets=(1.1020, 1.1040), fractions=(0.5, 0.5), move_be_after_r=1.0)
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),
        bar(2, 1.1005, 1.1025, 1.1005, 1.1022),   # partial 0.5 + BE to 1.1000
        bar(3, 1.1015, 1.1018, 1.0998, 1.1002),   # dips to BE -> runner out at entry
    ]
    t = _one_trade(s, bars)
    assert abs(t.r_multiple - 0.55) < 0.1
    assert t.r_multiple > 0                         # locked-in partial keeps it green
    assert "be" in t.exit_reason


def test_straight_stop_is_minus_one_r():
    """Price never closes past 1R; the original stop takes the full position at -1R."""
    s = MultiTargetLong(targets=(1.1020, 1.1040), fractions=(0.5, 0.5), move_be_after_r=1.0)
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),
        bar(2, 1.1001, 1.1010, 1.0975, 1.0978),   # straight to the stop @1.0980
        bar(3, 1.0978, 1.0982, 1.0975, 1.0980),
    ]
    t = _one_trade(s, bars)
    assert abs(t.r_multiple + 1.0) < 0.1
    assert t.exit_reason == "sl"                    # single leg, no partial taken


def test_trailing_stop_locks_in_profit():
    """Single far target; a trailing stop ratchets up and exits the full size in profit."""
    trail = TrailRule(activate_after_r=1.0, step_pips=1.0, distance_pips=10.0,
                      min_seconds_between_modifies=0)
    s = MultiTargetLong(targets=(1.1100,), fractions=(1.0,), move_be_after_r=None, trail=trail)
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),
        bar(2, 1.1005, 1.1025, 1.1005, 1.1022),   # fav 1.1R -> trail sl up to 1.1012
        bar(3, 1.1018, 1.1019, 1.1008, 1.1010),   # reverses into the trailed stop
    ]
    t = _one_trade(s, bars)
    assert t.r_multiple > 0.4                       # exited ~+0.6R via the trail
    assert t.exit_reason == "sl"


def test_single_target_full_exit_unchanged():
    """Backward compat: one target, fraction 1.0, no BE -> 100% at the target (2R)."""
    s = MultiTargetLong(targets=(1.1040,), fractions=(1.0,), move_be_after_r=None)
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),
        bar(2, 1.1010, 1.1045, 1.1008, 1.1042),   # straight through the 2R target
    ]
    t = _one_trade(s, bars)
    assert abs(t.r_multiple - 2.0) < 0.1
    assert t.exit_reason == "tp"                    # single leg
