"""SessionBreakoutERCompression through the REAL harness (spec 08 candidate, dev-only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.common.config import RiskConfig
from src.engine.strategy_compression import SessionBreakoutERCompression
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.engine.test_compression import CFG, build_series

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)


def _to_bt(bars):
    return [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                  close=b.close, volume=b.volume, spread_pips=0.4) for b in bars]


def _run(quiet_morning: bool):
    eng_bars, _ = build_series(quiet_morning=quiet_morning)
    bt = _to_bt(eng_bars)
    last = bt[-1]
    px = last.close
    for k in range(1, 6):                       # follow-through so a trade can resolve
        ts = last.ts_open_utc + timedelta(minutes=15 * k)
        px += 0.0010
        bt.append(BTBar(ts_open_utc=ts, open=px - 0.0008, high=px + 0.0004,
                        low=px - 0.0010, close=px, spread_pips=0.4))
    engine = EventDrivenBacktester(
        SessionBreakoutERCompression(CFG), RiskGovernor(RiskConfig()), SM,
        CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0),
        initial_balance=100_000.0)
    req = BacktestRequest(strategy_name="SessionBreakoutERCompression", config_version=0,
                          config={}, data_set="fixture",
                          period=(datetime(2026, 7, 14, tzinfo=timezone.utc),
                                  datetime(2026, 7, 16, tzinfo=timezone.utc)),
                          walk_forward=WFSpec(1, 1, 1), trial_count=1)
    return engine.run_on_bars(bt, req)


def test_quiet_morning_trades_through_harness_no_breach():
    rep = _run(quiet_morning=True)
    assert rep.metrics["trade_count"] >= 1
    assert rep.ftmo["breaches"] == 0


def test_loud_morning_takes_no_trade():
    rep = _run(quiet_morning=False)
    assert rep.metrics["trade_count"] == 0
