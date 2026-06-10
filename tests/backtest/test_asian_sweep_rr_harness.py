"""AsianSweepFadeRR through the REAL harness (spec 08 candidate, dev-only).

Mirrors test_asian_sweep_harness but with the asymmetric 2R target — the downward drift
is extended so the short can resolve at the (further) take-profit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.common.config import RiskConfig
from src.engine.strategy_asian_sweep_rr import AsianSweepFadeRR
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.engine.test_asian_sweep import SWEEP_SHORT, with_window_bars
from tests.engine.test_asian_sweep_rr import CFG_RR

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)


def _to_bt(bars):
    return [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                  close=b.close, volume=b.volume, spread_pips=0.4) for b in bars]


def _run(sweep: bool):
    extra = [SWEEP_SHORT] if sweep else [(495, 1.0998, 1.1002, 1.0994, 1.0996)]
    eng_bars, _ = with_window_bars(extra)
    bt = _to_bt(eng_bars)
    last = bt[-1]
    px = last.close
    for k in range(1, 11):                     # drift DOWN far enough to reach the 2R target
        ts = last.ts_open_utc + timedelta(minutes=15 * k)
        px -= 0.0004
        bt.append(BTBar(ts_open_utc=ts, open=px + 0.0003, high=px + 0.0005,
                        low=px - 0.0003, close=px, spread_pips=0.4))
    engine = EventDrivenBacktester(
        AsianSweepFadeRR(CFG_RR), RiskGovernor(RiskConfig()), SM,
        CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0),
        initial_balance=100_000.0)
    req = BacktestRequest(strategy_name="AsianSweepFadeRR", config_version=0,
                          config={}, data_set="fixture",
                          period=(datetime(2026, 1, 15, tzinfo=timezone.utc),
                                  datetime(2026, 1, 16, tzinfo=timezone.utc)),
                          walk_forward=WFSpec(1, 1, 1), trial_count=1)
    return engine.run_on_bars(bt, req)


def test_sweep_day_trades_through_harness_no_breach():
    rep = _run(sweep=True)
    assert rep.metrics["trade_count"] >= 1
    assert rep.ftmo["breaches"] == 0


def test_no_sweep_day_takes_no_trade():
    rep = _run(sweep=False)
    assert rep.metrics["trade_count"] == 0
