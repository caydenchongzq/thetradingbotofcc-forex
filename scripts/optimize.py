"""Generic parameter optimizer (spec 06 §5) — sweep a search space, rank, propose the best.

Strategy-agnostic: a spec YAML names the strategy and a search space of dotted params. Each
candidate is backtested through the REAL gated harness (in-sample gates + walk-forward); the
lockbox is held out of ranking and checked ONCE on the winner. Every candidate is judged at
a DSR trial_count equal to the sweep size (trying N configs raises the winner's bar). The
winner is written as a PROPOSAL for human approval — nothing is promoted automatically.

Usage:
    py scripts/optimize.py config/optimize/example.yaml
    py scripts/optimize.py config/optimize/example.yaml --out config/proposals/opt.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import ConfigStore, TrialLedger                 # noqa: E402
from src.agents.optimizer import (                              # noqa: E402
    apply_overrides, build_diff, enumerate_candidates, expand_grid, grid_size,
    rank, refine_space)
from src.backtest.costs import CostModel                        # noqa: E402
from src.backtest.engine import EventDrivenBacktester           # noqa: E402
from src.backtest.types import BacktestRequest, WFSpec          # noqa: E402
from src.backtest.walkforward import walk_forward               # noqa: E402
from src.common.config import load_config                       # noqa: E402
from src.data.store import read_parquet_bars                    # noqa: E402
from src.engine import build_strategy                           # noqa: E402
from src.ops.runtime_config import resolve_strategy_config      # noqa: E402
from src.risk.governor import RiskGovernor                      # noqa: E402
from src.risk.types import SymbolMeta                           # noqa: E402


def _fmt(cand: dict) -> str:
    return ",".join(f"{k.split('.')[-1]}={v}" for k, v in cand.items())


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="path to an optimizer spec YAML")
    ap.add_argument("--data", default=None)
    ap.add_argument("--state", default=None, help="override TBOT_STATE_DIR")
    ap.add_argument("--out", default=None, help="proposal JSON output path")
    ap.add_argument("--base-trials", type=int, default=0,
                    help="add to the DSR trial_count (e.g. prior cumulative trials)")
    ap.add_argument("--top", type=int, default=12, help="leaderboard rows to show")
    args = ap.parse_args(argv)
    if args.state:
        os.environ["TBOT_STATE_DIR"] = args.state

    spec = yaml.safe_load(Path(args.spec).read_text(encoding="utf-8")) or {}
    space = spec.get("space", {})
    if not space:
        print("ERROR: spec has no 'space'."); return 1
    method = spec.get("method", "grid")
    budget = int(spec.get("budget", 40))
    seed = int(spec.get("seed", 0))
    objective = spec.get("objective", "oos_expectancy")
    lockbox_months = int(spec.get("lockbox_months", 6))

    cfg = load_config()
    bt = cfg.raw.get("backtest", {})
    data_path = args.data or bt.get("data_path", "state/parquet/eurusd_m15.parquet")
    if not Path(data_path).exists():
        print(f"ERROR: {data_path} not found."); return 1
    bars = read_parquet_bars(data_path)
    period = (bars[0].ts_open_utc, bars[-1].ts_open_utc)

    sym = bt.get("symbol", {})
    sm = SymbolMeta(symbol=cfg.execution.symbol,
                    pip_value_per_lot_usd=float(sym.get("pip_value_per_lot_usd", 10.0)),
                    min_lot=float(sym.get("min_lot", 0.01)), max_lot=float(sym.get("max_lot", 50.0)),
                    lot_step=float(sym.get("lot_step", 0.01)),
                    stops_level_pips=float(sym.get("stops_level_pips", 0.0)),
                    digits=int(sym.get("digits", 5)), pip_size=float(sym.get("pip_size", 0.0001)))
    cost = CostModel(commission_per_lot_per_side_usd=float(bt.get("commission_per_lot_per_side_usd", 3.0)),
                     slippage_pips=float(bt.get("slippage_pips", 0.2)),
                     pip_size=sm.pip_size, pip_value_per_lot_usd=sm.pip_value_per_lot_usd)

    # Base config to overlay the sweep onto. 'head' = the live/promoted HEAD; or a dev YAML.
    base_spec = spec.get("base", "head")
    if base_spec in (None, "head", "HEAD"):
        base_cfg, base_ver = resolve_strategy_config(
            cfg.state_dir, cfg.raw.get("strategy", {}), cfg.config_version)
    else:
        raw_dev = yaml.safe_load(Path(base_spec).read_text(encoding="utf-8")) or {}
        base_cfg = raw_dev.get("strategy", raw_dev)
        base_ver = base_cfg.get("config_version", 0)
    if spec.get("strategy"):
        base_cfg = {**base_cfg, "name": spec["strategy"]}
    store = ConfigStore(cfg.state_dir, {**cfg.raw.get("strategy", {}),
                                        "config_version": cfg.config_version})
    head_ver = store.head_version()

    def evaluate(cand: dict, trial_count: int) -> dict:
        ccfg = apply_overrides(base_cfg, cand)
        eng = EventDrivenBacktester(build_strategy(ccfg), RiskGovernor(cfg.risk), sm, cost,
                                    initial_balance=cfg.account.initial)
        req = BacktestRequest(strategy_name=ccfg.get("name", "SessionBreakoutER"),
                              config_version=base_ver, config=ccfg, data_set="mt5_final",
                              period=period, walk_forward=WFSpec(12, 3, 3),
                              trial_count=trial_count)
        rep = eng.run_on_bars(bars, req)
        wfr = walk_forward(rep.artifacts["trades"], period,
                           WFSpec(12, 3, 3, lockbox_months=lockbox_months),
                           initial=cfg.account.initial)
        return {
            "candidate": cand, "gates_passed": rep.passed,
            "severe_collapse": wfr.severe_collapse, "stitched_collapse": wfr.stitched_collapse,
            "oos_expectancy": wfr.stitched_oos_expectancy,
            "in_sample_expectancy": rep.metrics["expectancy_r"],
            "sharpe": rep.metrics["sharpe"], "profit_factor": rep.metrics["profit_factor"],
            "trades": rep.metrics["trade_count"], "breaches": rep.ftmo["breaches"],
            "dsr": rep.overfitting["deflated_sharpe"],
            "folds": f"{wfr.folds_profitable}/{wfr.folds_scored}",
            "lockbox": wfr.lockbox_metrics,
        }

    coarse = enumerate_candidates(space, method, budget, seed)
    print(f"Optimizer | strategy={base_cfg.get('name')} | base v{base_ver} | method={method} "
          f"| full grid={grid_size(space)} | evaluating={len(coarse)} | objective={objective}")

    if method == "coarse_to_fine":
        n1 = len(coarse)
        phase1 = [evaluate(c, n1 + args.base_trials) for c in coarse]
        r1 = rank(phase1, objective) or sorted(
            (p for p in phase1 if not p["severe_collapse"]),
            key=lambda r: r[objective], reverse=True)
        if not r1:
            print("\nNo coarse candidate was even close — nothing to refine."); return 2
        center = r1[0]["candidate"]
        fine = expand_grid(refine_space(space, center))
        seen = {tuple(sorted(c.items())) for c in coarse}
        fine = [c for c in fine if tuple(sorted(c.items())) not in seen]
        total = n1 + len(fine)
        print(f"  coarse winner ~ {_fmt(center)} -> refining {len(fine)} more "
              f"(total trials={total + args.base_trials})")
        results = [evaluate(c, total + args.base_trials) for c in fine] or phase1
        trial_count = total + args.base_trials
    else:
        trial_count = len(coarse) + args.base_trials
        results = [evaluate(c, trial_count) for c in coarse]

    ranked = rank(results, objective)
    print(f"\n=== LEADERBOARD (trial_count={trial_count}; lockbox HELD OUT of ranking) ===")
    print(f"{'#':>2} {'params':<34}{'OOS_R':>8}{'IS_R':>7}{'shrp':>6}{'PF':>6}"
          f"{'trd':>5}{'folds':>7}{'DSR':>6} gates")
    shown = ranked[:args.top] if ranked else sorted(
        results, key=lambda r: r.get(objective, -9), reverse=True)[:args.top]
    for i, r in enumerate(shown, 1):
        ok = "PASS" if r["gates_passed"] and not r["severe_collapse"] and not r["stitched_collapse"] else "fail"
        print(f"{i:>2} {_fmt(r['candidate']):<34}{r['oos_expectancy']:>+8.3f}"
              f"{r['in_sample_expectancy']:>+7.3f}{r['sharpe']:>6.2f}{r['profit_factor']:>6.2f}"
              f"{r['trades']:>5}{r['folds']:>7}{r['dsr']:>6.2f} {ok}")

    if not ranked:
        print("\nNo candidate cleared the gates + walk-forward at this trial count. "
              "Nothing to propose (this is the optimizer refusing to overfit).")
        return 2

    win = ranked[0]
    lb = win["lockbox"] or {}
    print(f"\nWINNER: {_fmt(win['candidate'])}  (OOS exp {win['oos_expectancy']:+.3f}R)")
    if lb:
        lb_ok = lb["expectancy_r"] >= 0.10 and lb["profit_factor"] >= 1.3 and lb["trade_count"] >= 30
        print(f"  LOCKBOX (held out, checked once): trades={lb['trade_count']} "
              f"exp={lb['expectancy_r']:+.3f}R PF={lb['profit_factor']:.2f} "
              f"sharpe={lb['sharpe']:.2f} -> {'PASS' if lb_ok else 'FAIL'}")
        if not lb_ok:
            print("  WARNING: winner FAILS the lockbox — do NOT promote. Treat as overfit.")

    diff = build_diff(base_cfg, win["candidate"])
    proposal = {
        "proposal_id": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d-opt-%H%M%S"),
        "parent_config_version": head_ver,
        "author": "optimizer",
        "created_utc": datetime.now(tz=timezone.utc).isoformat(),
        "hypothesis": (f"Optimizer sweep ({method}, {trial_count} trials) over "
                       f"{list(space)}; best by {objective}={win['oos_expectancy']:+.3f}R "
                       f"OOS. Lockbox checked once."),
        "diff": [{"param": d.param, "from": d.from_value, "to": d.to_value} for d in diff],
        "status": "proposed",
    }
    out = Path(args.out or f"config/proposals/opt_{proposal['proposal_id']}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    print(f"\nProposal written -> {out}")
    print(f"Review, then promote (human-in-the-loop):\n  py scripts/process_proposal.py {out} --approve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
