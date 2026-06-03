"""Run an improvement-loop proposal through the deterministic gate (spec 06 §4).

Reads a proposal JSON (a versioned config diff), validates the allowed levers, runs the
candidate config through the REAL backtester + walk-forward + lockbox using the true
cumulative trial count, records the trial in the ledger, and prints the verdict. With
--approve, a PASS is promoted to a new config version (human-in-the-loop, spec 06 §6).

Usage:
    py scripts/process_proposal.py config/proposals/example.json
    py scripts/process_proposal.py config/proposals/example.json --approve
"""

from __future__ import annotations

import argparse
import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import ConfigStore, TrialLedger, approve_and_promote, iso_week, process_proposal  # noqa: E402
from src.backtest.costs import CostModel                       # noqa: E402
from src.backtest.engine import EventDrivenBacktester          # noqa: E402
from src.backtest.types import BacktestRequest, WFSpec         # noqa: E402
from src.backtest.validate import walkforward_verdict          # noqa: E402
from src.backtest.walkforward import walk_forward              # noqa: E402
from src.common.config import load_config                      # noqa: E402
from src.data.store import read_parquet_bars                   # noqa: E402
from src.engine import build_strategy                       # noqa: E402
from src.risk.governor import RiskGovernor                     # noqa: E402
from src.risk.types import SymbolMeta                          # noqa: E402


class _Result:
    def __init__(self, passed, report, wfr, verdict):
        self.passed, self.report, self.wfr, self.verdict = passed, report, wfr, verdict


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("proposal", help="path to a proposal JSON")
    ap.add_argument("--approve", action="store_true", help="promote if it PASSES")
    ap.add_argument("--data", default=None)
    ap.add_argument("--state", default=None, help="override TBOT_STATE_DIR")
    args = ap.parse_args(argv)
    if args.state:
        os.environ["TBOT_STATE_DIR"] = args.state

    cfg = load_config()
    bt = cfg.raw.get("backtest", {})
    data_path = args.data or bt.get("data_path", "state/parquet/eurusd_m15.parquet")
    if not Path(data_path).exists():
        print(f"ERROR: {data_path} not found. Run scripts/mt5_export.py first."); return 1
    bars = read_parquet_bars(data_path)

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

    base_cfg = dict(cfg.raw.get("strategy", {})); base_cfg["config_version"] = cfg.config_version
    store = ConfigStore(cfg.state_dir, base_cfg)
    ledger = TrialLedger(cfg.state_dir)
    proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))

    def backtest_fn(candidate_config: dict, trial_count: int) -> _Result:
        engine = EventDrivenBacktester(build_strategy(candidate_config),
                                       RiskGovernor(cfg.risk), sm, cost,
                                       initial_balance=cfg.account.initial)
        req = BacktestRequest(strategy_name=candidate_config.get("name", "SessionBreakoutER"),
                              config_version=candidate_config.get("config_version", 1),
                              config=candidate_config, data_set="mt5_final",
                              period=(bars[0].ts_open_utc, bars[-1].ts_open_utc),
                              walk_forward=WFSpec(12, 3, 3, lockbox_months=6),
                              trial_count=trial_count)
        report = engine.run_on_bars(bars, req)
        wfr = walk_forward(report.artifacts["trades"],
                           (bars[0].ts_open_utc, bars[-1].ts_open_utc),
                           req.walk_forward, initial=cfg.account.initial)
        verdict = walkforward_verdict(report.passed, wfr)
        return _Result(verdict.passed, report, wfr, verdict)

    period = iso_week(datetime.now(tz=timezone.utc))
    weekly_cap = int(cfg.raw.get("improvement_loop", {}).get("trial_budget_per_week", 4))
    out = process_proposal(proposal, store, ledger, backtest_fn,
                           period=period, weekly_cap=weekly_cap)

    print(f"\nProposal {proposal.get('proposal_id')} -> {out.status.upper()}")
    print(f"  parent config v{store.head_version()}  |  cumulative trials={out.trial_count} "
          f"(period {period}, cap {weekly_cap})")
    if out.reason:
        print(f"  reason: {out.reason}")
    if out.report is not None:
        r = out.report
        m = r.report.metrics
        print(f"  in-sample: trades={m['trade_count']} exp={m['expectancy_r']:+.3f}R "
              f"PF={m['profit_factor']:.2f} sharpe={m['sharpe']:.2f} breaches={r.report.ftmo['breaches']}")
        failed_gates = [n for n, g in r.report.gates.items() if not g.passed]
        if failed_gates:
            print(f"  in-sample gates FAILED: {', '.join(failed_gates)}")
        v = r.verdict
        print(f"  OOS: folds {v.folds_profitable}/{v.folds_scored} profitable, "
              f"stitched_collapse={v.stitched_collapse}, severe={v.severe_collapse}, "
              f"lockbox_ok={v.lockbox_ok}")

    if out.status == "passed" and args.approve:
        new_v = approve_and_promote(proposal, store, out.candidate_config, approver="human")
        print(f"\nPROMOTED -> config v{new_v} is now HEAD. Live box adopts at next session start.")
    elif out.status == "passed":
        print("\nPASSED. Re-run with --approve to promote (human-in-the-loop).")
    return 0 if out.status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
