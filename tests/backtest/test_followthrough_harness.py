"""SessionBreakoutERFollowThrough through the REAL harness (spec 08 candidate, dev-only).

Drives one incumbent LONG break, then holds price UNDERWATER (below entry, above the far stop,
below the 1R target) for several bars. The incumbent would carry that trade to the session
close ("eod"); the follow-through overlay must instead SCRATCH it at market once the time
window elapses ("manage_close"). The A/B on the identical fixture isolates the overlay.
"""

from __future__ import annotations

from datetime import date, timedelta, timezone

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.common.config import RiskConfig
from src.engine.registry import build_strategy
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta
from tests.engine.conftest import DEFAULT_CFG, make_series

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)
FT_CFG = {**DEFAULT_CFG, "follow_through": {"time_stop_bars": 4, "min_progress_r": 0.0}}


def _to_bt(bars):
    return [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                  close=b.close, volume=b.volume, spread_pips=0.4) for b in bars]


def _fixture():
    """Incumbent long-break bars + 8 underwater-and-flat post bars (~1.1060)."""
    eng_bars, _ = make_series(date(2026, 6, 2), "trend_up")
    bt = _to_bt(eng_bars)
    last = bt[-1]
    for k in range(1, 9):
        ts = last.ts_open_utc + timedelta(minutes=15 * k)
        # close 1.1060 sits below the ~1.1064 entry (underwater) but well inside [SL 1.1045,
        # TP 1.1070]; range stays inside that band so no broker stop/target fires.
        bt.append(BTBar(ts_open_utc=ts, open=1.1060, high=1.1063, low=1.1056,
                        close=1.1060, spread_pips=0.4))
    return bt


def _run(strategy_name, config):
    bt = _fixture()
    engine = EventDrivenBacktester(
        build_strategy({**config, "name": strategy_name}), RiskGovernor(RiskConfig()), SM,
        CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0), initial_balance=100_000.0)
    req = BacktestRequest(strategy_name=strategy_name, config_version=0, config=config,
                          data_set="fixture",
                          period=(bt[0].ts_open_utc, bt[-1].ts_open_utc + timedelta(minutes=15)),
                          walk_forward=WFSpec(1, 1, 1), trial_count=1)
    return engine.run_on_bars(bt, req)


def test_overlay_scratches_the_stalled_break():
    rep = _run("SessionBreakoutERFollowThrough", FT_CFG)
    trades = rep.artifacts["trades"]
    assert len(trades) == 1
    assert "manage_close" in trades[0].exit_reason
    assert trades[0].r_multiple < 0          # scratched at a small loss, not a full -1R
    assert rep.ftmo["breaches"] == 0


def test_incumbent_holds_the_same_fixture():
    # Same bars, no overlay: the incumbent must NOT scratch (carries to eod / session close).
    rep = _run("SessionBreakoutER", DEFAULT_CFG)
    trades = rep.artifacts["trades"]
    assert len(trades) == 1
    assert "manage_close" not in trades[0].exit_reason
