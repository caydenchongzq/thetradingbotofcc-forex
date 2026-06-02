"""Cost & fill model (spec 05 §4) — pure.

An intraday breakout edge lives or dies on spread + slippage, so these are modelled
explicitly and with the correct sign for long/short. Stop-entry fills are modelled at
the trigger level shifted adversely by slippage.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_per_lot_per_side_usd: float = 3.5   # FTMO-style
    slippage_pips: float = 0.2                      # mean adverse slippage
    pip_size: float = 0.0001
    pip_value_per_lot_usd: float = 10.0

    def entry_fill(self, side: str, ref_price: float, spread_pips: float) -> float:
        """Buys lift the ask (ref + half-spread + slippage); sells hit the bid. Adverse."""
        half_spread = (spread_pips / 2.0) * self.pip_size
        slip = self.slippage_pips * self.pip_size
        if side == "long":
            return ref_price + half_spread + slip
        return ref_price - half_spread - slip

    def stop_entry_fill(self, side: str, level: float) -> float:
        """Breakout stop-entry: filled at the level shifted adversely by slippage."""
        slip = self.slippage_pips * self.pip_size
        return level + slip if side == "long" else level - slip

    def exit_fill(self, side: str, ref_price: float, spread_pips: float,
                  slippage: bool = True) -> float:
        """Closing a long sells the bid; closing a short buys the ask. Adverse."""
        half_spread = (spread_pips / 2.0) * self.pip_size
        slip = (self.slippage_pips * self.pip_size) if slippage else 0.0
        if side == "long":
            return ref_price - half_spread - slip
        return ref_price + half_spread + slip

    def commission(self, lots: float) -> float:
        # Round-turn = both sides.
        return 2.0 * self.commission_per_lot_per_side_usd * lots

    def pnl_usd(self, side: str, entry: float, exit_: float, lots: float) -> float:
        gross_pips = self.gross_pips(side, entry, exit_)
        return gross_pips * self.pip_value_per_lot_usd * lots - self.commission(lots)

    def gross_pips(self, side: str, entry: float, exit_: float) -> float:
        diff = (exit_ - entry) if side == "long" else (entry - exit_)
        return diff / self.pip_size
