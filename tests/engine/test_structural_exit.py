"""SessionBreakoutERStructuralExit unit tests (spec 08, 2026-06-25).

The candidate is a pure EXIT overlay on the incumbent: ``evaluate`` is inherited unchanged
(same entries), and ``manage`` adds ONE structural-rejection exit — scratch when the current
bar closes BACK INSIDE the opening range.  These tests pin both layers.

Test structure mirrors test_followthrough.py (the previous additive-management candidate).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.engine.registry import build_strategy
from src.engine.strategy import ManageDecision, SessionBreakoutER
from src.engine.strategy_structural_exit import SessionBreakoutERStructuralExit
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias
from tests.engine.conftest import DEFAULT_CFG, make_series

LONDON = ZoneInfo("Europe/London")
UTC = timezone.utc
PIP = 0.0001


# ── helpers ──────────────────────────────────────────────────────────────────

class _TV:
    """Stand-in for the backtester's _TradeView (minimal read-only manage input)."""
    def __init__(self, direction, entry_price, sl_price, tp_price=None, bars_held=1):
        self.direction = direction
        self.entry_price = entry_price
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.bars_held = bars_held


def _bar(ts_utc: datetime, o, h, l, c) -> Bar:
    return Bar(ts_open_utc=ts_utc, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def _make_bars_with_or(base_date: date, or_high: float, or_low: float, mgmt_close: float):
    """Return (bars, now_utc) suitable for manage() testing.

    OR bars land at 12:00/12:15 UTC (= 13:00/13:15 Europe/London summer) so the
    strategy's OR-reconstruction finds them on ``base_date``.  The final bar is the
    management bar whose close is ``mgmt_close``.
    """
    start = datetime(base_date.year, base_date.month, base_date.day, 8, 0, tzinfo=UTC)
    bars = []
    # 16 warmup bars 08:00–11:45 UTC
    for i in range(16):
        ts = start + timedelta(minutes=15 * i)
        mid = 1.1000 + i * PIP
        bars.append(_bar(ts, mid, mid + 2 * PIP, mid - 2 * PIP, mid + PIP))
    # OR bar 1 — 12:00 UTC = 13:00 London (summer/BST)
    ts_or1 = start + timedelta(hours=4)          # 12:00 UTC
    bars.append(_bar(ts_or1, or_low + PIP, or_high, or_low, (or_high + or_low) / 2))
    # OR bar 2 — 12:15 UTC = 13:15 London
    ts_or2 = ts_or1 + timedelta(minutes=15)
    bars.append(_bar(ts_or2, (or_high + or_low) / 2, or_high, or_low, (or_high + or_low) / 2))
    # Management bar — 12:30 UTC = 13:30 London (just after OR ends)
    ts_mgmt = ts_or2 + timedelta(minutes=15)
    bars.append(_bar(ts_mgmt, mgmt_close, mgmt_close + PIP, mgmt_close - PIP, mgmt_close))
    now_utc = ts_mgmt + timedelta(minutes=10)
    return bars, now_utc


# ── registration / identity ───────────────────────────────────────────────────

def test_registered_and_built():
    s = build_strategy({**DEFAULT_CFG, "name": "SessionBreakoutERStructuralExit"})
    assert isinstance(s, SessionBreakoutERStructuralExit)
    assert s.name == "SessionBreakoutERStructuralExit"


def test_is_subclass_of_incumbent():
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    assert isinstance(s, SessionBreakoutER)


# ── evaluate inherits incumbent byte-for-byte ─────────────────────────────────

def test_evaluate_matches_incumbent_on_all_series_kinds():
    """The overlay must produce IDENTICAL evaluate() output to the incumbent."""
    for kind in ("trend_up", "trend_down", "chop"):
        bars, now = make_series(date(2026, 6, 25), kind)
        inc = SessionBreakoutER(DEFAULT_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
        cand = SessionBreakoutERStructuralExit(DEFAULT_CFG).evaluate(
            bars, now, ContextBias.NORMAL, None)
        assert type(inc) is type(cand), f"type mismatch on {kind}"
        if isinstance(inc, Signal):
            assert inc.direction is cand.direction
            assert inc.entry_price == cand.entry_price
            assert inc.entry_type == cand.entry_type == "market"
            assert inc.exit_plan.initial_sl_price == cand.exit_plan.initial_sl_price
        else:
            assert isinstance(cand, NoSignal)
            assert inc.reason == cand.reason


# ── manage: structural rejection (scratch) ────────────────────────────────────

def test_scratches_long_when_close_below_or_high():
    """A long trade where the management bar closes below OR_high → scratch."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    or_high, or_low = 1.1050, 1.1020
    # Entry was above OR_high (market fill above the level)
    tv = _TV("long", or_high + 5 * PIP, or_low - 10 * PIP)
    # Management bar closes just below OR_high → structural rejection
    mgmt_close = or_high - 2 * PIP
    bars, now = _make_bars_with_or(date(2026, 6, 25), or_high, or_low, mgmt_close)
    dec = s.manage(tv, bars, now)
    assert dec.kind == "close_all", f"Expected scratch, got {dec.kind}"


def test_scratches_short_when_close_above_or_low():
    """A short trade where the management bar closes above OR_low → scratch."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    or_high, or_low = 1.1050, 1.1020
    tv = _TV("short", or_low - 5 * PIP, or_high + 10 * PIP)
    mgmt_close = or_low + 2 * PIP    # closed back inside range → rejection for short
    bars, now = _make_bars_with_or(date(2026, 6, 25), or_high, or_low, mgmt_close)
    dec = s.manage(tv, bars, now)
    assert dec.kind == "close_all", f"Expected scratch, got {dec.kind}"


def test_holds_long_when_close_above_or_high():
    """A long trade where price stays above OR_high after entry → no rejection, hold."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    or_high, or_low = 1.1050, 1.1020
    tv = _TV("long", or_high + 5 * PIP, or_low - 10 * PIP)
    mgmt_close = or_high + 10 * PIP   # still above OR_high → no rejection
    bars, now = _make_bars_with_or(date(2026, 6, 25), or_high, or_low, mgmt_close)
    dec = s.manage(tv, bars, now)
    # Expect hold (or move_sl if break-even logic triggers, but never close_all)
    assert dec.kind != "close_all", f"Unexpected scratch: {dec.kind}"


def test_holds_short_when_close_below_or_low():
    """A short trade where price stays below OR_low → no rejection, hold."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    or_high, or_low = 1.1050, 1.1020
    tv = _TV("short", or_low - 5 * PIP, or_high + 10 * PIP)
    mgmt_close = or_low - 10 * PIP   # still below OR_low → no rejection
    bars, now = _make_bars_with_or(date(2026, 6, 25), or_high, or_low, mgmt_close)
    dec = s.manage(tv, bars, now)
    assert dec.kind != "close_all"


def test_holds_when_close_exactly_at_or_high_long():
    """Close exactly at OR_high for a long is NOT a rejection (boundary — strictly less than)."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    or_high, or_low = 1.1050, 1.1020
    tv = _TV("long", or_high + 5 * PIP, or_low - 10 * PIP)
    mgmt_close = or_high            # exactly at boundary — strict < should NOT trigger
    bars, now = _make_bars_with_or(date(2026, 6, 25), or_high, or_low, mgmt_close)
    dec = s.manage(tv, bars, now)
    assert dec.kind != "close_all", "Close exactly at OR_high should not be a rejection"


# ── manage: edge-case / failsafe ─────────────────────────────────────────────

def test_failsafe_when_no_bars():
    """Empty bars → fall back to incumbent (hold), no crash."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    tv = _TV("long", 1.1055, 1.1020)
    dec = s.manage(tv, [], None)
    assert dec.kind == "hold"


def test_failsafe_when_no_or_bars_in_history(monkeypatch):
    """If history contains no OR-window bars (e.g. all warmup), fall back to incumbent."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    tv = _TV("long", 1.1055, 1.1020)
    # Bars only at 08:00–10:00 UTC (well before OR window) — OR reconstruction will find nothing
    start = datetime(2026, 6, 25, 8, 0, tzinfo=UTC)
    bars = [_bar(start + timedelta(minutes=15 * i), 1.1000, 1.1010, 1.0990, 1.1005)
            for i in range(8)]
    now = bars[-1].ts_open_utc + timedelta(minutes=10)
    dec = s.manage(tv, bars, now)
    # Must not crash; behaviour falls back to incumbent's hold
    assert dec.kind in ("hold", "move_sl")


def test_no_regression_on_breakeven_logic():
    """When no structural rejection, incumbent's break-even logic must still fire."""
    s = SessionBreakoutERStructuralExit(DEFAULT_CFG)
    or_high, or_low = 1.1050, 1.1020
    # Long entry, sl well below; price has advanced > move_be_after_r above entry
    # move_be_after_r defaults to 1.0 in DEFAULT_CFG; risk = 35p, so +35p triggers BE
    entry = or_high + 5 * PIP   # 1.10550
    sl = or_low - 10 * PIP      # 1.10100; risk = 45p
    tv = _TV("long", entry, sl)
    # Close well above OR_high AND above entry + 1×risk (triggers BE)
    mgmt_close = entry + 46 * PIP   # +46 pips above entry > risk 45p
    bars, now = _make_bars_with_or(date(2026, 6, 25), or_high, or_low, mgmt_close)
    dec = s.manage(tv, bars, now)
    # No structural rejection (close above or_high) and BE should trigger
    assert dec.kind == "move_sl", f"Expected BE move_sl, got {dec.kind}"
