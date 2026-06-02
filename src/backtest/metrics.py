"""Acceptance metrics (spec 05 §6) — pure. Computed on out-of-sample trade lists.

Sharpe/Sortino are the STANDARD annualised figures: built from a daily PnL-return series
and scaled by sqrt(252), so they are comparable to the R6 thresholds (≥1.0 / ≥1.5).
Per-trade stats (expectancy R, win rate, profit factor) stay per-trade by definition.
The deflated-Sharpe inputs use the *daily* (non-annualised) Sharpe and the daily-return
count, which is the correct basis for the DSR significance test (spec 05 §8)."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta
from statistics import mean, pstdev, stdev
from typing import Sequence

from src.common.timeutil import ensure_utc

TRADING_DAYS_PER_YEAR = 252


def expectancy_r(r_multiples: Sequence[float]) -> float:
    return mean(r_multiples) if r_multiples else 0.0


def win_rate(r_multiples: Sequence[float]) -> float:
    if not r_multiples:
        return 0.0
    return sum(1 for r in r_multiples if r > 0) / len(r_multiples)


def profit_factor(pnls: Sequence[float]) -> float:
    wins = sum(p for p in pnls if p > 0)
    losses = -sum(p for p in pnls if p < 0)
    if losses <= 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def sharpe(returns: Sequence[float]) -> float:
    """Sharpe of a return series (NON-annualised). Generic helper used in tests."""
    if len(returns) < 2:
        return 0.0
    sd = stdev(returns)
    return mean(returns) / sd if sd > 0 else 0.0


def sortino(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    downside = [min(0.0, r) for r in returns]
    dd = math.sqrt(mean([d * d for d in downside]))
    return mean(returns) / dd if dd > 0 else 0.0


def max_drawdown(pnls: Sequence[float]) -> float:
    peak = cum = mdd = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    return mdd


def _skew_kurt(xs: Sequence[float]) -> tuple[float, float]:
    n = len(xs)
    if n < 3:
        return 0.0, 3.0
    m = mean(xs)
    sd = pstdev(xs)
    if sd == 0:
        return 0.0, 3.0
    skew = sum(((x - m) / sd) ** 3 for x in xs) / n
    kurt = sum(((x - m) / sd) ** 4 for x in xs) / n
    return skew, kurt


def daily_returns(trades, initial: float) -> list[float]:
    """Daily PnL-as-fraction-of-initial series, with zero-return business days filled in
    between the first and last trading day (the honest denominator for Sharpe)."""
    if not trades or initial <= 0:
        return []
    by_day: dict = defaultdict(float)
    for t in trades:
        by_day[ensure_utc(t.exit_ts).date()] += t.pnl_usd
    days = sorted(by_day)
    out: list[float] = []
    d, end = days[0], days[-1]
    while d <= end:
        if d.weekday() < 5:  # Mon–Fri
            out.append(by_day.get(d, 0.0) / initial)
        d += timedelta(days=1)
    return out


def summarize(trades, initial: float = 100_000.0) -> dict:
    """Roll a list of SimTrade into the metric dict the gates and report consume."""
    r = [t.r_multiple for t in trades]
    pnls = [t.pnl_usd for t in trades]

    rets = daily_returns(trades, initial)
    sr_daily = sharpe(rets)                         # non-annualised, for DSR
    ann = math.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe_ann = sr_daily * ann
    sortino_ann = sortino(rets) * ann
    d_skew, d_kurt = _skew_kurt(rets)

    return {
        "trade_count": len(trades),
        "expectancy_r": expectancy_r(r),
        "win_rate": win_rate(r),
        "profit_factor": profit_factor(pnls),
        "sharpe": sharpe_ann,
        "sortino": sortino_ann,
        "max_drawdown_usd": max_drawdown(pnls),
        "mean_mae_pips": mean([t.mae_pips for t in trades]) if trades else 0.0,
        "mean_mfe_pips": mean([t.mfe_pips for t in trades]) if trades else 0.0,
        "net_pnl_usd": sum(pnls),
        "n_days": len(rets),
        # DSR inputs (daily basis):
        "_sr_for_dsr": sr_daily,
        "_n_for_dsr": len(rets),
        "_skew": d_skew,
        "_kurt": d_kurt,
    }
