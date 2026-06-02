"""End-to-end: clean -> Parquet -> EventDrivenBacktester.run() via a data loader.

Proves the run() wiring (loader -> store -> event loop) works without a live broker.
Live data comes from scripts/mt5_export.py on the Windows host."""

from datetime import date, datetime, timedelta, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.common.config import RiskConfig
from src.data.clean import clean_bars
from src.data.store import read_parquet_bars, write_parquet
from src.engine import SessionBreakoutER
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.engine.conftest import DEFAULT_CFG, make_series

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)


def test_clean_to_parquet_to_run(tmp_path):
    eng_bars, _ = make_series(date(2026, 6, 2), "trend_up")
    bt = [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                close=b.close, volume=b.volume, spread_pips=0.4) for b in eng_bars]
    last = bt[-1]; px = last.close
    for k in range(1, 6):
        px += 0.0010
        bt.append(BTBar(ts_open_utc=last.ts_open_utc + timedelta(minutes=15 * k),
                        open=px - 0.0008, high=px + 0.0004, low=px - 0.0010,
                        close=px, spread_pips=0.4))

    cleaned, rep = clean_bars(bt, tf_min=15, pip_size=0.0001)
    assert rep.output_count == len(bt)             # clean fixture: nothing dropped
    path = write_parquet(cleaned, tmp_path / "eurusd_m15.parquet")

    engine = EventDrivenBacktester(
        SessionBreakoutER(DEFAULT_CFG), RiskGovernor(RiskConfig()), SM,
        CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0),
        initial_balance=100_000.0,
        data_loader=lambda req: read_parquet_bars(path),
    )
    req = BacktestRequest(strategy_name="SessionBreakoutER", config_version=1,
                          config={}, data_set="mt5_final",
                          period=(datetime(2026, 6, 2, tzinfo=timezone.utc),
                                  datetime(2026, 6, 3, tzinfo=timezone.utc)),
                          walk_forward=WFSpec(12, 3, 3), trial_count=1)
    report = engine.run(req)   # exercises the loader -> store -> event-loop path
    assert report.metrics["trade_count"] >= 1
    assert report.ftmo["breaches"] == 0
    assert "deflated_sharpe" in report.gates
