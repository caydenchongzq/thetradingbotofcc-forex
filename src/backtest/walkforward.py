"""Walk-forward / out-of-sample validation (spec 05 §7) — pure.

For a fixed-config run the meaningful robustness checks are:
  * a held-out LOCKBOX (most recent window) that still clears the core gates;
  * per-fold CONSISTENCY — a strong majority of folds positive and no SEVERE losing fold
    (normal variance, e.g. a -0.06R quarter, is not a failure);
  * NO STITCHED-OOS COLLAPSE — stitched out-of-sample expectancy stays >= a fraction of
    in-sample (the R6 §6 definition).

When the improvement loop later fits params per window, the same split becomes a true
in-sample/out-of-sample test and the lockbox is what the agents must never see."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.common.timeutil import ensure_utc

from .metrics import summarize
from .types import WFSpec


def add_months(dt: datetime, months: int) -> datetime:
    m = dt.month - 1 + months
    year = dt.year + m // 12
    month = m % 12 + 1
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass
class Split:
    dev_folds: list           # list[(start, end)]
    lockbox: tuple | None     # (start, end) or None


def make_splits(period: tuple[datetime, datetime], wf: WFSpec) -> Split:
    start, end = ensure_utc(period[0]), ensure_utc(period[1])
    lockbox = None
    dev_end = end
    if wf.lockbox_months > 0:
        lockbox_start = add_months(end, -wf.lockbox_months)
        if lockbox_start > start:
            lockbox = (lockbox_start, end)
            dev_end = lockbox_start
    folds = []
    step = max(1, wf.test_months)
    t = start
    while t < dev_end:
        nxt = add_months(t, step)
        folds.append([t, min(nxt, dev_end)])
        t = nxt
    # Merge a trailing stub fold (< ~half a test window) into the previous fold so a
    # boundary artifact isn't scored as if it were a full period.
    if len(folds) >= 2:
        last_days = (folds[-1][1] - folds[-1][0]).days
        if last_days < step * 20:   # ~20 days/month heuristic
            folds[-2][1] = folds[-1][1]
            folds.pop()
    return Split(dev_folds=[(a, b) for a, b in folds], lockbox=lockbox)


def _trades_in(trades, window):
    lo, hi = window
    return [t for t in trades if lo <= ensure_utc(t.entry_ts) < hi]


@dataclass
class WalkForwardResult:
    fold_metrics: list = field(default_factory=list)
    lockbox_metrics: dict | None = None
    folds_total: int = 0
    folds_scored: int = 0
    folds_profitable: int = 0
    weak_folds: int = 0           # scored folds with expectancy <= 0 (advisory)
    min_fold_expectancy: float = 0.0
    severe_collapse: bool = False  # a scored fold worse than the severe floor
    stitched_collapse: bool = False  # stitched OOS < floor_frac * in-sample
    in_sample_expectancy: float = 0.0
    stitched_oos_expectancy: float = 0.0


def walk_forward(trades, period, wf: WFSpec, initial: float,
                 min_fold_trades: int = 15, floor_frac: float = 0.5,
                 severe_fold_floor_r: float = -0.25) -> WalkForwardResult:
    """Bucket trades into dev folds + lockbox and assess robustness.

    - ``floor_frac``: stitched OOS expectancy must stay >= floor_frac * in-sample.
    - ``severe_fold_floor_r``: no scored fold may be worse than this (catastrophic regime).
    """
    split = make_splits(period, wf)
    overall = summarize(trades, initial)
    res = WalkForwardResult(folds_total=len(split.dev_folds),
                            in_sample_expectancy=overall["expectancy_r"])

    expectancies = []
    dev_trades = []
    for w in split.dev_folds:
        ft = _trades_in(trades, w)
        m = summarize(ft, initial)
        res.fold_metrics.append({
            "start": w[0].date().isoformat(), "end": w[1].date().isoformat(),
            "trades": m["trade_count"], "expectancy_r": m["expectancy_r"],
            "profit_factor": m["profit_factor"], "net_pnl_usd": m["net_pnl_usd"],
        })
        dev_trades += ft
        if m["trade_count"] >= min_fold_trades:
            res.folds_scored += 1
            expectancies.append(m["expectancy_r"])
            if m["expectancy_r"] > 0:
                res.folds_profitable += 1
            else:
                res.weak_folds += 1
            if m["expectancy_r"] < severe_fold_floor_r:
                res.severe_collapse = True

    res.min_fold_expectancy = min(expectancies) if expectancies else 0.0
    stitched = summarize(dev_trades, initial)
    res.stitched_oos_expectancy = stitched["expectancy_r"]
    res.stitched_collapse = (overall["expectancy_r"] > 0
                             and stitched["expectancy_r"] < floor_frac * overall["expectancy_r"])
    if split.lockbox is not None:
        res.lockbox_metrics = summarize(_trades_in(trades, split.lockbox), initial)
        res.lockbox_metrics["window"] = (split.lockbox[0].date().isoformat(),
                                         split.lockbox[1].date().isoformat())
    return res
