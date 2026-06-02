"""Event-driven loop drives the REAL Strategy + RiskGovernor (spec 05 §1-§2, §11)."""

from datetime import datetime, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, WFSpec
from src.common.config import RiskConfig
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.backtest.conftest import GoLongOnceStrategy, bar

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)


def _req(trials=1):
    return BacktestRequest(
        strategy_name="GoLongOnce", config_version=1, config={}, data_set="fixture",
        period=(datetime(2026, 6, 2, tzinfo=timezone.utc),
                datetime(2026, 6, 3, tzinfo=timezone.utc)),
        walk_forward=WFSpec(1, 1, 1), trial_count=trials, monte_carlo_runs=0)


def _engine(strategy):
    return EventDrivenBacktester(strategy, RiskGovernor(RiskConfig()), SM,
                                 CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0),
                                 initial_balance=100_000.0)


def test_winning_trade_tape():
    # bar1 (idx1) fires a long at 1.1000, SL 1.0980, TP 1.1040.
    # bar2 trades up through the TP -> win; no FTMO breach.
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),
        bar(2, 1.1001, 1.1050, 1.1000, 1.1045),   # TP 1.1040 hit
        bar(3, 1.1045, 1.1048, 1.1041, 1.1043),
    ]
    rep = _engine(GoLongOnceStrategy(entry_idx=1)).run_on_bars(bars, _req())
    assert rep.metrics["trade_count"] == 1
    assert rep.ftmo["breaches"] == 0
    assert rep.metrics["net_pnl_usd"] > 0           # a winner net of costs
    assert rep.gates["ftmo_no_breach"].passed


def test_losing_trade_hits_stop_no_breach():
    bars = [
        bar(0, 1.0995, 1.1000, 1.0990, 1.0998),
        bar(1, 1.0998, 1.1002, 1.0996, 1.1000),
        bar(2, 1.1000, 1.1001, 1.0975, 1.0978),    # SL 1.0980 hit
        bar(3, 1.0978, 1.0982, 1.0975, 1.0980),
    ]
    rep = _engine(GoLongOnceStrategy(entry_idx=1)).run_on_bars(bars, _req())
    assert rep.metrics["trade_count"] == 1
    assert rep.metrics["net_pnl_usd"] < 0
    assert rep.ftmo["breaches"] == 0                # a single stop never breaches
    # r-multiple of a stop-out is about -1 (loss ~= risked amount).
    assert -1.6 < rep.metrics["expectancy_r"] < -0.5


def test_no_signal_no_trades():
    bars = [bar(i, 1.10, 1.1005, 1.0995, 1.10) for i in range(5)]
    rep = _engine(GoLongOnceStrategy(entry_idx=99)).run_on_bars(bars, _req())
    assert rep.metrics["trade_count"] == 0
    assert rep.ftmo["breaches"] == 0
