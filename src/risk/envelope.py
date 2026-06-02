"""FTMO loss-budget envelope math (spec 02 §2).

Pure functions over (balance_0000, initial, equity). No I/O, no state.
"""

from __future__ import annotations

from dataclasses import dataclass

DAILY_LOSS_PCT = 0.05   # 5% of initial, equity-checked
OVERALL_LOSS_PCT = 0.10  # 10% of initial, static


@dataclass(frozen=True)
class Envelope:
    daily_floor_equity: float
    overall_floor_equity: float
    daily_budget_usd: float
    daily_loss_used_usd: float
    daily_pct_used: float
    overall_dd_usd: float


def compute_envelope(balance_0000: float, initial: float, equity: float) -> Envelope:
    daily_floor = balance_0000 - DAILY_LOSS_PCT * initial
    overall_floor = initial - OVERALL_LOSS_PCT * initial
    daily_budget = balance_0000 - daily_floor  # == 0.05 * initial
    daily_loss_used = max(0.0, balance_0000 - equity)
    daily_pct_used = daily_loss_used / daily_budget if daily_budget > 0 else 0.0
    overall_dd = max(0.0, initial - equity)
    return Envelope(
        daily_floor_equity=daily_floor,
        overall_floor_equity=overall_floor,
        daily_budget_usd=daily_budget,
        daily_loss_used_usd=daily_loss_used,
        daily_pct_used=daily_pct_used,
        overall_dd_usd=overall_dd,
    )
