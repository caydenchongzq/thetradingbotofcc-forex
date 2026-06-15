"""SecondEntryORB unit tests (research-engine candidate, spec 08, 2026-06-13).

Two layers: (1) the pure ``second_entry_breakout_trigger`` episode counter, and (2) the
strategy's ``evaluate`` over shared session fixtures, including the key invariant that the
FIRST break is byte-for-byte the incumbent (additive-only) while a re-break adds a 2nd entry.

Summer dates: the default London window 13:00-16:00 maps to 12:00-15:00 UTC, so the 30-min
opening range is the 12:00/12:15 UTC bars and post-OR bars run from 12:30 UTC.
"""

from __future__ import annotations

import pytest

from datetime import datetime, timedelta, timezone

from src.engine.indicators import second_entry_breakout_trigger
from src.engine.registry import build_strategy
from src.engine.strategy import SessionBreakoutER
from src.engine.strategy_second_entry import SecondEntryORB
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001
LVL = 1.1000


# ============================ pure indicator: episode trigger ============================
def test_first_break_fires_like_incumbent_max1():
    """max_entries=1 reproduces the incumbent one-shot: the first break fires."""
    assert second_entry_breakout_trigger([1.1010], LVL, "long", 1) is True


def test_second_episode_blocked_at_max1():
    """break -> close inside -> re-break: at max_entries=1 the re-break must NOT fire."""
    closes = [1.1010, 1.0995, 1.1012]
    assert second_entry_breakout_trigger(closes, LVL, "long", 1) is False


def test_second_episode_fires_at_max2():
    """Same sequence at max_entries=2: the re-break (current bar) DOES fire (additive)."""
    closes = [1.1010, 1.0995, 1.1012]
    assert second_entry_breakout_trigger(closes, LVL, "long", 2) is True


def test_mid_run_continuation_does_not_fire():
    """A bar continuing an existing beyond-run is not an episode start -> no entry."""
    closes = [1.0995, 1.1010, 1.1012]
    assert second_entry_breakout_trigger(closes, LVL, "long", 2) is False


def test_current_not_beyond_does_not_fire():
    closes = [1.1010, 1.0995, 1.0996]
    assert second_entry_breakout_trigger(closes, LVL, "long", 2) is False


def test_third_episode_blocked_at_max2():
    closes = [1.1010, 1.0995, 1.1011, 1.0994, 1.1013]
    assert second_entry_breakout_trigger(closes, LVL, "long", 2) is False


def test_short_mirror_second_episode_fires_at_max2():
    closes = [1.0990, 1.1005, 1.0988]
    assert second_entry_breakout_trigger(closes, LVL, "short", 2) is True


def test_degenerate_inputs_fail_safe():
    assert second_entry_breakout_trigger([], LVL, "long", 2) is False
    assert second_entry_breakout_trigger([1.1010], LVL, "long", 0) is False


# ============================ strategy: evaluate ============================
CFG = {
    "instrument": "EURUSD", "pip_size": PIP, "timeframe_minutes": 15,
    "session": {"tz": "Europe/London", "window_start": "13:00", "window_end": "16:00",
                "opening_range_minutes": 30, "one_shot_per_side": True},
    "breakout": {"buffer_pips": 1.5},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.10, "atr_high_pct": 0.95},
    "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
    "second_entry": {"max_entries_per_side": 2},
}


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def _series(base_date=datetime(2025, 6, 17), n_warmup=16):
    """Trending warmup -> 2 OR bars -> post-OR: break (ep1) -> close inside -> re-break (ep2).

    Returns (warmup+OR bars, b1, b2, b3, now_after_b3, long_level).
    """
    start = datetime(base_date.year, base_date.month, base_date.day, 8, 0, tzinfo=timezone.utc)
    bars = []
    base = 1.1000
    for i in range(n_warmup):                                   # trending warmup -> ER high
        ts = start + timedelta(minutes=15 * i)
        o = base + 0.0003 * i
        bars.append(_bar(ts, o, o + 0.0005, o - 0.0003, o + 0.0003))
    or0 = start + timedelta(minutes=15 * n_warmup)              # 12:00 UTC
    bars.append(_bar(or0, 1.1050, 1.1054, 1.1046, 1.1050))
    bars.append(_bar(or0 + timedelta(minutes=15), 1.1050, 1.1053, 1.1047, 1.1051))
    lvl = 1.1054 + 1.5 * PIP                                     # long_level ~1.10555
    b1 = _bar(or0 + timedelta(minutes=30), 1.1052, 1.1063, 1.1051, 1.1060)   # break (episode 1)
    b2 = _bar(or0 + timedelta(minutes=45), 1.1059, 1.1061, 1.1049, 1.1052)   # close back inside
    b3 = _bar(or0 + timedelta(minutes=60), 1.1057, 1.1066, 1.1056, 1.1061)   # re-break (episode 2)
    now = b3.ts_open_utc + timedelta(minutes=10)
    return bars, b1, b2, b3, now, lvl


