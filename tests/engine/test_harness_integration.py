"""A4-style: the REAL strategy validated through the REAL backtest harness (spec 01 §6)."""

from datetime import date, datetime, timedelta, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.common.config import RiskConfig
from src.engine import SessionBreakoutER
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.engine.conftest import DEFAULT_CFG, make_series

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)


def test_real_strategy_runs_through_harness_no_breach():
    eng_bars, _ = make_series(date(2026, 6, 2), "trend_up")
    # Convert to BTBars and add follow-through bars so the opened trade can resolve.
    bt = [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                close=b.close, volume=b.volume, spread_pips=0.4) for b in eng_bars]
    last = bt[-1]
    px = last.close
    for k in range(1, 6):
        ts = last.ts_open_utc + timedelta(minutes=15 * k)
        px += 0.0010
        bt.append(BTBar(ts_open_utc=ts, open=px - 0.0008, high=px + 0.0004,
                        low=px - 0.0010, close=px, spread_pips=0.4))

    bt_engine = EventDrivenBacktester(
        SessionBreakoutER(DEFAULT_CFG), RiskGovernor(RiskConfig()), SM,
        CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0), initial_balance=100_000.0)
    req = BacktestRequest(strategy_name="SessionBreakoutER", config_version=1, config={},
                          data_set="fixture",
                          period=(datetime(2026, 6, 2, tzinfo=timezone.utc),
                                  datetime(2026, 6, 3, tzinfo=timezone.utc)),
                          walk_forward=WFSpec(1, 1, 1), trial_count=1)
    rep = bt_engine.run_on_bars(bt, req)
    # The breakout fires, the Governor sizes it, a trade is recorded, and crucially the
    # FTMO simulator sees ZERO breaches (the deterministic spine end to end).
    assert rep.metrics["trade_count"] >= 1
    assert rep.ftmo["breaches"] == 0
    assert rep.gates["ftmo_no_breach"].passed
