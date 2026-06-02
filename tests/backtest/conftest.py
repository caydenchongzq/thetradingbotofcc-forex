"""Builders + synthetic strategies for backtest tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.backtest.types import BTBar
from src.engine.types import (
    Bar, Direction, ExitPlan, NoSignal, RegimeState, Signal, VolState,
)

T0 = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


def bar(i, o, h, l, c, spread=0.4):
    return BTBar(ts_open_utc=T0 + timedelta(minutes=15 * i), open=o, high=h, low=l,
                 close=c, volume=1000, spread_pips=spread)


def _regime():
    return RegimeState(er=0.5, er_threshold=0.30, atr_pips=10.0, atr_percentile=0.6,
                       vol_state=VolState.NORMAL, regime_gate_passed=True)


class GoLongOnceStrategy:
    """Enters one long stop-breakout on bar index `entry_idx`; holds (lets SL/TP work)."""
    name = "GoLongOnce"
    config_version = 1

    def __init__(self, entry_idx=1, entry=1.1000, sl=1.0980, tp=1.1040):
        self.entry_idx, self.entry, self.sl, self.tp = entry_idx, entry, sl, tp
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
            exit_plan=ExitPlan(initial_sl_price=self.sl, initial_sl_pips=sl_pips,
                               targets=(self.tp,), target_r_multiples=(2.0,),
                               partial_fractions=(1.0,), move_be_after_r=None, trail=None),
            regime=_regime(), session="london_ny_overlap", breakout_level=self.entry,
            entry_reason="test_breakout", context_bias=context_bias, config_version=1)

    def manage(self, open_trade, bars, now_utc):
        class _Hold:
            kind = "hold"
        return _Hold()
