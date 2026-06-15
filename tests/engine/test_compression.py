"""SessionBreakoutERCompression — research-engine candidate (spec 08, 2026-06-07).

The compression filter is ENTRY-SIDE ONLY: a quiet pre-session morning lets the parent
breakout signal through; a loud morning blocks it with its own NoSignal reason. Every
degraded path (insufficient pre-session history) blocks — fail safe.
"""

from __future__ import annotations

import pytest

from datetime import datetime, timedelta, timezone

from src.engine.indicators import compression_pct
from src.engine.registry import build_strategy
from src.engine.strategy_compression import SessionBreakoutERCompression
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001

CFG = {
    "name": "SessionBreakoutERCompression",
    "instrument": "EURUSD", "pip_size": 0.0001, "timeframe_minutes": 15,
    "session": {"tz": "Europe/London", "window_start": "13:00", "window_end": "16:00",
                "opening_range_minutes": 30, "one_shot_per_side": True},
    "breakout": {"buffer_pips": 1.5},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.10, "atr_high_pct": 0.95},
    "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
    "compression": {"recent_bars": 20, "baseline_bars": 60, "max_pct": 0.50},
}




def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000,
               is_closed=True)


def build_series(quiet_morning: bool):
    """64 baseline bars + 20 morning bars + 2 OR bars + 1 breakout bar (15m, UTC).

    July => London is BST, so the 13:00 session window opens at 12:00 UTC. The series is
    continuous and anchored so it ENDS with the breakout bar at 12:30 UTC; the last
    pre-session bar closes right before the window opens. `quiet_morning=True` makes the
    morning TR ~6 pips vs a ~15 pip baseline (compressed); False swaps them.
    64 baseline bars: the filter needs recent_n + baseline_n + 1 PRE-SESSION bars
    (true_ranges yields n-1 values). Returns (bars, now_utc).
    """
    base_tr = (15 if quiet_morning else 6) * PIP
    morn_tr = (6 if quiet_morning else 15) * PIP
    total = 64 + 20 + 2 + 1
    ts = (datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
          - timedelta(minutes=15 * (total - 1)))
    price = 1.1000
    bars = []

    def add(o, c, tr):
        nonlocal ts
        mid = (o + c) / 2.0
        bars.append(_bar(ts, o, mid + tr / 2.0, mid - tr / 2.0, c))
        ts += timedelta(minutes=15)

    for i in range(64):                       # baseline: flat oscillation
        add(price, price + (2 * PIP if i % 2 == 0 else -2 * PIP), base_tr)
    for _ in range(20):                       # morning: gentle uptrend
        add(price, price + 3 * PIP, morn_tr)
        price += 3 * PIP
    or_highs = []
    for _ in range(2):                        # opening range (12:00, 12:15 UTC)
        add(price, price + 3 * PIP, 8 * PIP)
        or_highs.append(bars[-1].high)
        price += 3 * PIP
    level = max(or_highs) + 1.5 * PIP         # buffer
    add(price, level + 5 * PIP, 10 * PIP)     # breakout bar closes above level+buffer
    now = bars[-1].ts_open_utc + timedelta(minutes=20)
    return bars, now


# ---------------------------------------------------------------- indicator
def test_compression_pct_quiet_recent_is_low():
    h, l, c = [], [], []
    px = 1.1
    for i in range(61):                       # baseline TR 15 pips
        h.append(px + 15 * PIP); l.append(px); c.append(px + 7 * PIP)
    for i in range(20):                       # recent TR 6 pips
        h.append(px + 6 * PIP); l.append(px); c.append(px + 3 * PIP)
    assert compression_pct(h, l, c, 20, 60) <= 0.05


def test_compression_pct_loud_recent_is_high():
    h, l, c = [], [], []
    px = 1.1
    for i in range(61):
        h.append(px + 6 * PIP); l.append(px); c.append(px + 3 * PIP)
    for i in range(20):
        h.append(px + 15 * PIP); l.append(px); c.append(px + 7 * PIP)
    assert compression_pct(h, l, c, 20, 60) >= 0.95


def test_compression_pct_insufficient_history_fails_safe():
    h = [1.1, 1.2]; l = [1.0, 1.1]; c = [1.05, 1.15]
    assert compression_pct(h, l, c, 20, 60) == 1.0
    assert compression_pct([], [], [], 20, 60) == 1.0
    assert compression_pct(h, l, c, 0, 60) == 1.0
    assert compression_pct(h, l[:1], c, 1, 1) == 1.0   # mismatched lengths


# ---------------------------------------------------------------- strategy
def test_quiet_morning_allows_breakout_signal():
    bars, now = build_series(quiet_morning=True)
    strat = SessionBreakoutERCompression(CFG)
    out = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(out, Signal), getattr(out, "reason", None)
    assert out.direction is Direction.LONG


def test_loud_morning_blocks_with_compression_reason():
    bars, now = build_series(quiet_morning=False)
    strat = SessionBreakoutERCompression(CFG)
    out = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(out, NoSignal)
    assert out.reason == "pre_session_not_compressed"


def test_parent_strategy_would_signal_in_loud_case():
    """The block in the loud case comes from the filter, not the parent's gates."""
    from src.engine.strategy import SessionBreakoutER
    bars, now = build_series(quiet_morning=False)
    parent = SessionBreakoutER(CFG)
    assert isinstance(parent.evaluate(bars, now, ContextBias.NORMAL, None), Signal)


def test_insufficient_pre_session_history_blocks():
    bars, now = build_series(quiet_morning=True)
    strat = SessionBreakoutERCompression(CFG)
    # Strip the early history so the filter (not warmup) is what decides.
    assert strat._pre_session_compressed(bars[-30:], now) is False


def test_warmup_covers_filter_history():
    strat = SessionBreakoutERCompression(CFG)
    assert strat.warmup_bars() >= 20 + 60 + 2


def test_registry_builds_compression_strategy():
    strat = build_strategy(dict(CFG))
    assert isinstance(strat, SessionBreakoutERCompression)
    assert strat.name == "SessionBreakoutERCompression"


def test_determinism_same_input_same_output():
    bars, now = build_series(quiet_morning=True)
    strat = SessionBreakoutERCompression(CFG)
    a = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    b = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(a, Signal) and isinstance(b, Signal)
    assert a.entry_price == b.entry_price and a.exit_plan == b.exit_plan


def test_manage_inherited_from_incumbent():
    """Exit/management semantics are the parent's — no live-mirror needed."""
    strat = SessionBreakoutERCompression(CFG)
    assert "manage" not in SessionBreakoutERCompression.__dict__
    assert "evaluate" in SessionBreakoutERCompression.__dict__
