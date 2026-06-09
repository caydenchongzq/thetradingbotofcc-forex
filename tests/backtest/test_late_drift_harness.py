"""LateSessionDrift through the REAL harness (spec 08 candidate, dev-only).

Confirms the time-boxed exit actually fires inside the event-driven engine: one entry on
the 21:00 bar, then a manage-driven close ~12 bars later (NOT an SL/TP fill), with zero
simulated FTMO breaches.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.common.config import RiskConfig
from src.engine.strategy_late_drift import LateSessionDrift
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.engine.test_late_drift import CFG, ENTRY_TS, drift_bars

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)


def _to_bt(bars):
    return [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                  close=b.close, volume=b.volume, spread_pips=0.4) for b in bars]


def _run(post_bars):
    bt = _to_bt(drift_bars())
    last = bt[-1]
    px = last.close
    for k in range(1, post_bars + 1):          # gentle up-drift; small moves, no SL/TP hit
        ts = last.ts_open_utc + timedelta(minutes=15 * k)
        px += 0.0001
        bt.append(BTBar(ts_open_utc=ts, open=px - 0.0001, high=px + 0.0002,
                        low=px - 0.0002, close=px, spread_pips=0.4))
    engine = EventDrivenBacktester(
        LateSessionDrift(CFG), RiskGovernor(RiskConfig()), SM,
        CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0),
        initial_balance=100_000.0)
    req = BacktestRequest(strategy_name="LateSessionDrift", config_version=0,
                          config={}, data_set="fixture",
                          period=(ENTRY_TS - timedelta(days=1), ENTRY_TS + timedelta(days=1)),
                          walk_forward=WFSpec(1, 1, 1), trial_count=1)
    return engine.run_on_bars(bt, req)


def test_drift_day_trades_and_time_box_closes():
    rep = _run(post_bars=16)
    assert rep.metrics["trade_count"] == 1
    trades = rep.artifacts["trades"]
    assert trades[0].exit_reason == "manage_close"     # time-box, not SL/TP/eod
    assert rep.ftmo["breaches"] == 0


def test_only_one_entry_per_day():
    rep = _run(post_bars=20)
    assert rep.metrics["trade_count"] == 1             # one-shot/day (evaluate only when flat)
