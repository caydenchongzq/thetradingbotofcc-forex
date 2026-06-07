"""A/B: incumbent HEAD (SessionBreakoutER) vs + pre-session compression filter.

Same data, same governor/costs, same exits — the ONLY difference is the candidate's
Crabel-style quiet-morning entry filter (research engine, 2026-06-07). Template:
scripts/compare_exits.py.  Run:  py scripts/compare_compression.py
"""
from __future__ import annotations
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.costs import CostModel
from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, WFSpec
from src.backtest.walkforward import walk_forward
from src.common.config import load_config
from src.data.store import read_parquet_bars
from src.ops.runtime_config import resolve_strategy_config
from src.engine import build_strategy
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta

cfg = load_config()
bt = cfg.raw.get("backtest", {})
bars = read_parquet_bars(bt.get("data_path", "state/parquet/eurusd_m15.parquet"))
sym = bt.get("symbol", {})
sm = SymbolMeta(symbol=cfg.execution.symbol,
                pip_value_per_lot_usd=float(sym.get("pip_value_per_lot_usd", 10.0)),
                min_lot=float(sym.get("min_lot", 0.01)), max_lot=float(sym.get("max_lot", 50.0)),
                lot_step=float(sym.get("lot_step", 0.01)),
                stops_level_pips=float(sym.get("stops_level_pips", 0.0)),
                digits=int(sym.get("digits", 5)), pip_size=float(sym.get("pip_size", 0.0001)))
cost = CostModel(
    commission_per_lot_per_side_usd=float(bt.get("commission_per_lot_per_side_usd", 3.0)),
    slippage_pips=float(bt.get("slippage_pips", 0.2)),
    pip_size=sm.pip_size, pip_value_per_lot_usd=sm.pip_value_per_lot_usd)
base_cfg, ver = resolve_strategy_config(cfg.state_dir, cfg.raw.get("strategy", {}), cfg.config_version)
initial = cfg.account.initial
period = (bars[0].ts_open_utc, bars[-1].ts_open_utc)

def run(label, strat_cfg):
    strategy = build_strategy(strat_cfg)
    eng = EventDrivenBacktester(strategy, RiskGovernor(cfg.risk), sm, cost, initial_balance=initial)
    req = BacktestRequest(strategy_name=strategy.name, config_version=cfg.config_version,
                          config=strat_cfg, data_set="mt5_final", period=period,
                          walk_forward=WFSpec(12, 3, 3), trial_count=1)
    rep = eng.run_on_bars(bars, req)
    m = rep.metrics
    wf = walk_forward(rep.artifacts["trades"], period,
                      WFSpec(12, 3, 3, lockbox_months=6), initial=initial)
    lb = wf.lockbox_metrics or {}
    print("\n===== %s =====" % label)
    print("in-sample : trades=%d exp=%+.3fR win=%.1f%% PF=%.2f sharpe=%.2f sortino=%.2f maxDD=$%.0f net=$%.0f" % (
        m['trade_count'], m['expectancy_r'], m['win_rate']*100, m['profit_factor'],
        m['sharpe'], m['sortino'], m['max_drawdown_usd'], m['net_pnl_usd']))
    print("gates     : %s | breaches=%d" % ('PASS' if rep.passed else 'FAIL', rep.ftmo['breaches']))
    print("walk-fwd  : stitched OOS=%+.3fR folds %d/%d prof, weak=%d, min=%+.3fR, collapse=%s/%s" % (
        wf.stitched_oos_expectancy, wf.folds_profitable, wf.folds_scored, wf.weak_folds,
        wf.min_fold_expectancy, wf.stitched_collapse, wf.severe_collapse))
    if lb:
        print("lockbox   : trades=%d exp=%+.3fR PF=%.2f sharpe=%.2f net=$%.0f" % (
            lb['trade_count'], lb['expectancy_r'], lb['profit_factor'], lb['sharpe'], lb['net_pnl_usd']))

print("Loaded %d bars | config HEAD v%d | initial $%.0f" % (len(bars), ver, initial))
run("INCUMBENT — SessionBreakoutER (HEAD)", copy.deepcopy(base_cfg))
cand = copy.deepcopy(base_cfg)
cand["name"] = "SessionBreakoutERCompression"
cand["compression"] = {"recent_bars": 20, "baseline_bars": 60, "max_pct": 0.50}
run("CANDIDATE — + pre-session compression filter (20/60, median cut)", cand)
