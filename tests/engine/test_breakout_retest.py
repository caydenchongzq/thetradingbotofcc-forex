"""BreakoutRetestER unit tests (research-engine candidate, spec 08, 2026-06-11).

Two layers: (1) the pure ``breakout_retest_trigger`` state machine, and (2) the strategy's
evaluate() over the shared session fixtures. Summer dates: the default London window
13:00-16:00 maps to 12:00-15:00 UTC, so the 30-min opening range is the 12:00/12:15 UTC bars
and post-OR bars run from 12:30 UTC.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.indicators import breakout_retest_trigger
from src.engine.registry import build_strategy
from src.engine.strategy_breakout_retest import BreakoutRetestER
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001


# ============================ pure indicator: trigger ============================
def test_trigger_long_break_retest_resume_on_last():
    highs = [1.1010, 1.1005, 1.1012]
    lows = [1.1002, 1.0995, 1.1001]
    closes = [1.1008, 1.0999, 1.1006]
    assert breakout_retest_trigger(highs, lows, closes, 1.1000, "long") is True


def test_trigger_long_one_shot_earlier_fire_returns_false():
    """If the resume already completed on an earlier bar, the current bar must NOT re-enter."""
    highs = [1.1010, 1.1009, 1.1012]
    lows = [1.1002, 1.0999, 1.1004]
    closes = [1.1008, 1.1006, 1.1007]
    assert breakout_retest_trigger(highs, lows, closes, 1.1000, "long") is False


def test_trigger_long_no_retest_returns_false():
    """Break that runs away without returning to the level -> no entry (trade-count risk)."""
    highs = [1.1010, 1.1020, 1.1030]
    lows = [1.1006, 1.1015, 1.1025]
    closes = [1.1008, 1.1018, 1.1028]
    assert breakout_retest_trigger(highs, lows, closes, 1.1000, "long") is False


def test_trigger_long_false_break_no_reclaim_returns_false():
    """Break, retest, but never closes back above -> false breakout, no entry."""
    highs = [1.1010, 1.1003, 1.0999]
    lows = [1.1002, 1.0995, 1.0990]
    closes = [1.1008, 1.0998, 1.0996]
    assert breakout_retest_trigger(highs, lows, closes, 1.1000, "long") is False


def test_trigger_short_mirror_on_last():
    # bar0 break below; bar1 high retests level but closes ABOVE it (not resumed);
    # bar2 (last) closes below -> resume short entry on the current bar.
    highs = [1.0998, 1.1003, 1.0999]
    lows = [1.0990, 1.0998, 1.0988]
    closes = [1.0992, 1.1001, 1.0994]
    assert breakout_retest_trigger(highs, lows, closes, 1.1000, "short") is True


def test_trigger_break_bar_is_never_entry():
    """A single bar that closes above the level cannot be both break and entry."""
    assert breakout_retest_trigger([1.1010], [1.1002], [1.1008], 1.1000, "long") is False


def test_trigger_degenerate_inputs_fail_safe():
    assert breakout_retest_trigger([], [], [], 1.1, "long") is False
    assert breakout_retest_trigger([1.1], [1.0], [], 1.05, "long") is False


# ============================ strategy: evaluate ============================
CFG = {
    "instrument": "EURUSD", "pip_size": PIP, "timeframe_minutes": 15,
    "session": {"tz": "Europe/London", "window_start": "13:00", "window_end": "16:00",
                "opening_range_minutes": 30, "one_shot_per_side": True},
    "breakout": {"buffer_pips": 1.5},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.10, "atr_high_pct": 0.95},
    "retest": {"atr_mult_sl": 1.0, "target_r": 1.5},
}


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def _retest_series(base_date=datetime(2025, 6, 17), n_warmup=16):
    """Warmup trend-up bars, 2 opening-range bars, then break -> retest -> resume bars.

    Opening range 12:00/12:15 UTC. Post-OR: 12:30 break above range high, 12:45 retest dip
    back to the level, 13:00 resume close above (= current bar, the entry)."""
    start = datetime(base_date.year, base_date.month, base_date.day, 8, 0, tzinfo=timezone.utc)
    bars = []
    base = 1.1000
    for i in range(n_warmup):                                   # trending warmup -> ER high
        ts = start + timedelta(minutes=15 * i)
        o = base + 0.0003 * i
        bars.append(_bar(ts, o, o + 0.0005, o - 0.0003, o + 0.0003))
    or0 = start + timedelta(minutes=15 * n_warmup)
    bars.append(_bar(or0, 1.1050, 1.1054, 1.1046, 1.1050))
    bars.append(_bar(or0 + timedelta(minutes=15), 1.1050, 1.1053, 1.1047, 1.1051))
    rh = 1.1054
    lvl = rh + 1.5 * PIP                                          # long_level ~1.10555
    b_break = or0 + timedelta(minutes=30)                        # break above level
    bars.append(_bar(b_break, 1.1052, 1.1062, 1.1051, 1.1060))
    b_retest = or0 + timedelta(minutes=45)                       # retest dip, closes under
    bars.append(_bar(b_retest, 1.1059, 1.1060, 1.1053, 1.1055))
    b_resume = or0 + timedelta(minutes=60)                       # resume close above = ENTRY
    bars.append(_bar(b_resume, 1.1057, 1.1064, 1.1056, 1.1062))
    now = b_resume + timedelta(minutes=10)
    return bars, now, lvl


def _eval(bars, now, cfg=CFG):
    return BreakoutRetestER(cfg).evaluate(bars, now, ContextBias.NORMAL, None)


def test_long_retest_entry_signal_and_geometry():
    bars, now, lvl = _retest_series()
    strat = BreakoutRetestER(CFG)
    sig = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.entry_type == "market"
    assert sig.entry_price == bars[-1].close          # honest fill at resume close
    regime = strat._regime(bars)
    assert abs(sig.exit_plan.initial_sl_pips - 1.0 * regime.atr_pips) < 1e-6
    assert sig.exit_plan.initial_sl_price < sig.entry_price
    assert len(sig.exit_plan.targets) == 1
    reward = (sig.exit_plan.targets[0] - sig.entry_price) / PIP
    assert abs(reward - 1.5 * sig.exit_plan.initial_sl_pips) < 1e-6
    assert sig.exit_plan.move_be_after_r is None       # no new manage() semantic


def test_stop_is_not_the_inherited_1_2_atr():
    """Exit geometry is this strategy's own (1.0xATR), NOT the incumbent's 1.2xATR."""
    bars, now, _ = _retest_series()
    strat = BreakoutRetestER(CFG)
    sig = strat.evaluate(bars, now, ContextBias.NORMAL, None)
    regime = strat._regime(bars)
    assert abs(sig.exit_plan.initial_sl_pips - 1.2 * regime.atr_pips) > 1e-6


def test_no_retest_breakout_gives_no_signal():
    """Price runs away after the break and never returns to the level -> no entry."""
    bars, now, _ = _retest_series()
    t2, t1 = bars[-2].ts_open_utc, bars[-1].ts_open_utc
    bars[-2] = _bar(t2, 1.1061, 1.1066, 1.1060, 1.1064)
    bars[-1] = _bar(t1, 1.1064, 1.1069, 1.1063, 1.1067)
    sig = _eval(bars, now)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "no_retest_entry"


def test_outside_session_no_signal():
    bars, now, _ = _retest_series()
    late = bars[-1].ts_open_utc.replace(hour=22)
    sig = _eval(bars, late)
    assert isinstance(sig, NoSignal)


def test_stand_down_no_signal():
    bars, now, _ = _retest_series()
    sig = BreakoutRetestER(CFG).evaluate(bars, now, ContextBias.STAND_DOWN, None)
    assert isinstance(sig, NoSignal)
    assert sig.reason == "stand_down"


def test_registry_builds_by_name():
    strat = build_strategy({**CFG, "name": "BreakoutRetestER"})
    assert isinstance(strat, BreakoutRetestER)
    assert strat.name == "BreakoutRetestER"
