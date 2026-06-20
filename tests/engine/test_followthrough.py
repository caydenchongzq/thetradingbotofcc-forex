"""SessionBreakoutERFollowThrough unit tests (research-engine candidate, spec 08, 2026-06-20).

The candidate is a pure EXIT overlay on the incumbent: ``evaluate`` is inherited byte-for-byte
(so entry behaviour must match the incumbent exactly), and ``manage`` adds ONE follow-through
failure exit — close at market once the trade has been held ``time_stop_bars`` closed bars and
is still below ``min_progress_r`` of favourable progress, otherwise defer to the incumbent's
break-even logic. These tests pin both layers.
"""

from __future__ import annotations

from datetime import timedelta

from src.engine.registry import build_strategy
from src.engine.strategy import ManageDecision, SessionBreakoutER
from src.engine.strategy_followthrough import SessionBreakoutERFollowThrough
from src.engine.types import Direction, NoSignal, Signal
from src.risk.types import ContextBias
from tests.engine.conftest import DEFAULT_CFG, make_series

FT_CFG = {**DEFAULT_CFG, "follow_through": {"time_stop_bars": 4, "min_progress_r": 0.0}}


class _TV:
    """Stand-in for the backtester's _TradeView (read-only manage input)."""
    def __init__(self, direction, entry_price, sl_price, bars_held):
        self.direction = direction
        self.entry_price = entry_price
        self.sl_price = sl_price
        self.bars_held = bars_held


# ============================ registry / identity ============================
def test_registered_and_built():
    s = build_strategy({**FT_CFG, "name": "SessionBreakoutERFollowThrough"})
    assert isinstance(s, SessionBreakoutERFollowThrough)
    assert s.name == "SessionBreakoutERFollowThrough"
    assert s.ft_time_stop_bars == 4 and s.ft_min_progress_r == 0.0


def test_evaluate_is_byte_for_byte_incumbent():
    # The overlay touches only manage; entries must be identical to the incumbent's.
    for kind in ("trend_up", "trend_down", "chop"):
        bars, now = make_series(__import__("datetime").date(2026, 6, 2), kind)
        inc = SessionBreakoutER(DEFAULT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
        cand = SessionBreakoutERFollowThrough(FT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
        assert type(inc) is type(cand)
        if isinstance(inc, Signal):
            assert inc.direction is cand.direction
            assert inc.entry_price == cand.entry_price
            assert inc.entry_type == cand.entry_type == "market"
            assert inc.exit_plan.initial_sl_price == cand.exit_plan.initial_sl_price
        else:
            assert isinstance(cand, NoSignal) and inc.reason == cand.reason


# ============================ manage: follow-through failure exit ============================
def _bars_at(price):
    # A single closed bar carrying the current price as its close (manage reads bars[-1].close).
    bars, _ = make_series(__import__("datetime").date(2026, 6, 2), "trend_up")
    last = bars[-1]
    bars[-1] = last.__class__(**{**last.__dict__, "close": price})
    return bars


def test_scratches_underwater_long_after_window():
    s = SessionBreakoutERFollowThrough(FT_CFG)
    # entry 1.1000, sl 1.0980 (risk 20p); price below entry after 4 bars -> scratch.
    tv = _TV("long", 1.1000, 1.0980, bars_held=4)
    dec = s.manage(tv, _bars_at(1.0995), None)
    assert dec.kind == "close_all"


def test_scratches_underwater_short_after_window():
    s = SessionBreakoutERFollowThrough(FT_CFG)
    tv = _TV("short", 1.1000, 1.1020, bars_held=5)
    dec = s.manage(tv, _bars_at(1.1006), None)   # short underwater (price up) -> scratch
    assert dec.kind == "close_all"


def test_no_scratch_before_window():
    s = SessionBreakoutERFollowThrough(FT_CFG)
    tv = _TV("long", 1.1000, 1.0980, bars_held=3)   # only 3 bars held < 4
    dec = s.manage(tv, _bars_at(1.0995), None)
    assert dec.kind == "hold"


def test_no_scratch_when_in_profit_after_window():
    s = SessionBreakoutERFollowThrough(FT_CFG)
    tv = _TV("long", 1.1000, 1.0980, bars_held=8)   # well past window but in profit
    dec = s.manage(tv, _bars_at(1.1010), None)      # +0.5R -> follow-through present, hold/BE
    assert dec.kind in ("hold", "move_sl")          # never a failure close


def test_disabled_when_time_stop_zero_matches_incumbent():
    s = SessionBreakoutERFollowThrough({**FT_CFG, "follow_through": {"time_stop_bars": 0}})
    tv = _TV("long", 1.1000, 1.0980, bars_held=20)
    # With the overlay disabled, an underwater trade must NOT be scratched: incumbent holds.
    assert s.manage(tv, _bars_at(1.0995), None).kind == "hold"


def test_failsafe_on_missing_bars_held():
    s = SessionBreakoutERFollowThrough(FT_CFG)

    class _NoHeld:
        direction = "long"; entry_price = 1.1000; sl_price = 1.0980
    # No bars_held attribute -> must not raise, must defer to incumbent (hold).
    assert s.manage(_NoHeld(), _bars_at(1.0995), None).kind == "hold"


def test_failsafe_on_zero_risk():
    s = SessionBreakoutERFollowThrough(FT_CFG)
    tv = _TV("long", 1.1000, 1.1000, bars_held=10)   # entry == sl -> risk 0
    assert s.manage(tv, _bars_at(1.0990), None).kind == "hold"


def test_min_progress_threshold_keeps_small_winners_but_scratches_flat():
    # With min_progress_r = 0.25R, a +0.1R trade after the window is still scratched (no real
    # follow-through), while a +0.3R trade is kept. Pins the threshold semantics.
    s = SessionBreakoutERFollowThrough(
        {**FT_CFG, "follow_through": {"time_stop_bars": 4, "min_progress_r": 0.25}})
    tv = _TV("long", 1.1000, 1.0980, bars_held=6)    # risk 20p; +0.1R = 1.1002
    assert s.manage(tv, _bars_at(1.1002), None).kind == "close_all"
    assert s.manage(tv, _bars_at(1.1006), None).kind in ("hold", "move_sl")  # +0.3R kept
