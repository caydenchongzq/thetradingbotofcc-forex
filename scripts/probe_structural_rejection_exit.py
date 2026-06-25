"""PROBE (not a strategy, not a trial): StructuralRejectionExit on EURUSD M15.

Decision question answered BEFORE spending a trial (spec 08 §5, queue note 2026-06-20):
  "PROBE the conditional outcome of incumbent trades that close back inside the opening
   range BEFORE spending a trial."

Mechanism probed:
  After an incumbent market-fill entry (SessionBreakoutER, market entry, the −0.024R base):
    LONG trade: the strategy breaks above OR_high and enters at market.
      A bar that subsequently CLOSES below OR_high = "structural rejection" (price failed
      to hold the breakout level and re-entered the prior range).
    SHORT trade: entry below OR_low. A bar that closes ABOVE OR_low = structural rejection.
  If trades with a structural rejection bar are the confirmed losers (lower conditional
  expectancy), scratching at market when that bar closes would be SELECTIVE — it would
  cut the losers, not the winners.

Differentiation from rejected exit models (spec 08 §4.3, exit-model now 0/4):
  * Full-exit-model (2026-06-03): scaled runner + 2R tail. Rejected on lockbox.
  * TP-2R sweep (2026-06-07): geometry tail. All 18 fail DSR.
  * Follow-through time-stop (2026-06-20): ANTI-selective — cut winners because fill is
    above the level while target is anchored to the level → winners are underwater early.
    The structural rejection exit is IMMUNE to this: a winner that pulls back but holds the
    OR high is NOT closed (close < OR_high is the trigger, not "underwater by N pips").
  * Fill-anchored exit (2026-06-21): anchored stop+target to fill, regressed expectancy.
  This probe tests a DIFFERENT question: does a structural price-action event (close back
  inside the range) selectively predict ultimate loss?

Simulation:
  Re-runs the incumbent backtest inline and for each SimTrade:
    1. Computes the session's opening-range bounds (first 30 min, 13:00-13:30 London)
       from the M15 bars matching that trade's London date.
    2. Scans bars during the trade's life (entry_ts → exit_ts) for a structural-rejection bar.
    3. Classifies the trade: had_rejection=True/False.
  Then computes conditional expectancy per group.

Decision rule (a-priori, announced before results are known):
  WORTH A TRIAL if:
    trades with had_rejection have mean_R < trades without by ≥ 0.15R  AND
    had_rejection count ≥ 20 (enough to estimate conditional expectancy reliably).
  PROBE-REJECT otherwise (closes exit-model family definitively).

Run: python3 scripts/probe_structural_rejection_exit.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import EventDrivenBacktester
from src.backtest.types import BacktestRequest, WFSpec
from src.backtest.costs import CostModel
from src.common.config import load_config
from src.data.store import read_parquet_bars
from src.engine import build_strategy
from src.ops.runtime_config import resolve_strategy_config
from src.risk.governor import RiskGovernor
from src.risk.types import SymbolMeta

PARQUET = "state/parquet/eurusd_m15.parquet"
LONDON_TZ = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")
OR_MINUTES = 30           # opening range duration (matches incumbent config)
WIN_START = time(13, 0)   # London time — session window start


def run_incumbent_backtest():
    """Return (trades, bars) from the current HEAD (market-fill incumbent)."""
    cfg = load_config()
    bt = cfg.raw.get("backtest", {})
    bars = read_parquet_bars(PARQUET)
    strategy_cfg, _ = resolve_strategy_config(cfg.state_dir, cfg.raw.get("strategy", {}),
                                              cfg.config_version)

    sym = bt.get("symbol", {})
    sm = SymbolMeta(
        symbol=cfg.execution.symbol,
        pip_value_per_lot_usd=float(sym.get("pip_value_per_lot_usd", 10.0)),
        pip_size=float(sym.get("pip_size", 0.0001)),
        min_lot=float(sym.get("min_lot", 0.01)),
        max_lot=float(sym.get("max_lot", 100.0)),
        contract_size=float(sym.get("contract_size", 100_000)),
        digits=int(sym.get("digits", 5)),
    )
    gov = RiskGovernor(cfg.risk)
    cost = CostModel(
        commission_per_lot_per_side_usd=float(bt.get("commission_per_lot_per_side_usd", 3.0)),
        slippage_pips=float(bt.get("slippage_pips", 0.2)),
        pip_size=sm.pip_size,
        pip_value_per_lot_usd=sm.pip_value_per_lot_usd,
    )
    strategy = build_strategy(strategy_cfg)
    initial = float(cfg.account.initial)

    wf = WFSpec(train_months=12, test_months=3, step_months=3, lockbox_months=6)
    req = BacktestRequest(
        strategy_name=strategy_cfg.get("name", "SessionBreakoutER"),
        config_version=0,
        config=strategy_cfg,
        data_set="dev",
        period=(bars[0].ts_open_utc, bars[-1].ts_open_utc),
        walk_forward=wf,
        trial_count=1,
    )
    bt_engine = EventDrivenBacktester(strategy, gov, sm, cost,
                                      initial_balance=initial)
    report = bt_engine.run_on_bars(bars, req)
    trades = report.artifacts.get("trades", [])
    return trades, bars


def build_bar_index(bars):
    """Return a dict: ts_utc -> BTBar for fast lookup."""
    return {b.ts_open_utc: b for b in bars}


def get_or_bounds(entry_ts, bars_by_ts, all_bars_sorted_ts):
    """Compute OR high/low for the session that contains entry_ts.

    OR = max(high) / min(low) of bars from WIN_START up to WIN_START + OR_MINUTES
    on the same London calendar date as entry_ts.
    """
    entry_london = entry_ts.astimezone(LONDON_TZ)
    entry_london_date = entry_london.date()

    or_start_time = WIN_START
    from datetime import timedelta
    or_end_time = (
        (entry_london.replace(hour=WIN_START.hour, minute=WIN_START.minute,
                               second=0, microsecond=0) +
         timedelta(minutes=OR_MINUTES)).time()
    )

    or_highs, or_lows = [], []
    for ts in all_bars_sorted_ts:
        bar = bars_by_ts[ts]
        ts_london = ts.astimezone(LONDON_TZ)
        if ts_london.date() != entry_london_date:
            continue
        t = ts_london.time()
        if t >= or_start_time and t < or_end_time:
            or_highs.append(bar.high)
            or_lows.append(bar.low)

    if not or_highs:
        return None, None
    return max(or_highs), min(or_lows)


def main():
    if not Path(PARQUET).exists():
        print(f"ERROR: {PARQUET} not found."); return

    print("Running incumbent market-fill backtest to get trade list...")
    trades, bars = run_incumbent_backtest()
    print(f"  Got {len(trades)} trades from incumbent backtest.")

    bars_by_ts = build_bar_index(bars)
    all_ts = sorted(bars_by_ts.keys())

    print("Classifying trades by structural rejection...")
    results = []
    for trade in trades:
        or_high, or_low = get_or_bounds(trade.entry_ts, bars_by_ts, all_ts)
        if or_high is None:
            continue

        # Find the OR bound relevant to this trade's direction
        if trade.direction == "long":
            rejection_level = or_high   # a close BELOW this = rejection
        else:
            rejection_level = or_low    # a close ABOVE this = rejection

        had_rejection = False
        rejection_bar_num = None
        bar_count = 0

        for ts in all_ts:
            if ts < trade.entry_ts:
                continue
            if ts >= trade.exit_ts:
                break
            bar = bars_by_ts[ts]
            bar_count += 1
            if trade.direction == "long" and bar.close < rejection_level:
                had_rejection = True
                if rejection_bar_num is None:
                    rejection_bar_num = bar_count
            elif trade.direction == "short" and bar.close > rejection_level:
                had_rejection = True
                if rejection_bar_num is None:
                    rejection_bar_num = bar_count

        results.append({
            "direction": trade.direction,
            "r_multiple": trade.r_multiple,
            "exit_reason": trade.exit_reason,
            "had_rejection": had_rejection,
            "rejection_bar_num": rejection_bar_num,
        })

    df = pd.DataFrame(results)
    if df.empty:
        print("No classified trades."); return

    n_total = len(df)
    n_rej = df["had_rejection"].sum()
    n_no_rej = (~df["had_rejection"]).sum()

    print()
    print("=" * 65)
    print("PROBE: StructuralRejectionExit (close back inside OR)")
    print("=" * 65)
    print(f"  Total classified trades: {n_total}")
    print(f"  Had structural rejection: {n_rej} ({n_rej/n_total*100:.1f}%)")
    print(f"  No structural rejection:  {n_no_rej} ({n_no_rej/n_total*100:.1f}%)")
    print()

    for label, mask in [("With rejection", df["had_rejection"]),
                        ("No rejection",   ~df["had_rejection"])]:
        sub = df[mask]
        if len(sub) == 0:
            print(f"  {label}: no trades"); continue
        wins = (sub["r_multiple"] > 0).sum()
        mean_r = sub["r_multiple"].mean()
        print(f"  {label} (n={len(sub)}):")
        print(f"    Mean R:    {mean_r:+.3f}R")
        print(f"    Win rate:  {wins/len(sub)*100:.1f}%")
        print(f"    SL exits:  {(sub['exit_reason']=='sl').sum()}")
        print(f"    TP exits:  {(sub['exit_reason']=='tp').sum()}")
        print(f"    Other:     {((sub['exit_reason']!='sl')&(sub['exit_reason']!='tp')).sum()}")

    print()
    rej_r = df[df["had_rejection"]]["r_multiple"].mean() if n_rej > 0 else float("nan")
    no_rej_r = df[~df["had_rejection"]]["r_multiple"].mean() if n_no_rej > 0 else float("nan")
    delta_r = rej_r - no_rej_r

    # Distribution of when rejections occur
    if n_rej > 0:
        rej_bars = df[df["had_rejection"]]["rejection_bar_num"].dropna()
        print(f"  First rejection bar within trade (bars from entry):")
        print(f"    Median: {rej_bars.median():.0f}, Mean: {rej_bars.mean():.1f}, "
              f"Min: {rej_bars.min():.0f}, Max: {rej_bars.max():.0f}")

    print()
    print(f"  DELTA R (with_rej - no_rej): {delta_r:+.3f}R")
    print(f"  Pre-registered threshold: need delta ≤ −0.15R AND n_rej ≥ 20")
    worth = (delta_r <= -0.15 and n_rej >= 20)
    result_label = "WORTH A TRIAL" if worth else "PROBE-REJECT: exit-model family CLOSED"
    print(f"  -> {result_label}")
    print("=" * 65)


if __name__ == "__main__":
    main()
