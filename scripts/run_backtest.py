"""Run SessionBreakoutER through the event-driven harness on exported history (A4).

Reads the cleaned Parquet produced by mt5_export.py, drives the REAL strategy + REAL
Risk Governor, applies the R6 gates, and prints the verdict. This is the moment of truth:
does the edge clear every gate on out-of-sample data with ZERO FTMO breaches?

Usage:
    py scripts/run_backtest.py                       # whole dataset, trial_count=1
    py scripts/run_backtest.py --trials 12           # tighter DSR bar (cumulative trials)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.costs import CostModel                       # noqa: E402
from src.backtest.engine import EventDrivenBacktester          # noqa: E402
from src.backtest.types import BacktestRequest, WFSpec         # noqa: E402
from src.backtest.walkforward import walk_forward              # noqa: E402
from src.common.config import load_config                      # noqa: E402
from src.data.store import read_parquet_bars                   # noqa: E402
from src.engine import SessionBreakoutER                       # noqa: E402
from src.risk.governor import RiskGovernor                     # noqa: E402
from src.risk.types import SymbolMeta                          # noqa: E402


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1,
                    help="cumulative trial count (raises the deflated-Sharpe bar)")
    ap.add_argument("--data", default=None, help="override parquet path")
    ap.add_argument("--walkforward", action="store_true",
                    help="time-fold OOS stability + held-out lockbox verdict (spec 05 §7)")
    ap.add_argument("--lockbox-months", type=int, default=6)
    args = ap.parse_args(argv)

    cfg = load_config()
    bt = cfg.raw.get("backtest", {})
    data_path = args.data or bt.get("data_path", "state/parquet/eurusd_m15.parquet")
    if not Path(data_path).exists():
        print(f"ERROR: {data_path} not found. Run scripts/mt5_export.py first.")
        return 1

    bars = read_parquet_bars(data_path)
    if not bars:
        print("ERROR: no bars in dataset."); return 1
    print(f"Loaded {len(bars)} bars: {bars[0].ts_open_utc.isoformat()} "
          f"-> {bars[-1].ts_open_utc.isoformat()}")

    sym = bt.get("symbol", {})
    sm = SymbolMeta(symbol=cfg.execution.symbol,
                    pip_value_per_lot_usd=float(sym.get("pip_value_per_lot_usd", 10.0)),
                    min_lot=float(sym.get("min_lot", 0.01)),
                    max_lot=float(sym.get("max_lot", 50.0)),
                    lot_step=float(sym.get("lot_step", 0.01)),
                    stops_level_pips=float(sym.get("stops_level_pips", 0.0)),
                    digits=int(sym.get("digits", 5)),
                    pip_size=float(sym.get("pip_size", 0.0001)))
    cost = CostModel(
        commission_per_lot_per_side_usd=float(bt.get("commission_per_lot_per_side_usd", 3.0)),
        slippage_pips=float(bt.get("slippage_pips", 0.2)),
        pip_size=sm.pip_size, pip_value_per_lot_usd=sm.pip_value_per_lot_usd)

    strat_cfg = dict(cfg.raw.get("strategy", {}))
    strat_cfg["config_version"] = cfg.config_version
    strategy = SessionBreakoutER(strat_cfg)
    governor = RiskGovernor(cfg.risk)

    engine = EventDrivenBacktester(strategy, governor, sm, cost,
                                   initial_balance=cfg.account.initial)
    req = BacktestRequest(
        strategy_name=strategy.name, config_version=cfg.config_version, config=strat_cfg,
        data_set="mt5_final", period=(bars[0].ts_open_utc, bars[-1].ts_open_utc),
        walk_forward=WFSpec(12, 3, 3), trial_count=args.trials)

    rep = engine.run_on_bars(bars, req)

    print("\n================ BACKTEST REPORT ================")
    m = rep.metrics
    print(f"trades={m['trade_count']}  expectancy={m['expectancy_r']:+.3f}R  "
          f"win_rate={m['win_rate']:.1%}  PF={m['profit_factor']:.2f}")
    print(f"sharpe={m['sharpe']:.2f}  sortino={m['sortino']:.2f}  "
          f"maxDD=${m['max_drawdown_usd']:.0f}  net=${m['net_pnl_usd']:.0f}")
    print(f"FTMO: {rep.ftmo}")
    print(f"DSR={rep.overfitting['deflated_sharpe']:.3f} (trials={args.trials})")
    print("\nGATES:")
    for name, g in rep.gates.items():
        mark = "PASS" if g.passed else "FAIL"
        print(f"  [{mark}] {name:18s} value={g.value:.3f} thr={g.threshold:.3f} {g.note}")
    print("\nVERDICT (in-sample):", "PASS — clears every gate" if rep.passed
          else "FAIL — does not clear all gates")
    print("=================================================")

    if not args.walkforward:
        print("\n(Run with --walkforward for the out-of-sample stability + lockbox check.)")
        return 0 if rep.passed else 2

    # ---- Walk-forward OOS: the honest verdict ----
    trades = rep.artifacts["trades"]
    wf = WFSpec(train_months=12, test_months=3, step_months=3,
                lockbox_months=args.lockbox_months)
    wfr = walk_forward(trades, (bars[0].ts_open_utc, bars[-1].ts_open_utc), wf,
                       initial=cfg.account.initial)

    print("\n============== WALK-FORWARD (OOS) ===============")
    print(f"{'window':<25}{'trades':>7}{'exp(R)':>9}{'PF':>7}{'net$':>10}")
    for f in wfr.fold_metrics:
        pf = f["profit_factor"]
        pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"
        print(f"{f['start']+'..'+f['end']:<25}{f['trades']:>7}{f['expectancy_r']:>+9.3f}"
              f"{pf_s:>7}{f['net_pnl_usd']:>10.0f}")
    import math as _math
    maj_need = max(1, _math.ceil(0.6 * wfr.folds_scored)) if wfr.folds_scored else 1
    majority_ok = wfr.folds_profitable >= maj_need
    print(f"\nStability: {wfr.folds_profitable}/{wfr.folds_scored} scored folds profitable; "
          f"weak={wfr.weak_folds}; min fold={wfr.min_fold_expectancy:+.3f}R")
    print(f"Stitched OOS expectancy={wfr.stitched_oos_expectancy:+.3f}R vs "
          f"in-sample={wfr.in_sample_expectancy:+.3f}R "
          f"(collapse={wfr.stitched_collapse}); severe_fold={wfr.severe_collapse}")

    lb = wfr.lockbox_metrics
    if lb:
        lb_pass = (lb["expectancy_r"] >= 0.10 and lb["profit_factor"] >= 1.3
                   and lb["trade_count"] >= 30)
        print(f"\nLOCKBOX {lb['window'][0]}..{lb['window'][1]} (held out, never tuned on):")
        print(f"  trades={lb['trade_count']} exp={lb['expectancy_r']:+.3f}R "
              f"PF={lb['profit_factor']:.2f} sharpe={lb['sharpe']:.2f} "
              f"net=${lb['net_pnl_usd']:.0f}")
        print(f"  lockbox core-gates: {'PASS' if lb_pass else 'FAIL'}")
    else:
        lb_pass = True
        print("\nLOCKBOX: (none configured)")

    # Spec-aligned robustness verdict (R6 §6/§7): in-sample gates pass, no stitched-OOS
    # collapse, no SEVERE losing fold, a >=60% majority of folds profitable, lockbox holds.
    oos_ok = (rep.passed and not wfr.stitched_collapse and not wfr.severe_collapse
              and majority_ok and lb_pass)
    print("\nWALK-FORWARD VERDICT:",
          "PASS — edge holds out-of-sample" if oos_ok
          else "FAIL — does not hold up out-of-sample")
    print("  (needs: in-sample PASS, no stitched collapse, no severe fold (< -0.25R), "
          ">=60% folds profitable, lockbox PASS)")
    if wfr.weak_folds:
        print(f"  ADVISORY: {wfr.weak_folds} mildly-negative fold(s) — worth investigating "
              "(e.g. regime/seasonality), but within normal variance.")
    print("=================================================")
    return 0 if oos_ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
