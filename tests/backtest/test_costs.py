"""Cost & fill model (spec 05 §4)."""

from src.backtest.costs import CostModel

C = CostModel(commission_per_lot_per_side_usd=3.5, slippage_pips=0.2,
              pip_size=0.0001, pip_value_per_lot_usd=10.0)


def test_entry_fill_is_adverse():
    # Long lifts the ask: fill above ref by half-spread + slippage.
    long_fill = C.entry_fill("long", 1.10000, spread_pips=0.4)
    assert long_fill > 1.10000
    # Short hits the bid: fill below ref.
    short_fill = C.entry_fill("short", 1.10000, spread_pips=0.4)
    assert short_fill < 1.10000


def test_stop_entry_slips_in_trade_direction():
    assert C.stop_entry_fill("long", 1.10000) == 1.10000 + 0.2 * 0.0001
    assert C.stop_entry_fill("short", 1.10000) == 1.10000 - 0.2 * 0.0001


def test_gross_pips_sign():
    assert round(C.gross_pips("long", 1.1000, 1.1010), 6) == 10.0
    assert round(C.gross_pips("short", 1.1000, 1.1010), 6) == -10.0


def test_pnl_includes_round_turn_commission():
    # +10 pips on 1.0 lot = $100 gross, minus 2*3.5 commission = $93.
    assert round(C.pnl_usd("long", 1.1000, 1.1010, 1.0), 2) == 93.0
