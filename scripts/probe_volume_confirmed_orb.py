"""Probe: does a tick-volume (RVOL) confirmation filter improve the incumbent's break?

Research-engine probe for 2026-06-22-volume-confirmed-orb (spec 08 stage 5, run BEFORE
spending a trial — cf. the seasonality / false-break-fade probes). It does NOT register a
strategy, run a walk-forward, or append to the trial ledger; it only answers the a-priori
triage questions the library requires for any subtractive filter on the incumbent break:

  (1) how many of the incumbent's trades survive an RVOL>=thr veto (the 200-trade-floor risk),
  (2) does the surviving subset's expectancy / PF actually improve (the anti-selection risk).

Mechanism: RVOL of the BREAK bar = volume[break] / mean(volume[prev `lookback` bars]). The
break bar is the trade's entry bar (the incumbent enters at MARKET on the confirmed close, so
entry_ts == the break bar's ts_open_utc). We re-base on the *market-fill* HEAD incumbent (its
break is the live-faithful, near-breakeven base — NOT the +0.391R level-fill artifact), per the
INDEX caveat on the incumbent-FILTER queue.

Run:  py scripts/probe_volume_confirmed_orb.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from src.backtest.costs import CostModel  # noqa: E402
from src.backtest.engine import EventDrivenBacktester  # noqa: E402
from src.backtest.types import BacktestRequest, WFSpec  # noqa: E402
from src.common.config import load_config  # noqa: E402
from src.data.store import read_parquet_bars  # noqa: E402
from src.engine import build_strategy  # noqa: E402
from src.ops.runtime_config import resolve_strategy_config  # noqa: E402
from src.risk.governor import RiskGovernor  # noqa: E402
from src.risk.types import SymbolMeta  # noqa: E402


def _stats(rs: np.ndarray):
    if len(rs) == 0:
        return 0, 0.0, 0.0, 0.0
    exp = float(rs.mean())
    win = float((rs > 0).mean())
    gain = float(rs[rs > 0].sum())
    loss = float(-rs[rs < 0].sum())
    pf = gain / loss if loss > 0 else float("inf")
    return len(rs), exp, win, pf


def main() -> int:
    cfg = load_config()
    bt = cfg.raw.get("backtest", {})
    bars = read_parquet_bars(bt.get("data_path", "state/parquet/eurusd_m15.parquet"))
    sm = SymbolMeta(symbol=cfg.execution.symbol, pip_value_per_lot_usd=10.0, min_lot=0.01,
                    max_lot=50.0, lot_step=0.01, stops_level_pips=0.0, digits=5,
                    pip_size=0.0001)
    cost = CostModel(commission_per_lot_per_side_usd=3.0, slippage_pips=0.2,
                     pip_size=0.0001, pip_value_per_lot_usd=10.0)
    strat_cfg, _ = resolve_strategy_config(cfg.state_dir, cfg.raw.get("strategy", {}),
                                           cfg.config_version)
    strat = build_strategy(strat_cfg)
    eng = EventDrivenBacktester(strat, RiskGovernor(cfg.risk), sm, cost,
                                initial_balance=cfg.account.initial)
    req = BacktestRequest(strategy_name=strat.name, config_version=cfg.config_version,
                          config=strat_cfg, data_set="probe",
                          period=(bars[0].ts_open_utc, bars[-1].ts_open_utc),
                          walk_forward=WFSpec(12, 3, 3), trial_count=1)
    trades = eng.run_on_bars(bars, req).artifacts["trades"]

    varr = np.array([b.volume for b in bars], dtype=float)
    idx = {b.ts_open_utc: i for i, b in enumerate(bars)}

    def rvol(ts, lb):
        i = idx.get(ts)
        if i is None or i < lb:
            return None
        base = varr[i - lb:i].mean()
        return varr[i] / base if base > 0 else None

    base = np.array([t.r_multiple for t in trades])
    n, exp, win, pf = _stats(base)
    print(f"BASE (market-fill HEAD incumbent): n={n} exp={exp:+.3f}R win={win:.1%} PF={pf:.2f}")
    print("(200-trade floor: a surviving subset must keep n>=200 AND lift exp>=+0.10R/PF>=1.3)")
    for lb in (20, 48, 96):
        rv = [(rvol(t.entry_ts, lb), t.r_multiple) for t in trades]
        rv = [(x, r) for x, r in rv if x is not None]
        xs = np.array([x for x, _ in rv])
        print(f"\n--- RVOL lookback={lb} bars  (dist: min {xs.min():.2f} p10 "
              f"{np.percentile(xs, 10):.2f} med {np.median(xs):.2f} "
              f"p90 {np.percentile(xs, 90):.2f} max {xs.max():.2f}) ---")
        for thr in (1.0, 1.1, 1.2, 1.3, 1.5):
            kept = np.array([r for x, r in rv if x >= thr])
            n, exp, win, pf = _stats(kept)
            print(f"  thr>={thr:.1f}: n={n:3d} exp={exp:+.3f}R win={win:.1%} PF={pf:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
