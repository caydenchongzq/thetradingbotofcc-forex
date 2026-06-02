"""FTMO rule simulation (spec 05 §5) — the hard, binary gate.

Tracks, bar by bar, the same floors the live Risk Governor enforces, with the 00:00
CE(S)T reset of balance_0000. ANY crossing of a floor is a breach; a strategy/config
with any simulated breach is rejected outright."""

from __future__ import annotations

from src.risk.envelope import compute_envelope


class FtmoTracker:
    def __init__(self, initial: float, balance_0000: float):
        self.initial = initial
        self.balance_0000 = balance_0000
        self.breaches = 0
        self.breached = False
        self.worst_daily_loss_usd = 0.0
        self.worst_overall_dd_usd = 0.0
        self.max_requests_today = 0

    def reset_day(self, balance_0000: float) -> None:
        """00:00 CE(S)T reset: re-capture balance_0000 from balance (spec 02 §2)."""
        self.balance_0000 = balance_0000

    def observe_requests(self, requests_today: int) -> None:
        self.max_requests_today = max(self.max_requests_today, requests_today)

    def update(self, equity: float) -> bool:
        env = compute_envelope(self.balance_0000, self.initial, equity)
        self.worst_daily_loss_usd = max(self.worst_daily_loss_usd, env.daily_loss_used_usd)
        self.worst_overall_dd_usd = max(self.worst_overall_dd_usd, env.overall_dd_usd)
        if equity <= env.daily_floor_equity or equity <= env.overall_floor_equity:
            self.breaches += 1
            self.breached = True
        return self.breached

    def report(self) -> dict:
        return {
            "breaches": self.breaches,
            "worst_daily_loss_usd": round(self.worst_daily_loss_usd, 2),
            "worst_overall_dd_usd": round(self.worst_overall_dd_usd, 2),
            "max_requests_today": self.max_requests_today,
        }