@pytest.mark.skip(reason="incumbent now ARMS (RESTING_STOP_FIX §3); SecondEntryORB is a rejected close-trigger dev candidate — comparison invalid until it is itself ported")
def test_first_break_identical_to_incumbent():
    """The first-break signal must be byte-for-byte the incumbent's (additive-only invariant)."""
    bars, b1, _, _, _, _ = _series()
    e1 = bars + [b1]
    now1 = b1.ts_open_utc + timedelta(minutes=10)
    cand = SecondEntryORB(CFG).evaluate(e1, now1, ContextBias.NORMAL, None)
    base = SessionBreakoutER(CFG).evaluate(e1, now1, ContextBias.NORMAL, None)
    assert isinstance(cand, Signal) and isinstance(base, Signal)
    assert cand.direction is base.direction is Direction.LONG
    assert cand.entry_price == base.entry_price
    assert cand.exit_plan.initial_sl_price == base.exit_plan.initial_sl_price
    assert cand.exit_plan.initial_sl_pips == base.exit_plan.initial_sl_pips
    assert cand.exit_plan.targets == base.exit_plan.targets


@pytest.mark.skip(reason="incumbent now ARMS (RESTING_STOP_FIX §3); SecondEntryORB is a rejected close-trigger dev candidate — comparison invalid until it is itself ported")
def test_second_entry_fires_where_incumbent_is_silent():
    """On the re-break bar the incumbent (one-shot) is silent; SecondEntryORB enters."""
    bars, b1, b2, b3, now, lvl = _series()
    full = bars + [b1, b2, b3]
    cand = SecondEntryORB(CFG).evaluate(full, now, ContextBias.NORMAL, None)
    base = SessionBreakoutER(CFG).evaluate(full, now, ContextBias.NORMAL, None)
    assert isinstance(cand, Signal)
    assert cand.direction is Direction.LONG
    assert cand.entry_price == lvl                 # incumbent stop-entry at the level (reused)
    assert isinstance(base, NoSignal)              # incumbent already fired episode 1
    assert base.reason == "no_range_break"


def test_geometry_matches_incumbent_machinery():
    """Exit geometry is the incumbent's validated machinery (1.2xATR floor / 1R / be=None)."""
    bars, b1, b2, b3, now, _ = _series()
    strat = SecondEntryORB(CFG)
    sig = strat.evaluate(bars + [b1, b2, b3], now, ContextBias.NORMAL, None)
    regime = strat._regime(bars + [b1, b2, b3])
    assert sig.exit_plan.initial_sl_pips >= 1.2 * regime.atr_pips - 1e-9   # max(struct, 1.2ATR)
    assert sig.exit_plan.target_r_multiples == (1.0,)
    assert sig.exit_plan.move_be_after_r is None


def test_third_episode_does_not_fire():
    """With max_entries=2, a THIRD break must not fire (cap respected)."""
    bars, b1, b2, b3, _, _ = _series()
    b4 = _bar(b3.ts_open_utc + timedelta(minutes=15), 1.1060, 1.1062, 1.1050, 1.1052)  # inside
    b5 = _bar(b3.ts_open_utc + timedelta(minutes=30), 1.1057, 1.1067, 1.1056, 1.1062)  # ep3 break
    now = b5.ts_open_utc + timedelta(minutes=10)
    sig = SecondEntryORB(CFG).evaluate(bars + [b1, b2, b3, b4, b5], now, ContextBias.NORMAL, None)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "no_range_break"


def test_max1_collapses_to_incumbent():
    """max_entries_per_side=1 makes SecondEntryORB silent on the re-break, like the incumbent."""
    cfg = {**CFG, "second_entry": {"max_entries_per_side": 1}}
    bars, b1, b2, b3, now, _ = _series()
    sig = SecondEntryORB(cfg).evaluate(bars + [b1, b2, b3], now, ContextBias.NORMAL, None)
    assert isinstance(sig, NoSignal)


def test_stand_down_no_signal():
    bars, b1, b2, b3, now, _ = _series()
    sig = SecondEntryORB(CFG).evaluate(bars + [b1, b2, b3], now, ContextBias.STAND_DOWN, None)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "stand_down"


def test_outside_session_no_signal():
    bars, b1, b2, b3, now, _ = _series()
    late = now.replace(hour=22)
    sig = SecondEntryORB(CFG).evaluate(bars + [b1, b2, b3], late, ContextBias.NORMAL, None)
    assert isinstance(sig, NoSignal)


def test_registry_builds_by_name():
    strat = build_strategy({**CFG, "name": "SecondEntryORB"})
    assert isinstance(strat, SecondEntryORB)
    assert strat.name == "SecondEntryORB"
