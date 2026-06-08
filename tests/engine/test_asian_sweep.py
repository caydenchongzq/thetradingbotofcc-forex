"""AsianSweepFade unit tests (research-engine candidate, spec 08, 2026-06-08).

Fixtures use a WINTER date (London == UTC) so London session times map 1:1 to UTC,
keeping the bar arithmetic readable. The Asian range alternates two bar shapes with
DIFFERENT true ranges so the ATR percentile lands mid-band (vol NORMAL) instead of
degenerate 1.0, and closes oscillate so ER stays low (chop => inverted gate passes).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.registry import build_strategy
from src.engine.strategy_asian_sweep import AsianSweepFade
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001

CFG = {
    "name": "AsianSweepFade",
    "pip_size": PIP,
    "timeframe_minutes": 15,
    "fade": {"asian_start": "00:00", "asian_end": "08:00",
             "window_start": "08:00", "window_end": "11:00",
             "sweep_buffer_pips": 1.5, "min_asian_bars": 16,
             "one_shot_per_side": True},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.20, "atr_high_pct": 0.90},
    "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0],
              "partial_fractions": [1.0], "move_be_after_r": None},
}

ASIAN_HIGH = 1.1004
ASIAN_LOW = 1.0992


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def asian_bars(day=datetime(2026, 1, 15, tzinfo=timezone.utc), trending=False):
    """32 M15 bars 00:00..07:45 London(=UTC, winter). Chop by default; ER~1 if trending."""
    bars = []
    for i in range(32):
        ts = day + timedelta(minutes=15 * i)
        if trending:
            o = 1.0900 + 0.0003 * i
            bars.append(_bar(ts, o, o + 0.0005, o - 0.0003, o + 0.0003))
        elif i % 2 == 0:   # TR ~12 pips
            bars.append(_bar(ts, 1.1000, ASIAN_HIGH, ASIAN_LOW, 1.0996))
        else:              # TR ~8 pips
            bars.append(_bar(ts, 1.0996, 1.1002, 1.0994, 1.1000))
    return bars


def with_window_bars(extra, day=datetime(2026, 1, 15, tzinfo=timezone.utc), trending=False):
    """Asian bars + an inside 08:00 bar + the supplied (offset_min, o, h, l, c) bars."""
    bars = asian_bars(day, trending=trending)
    bars.append(_bar(day + timedelta(hours=8), 1.0998, 1.1002, 1.0994, 1.0998))
    for off, o, h, l, c in extra:
        bars.append(_bar(day + timedelta(minutes=off), o, h, l, c))
    now = bars[-1].ts_open_utc
    return bars, now


SWEEP_SHORT = (495, 1.0999, 1.1010, 1.0997, 1.1000)   # 08:15, runs the Asian high
SWEEP_LONG = (495, 1.0995, 1.0998, 1.0984, 1.0996)    # 08:15, runs the Asian low


def _eval(bars, now, cfg=CFG):
    return AsianSweepFade(cfg).evaluate(bars, now, ContextBias.NORMAL, None)


# ---------------------------------------------------------------- signals
def test_short_sweep_fade_signal():
    bars, now = with_window_bars([SWEEP_SHORT])
    sig = _eval(bars, now)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.SHORT
    assert sig.entry_type == "market"
    assert sig.entry_price == 1.1000
    assert sig.exit_plan.initial_sl_price > 1.1010          # beyond the sweep extreme
    assert sig.exit_plan.initial_sl_pips >= (1.1010 - 1.1000) / PIP
    assert len(sig.exit_plan.targets) == 1                  # single 1R target
    assert abs((sig.entry_price - sig.exit_plan.targets[0]) / PIP
               - sig.exit_plan.initial_sl_pips) < 1e-6
    assert sig.regime.regime_gate_passed and sig.regime.er < 0.30


def test_long_sweep_fade_signal_mirror():
    bars, now = with_window_bars([SWEEP_LONG])
    sig = _eval(bars, now)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.exit_plan.initial_sl_price < 1.0984


# ---------------------------------------------------------------- rejections
def test_no_sweep_no_signal():
    bars, now = with_window_bars([(495, 1.0998, 1.1002, 1.0994, 1.0996)])
    ns = _eval(bars, now)
    assert isinstance(ns, NoSignal) and ns.reason == "no_sweep"


def test_trending_er_blocks_fade():
    bars, now = with_window_bars([SWEEP_SHORT], trending=True)
    ns = _eval(bars, now)
    assert isinstance(ns, NoSignal) and ns.reason == "regime_gate_failed"


def test_outside_window():
    day = datetime(2026, 1, 15, tzinfo=timezone.utc)
    bars, _ = with_window_bars([SWEEP_SHORT])
    late = _bar(day + timedelta(hours=11), 1.0999, 1.1010, 1.0997, 1.1000)
    ns = _eval(bars + [late], late.ts_open_utc)
    assert isinstance(ns, NoSignal) and ns.reason == "outside_session"


def test_one_shot_per_side():
    second_sweep = (525, 1.0998, 1.1009, 1.0996, 1.0999)    # 08:45, same-side rerun
    inside = (510, 1.0999, 1.1002, 1.0996, 1.0998)          # 08:30
    bars, now = with_window_bars([SWEEP_SHORT, inside, second_sweep])
    ns = _eval(bars, now)
    assert isinstance(ns, NoSignal) and ns.reason == "sweep_already_faded"


def test_ambiguous_double_sided_sweep_blocks():
    both = (495, 1.0999, 1.1010, 1.0985, 1.0998)
    bars, now = with_window_bars([both])
    ns = _eval(bars, now)
    assert isinstance(ns, NoSignal) and ns.reason == "ambiguous_sweep"


def test_insufficient_asian_range_blocks():
    day = datetime(2026, 1, 15, tzinfo=timezone.utc)
    bars = []
    for i in range(8):                                       # only 2h of Asian bars
        ts = day + timedelta(hours=6, minutes=15 * i)
        o = 1.1000 if i % 2 == 0 else 1.0996
        bars.append(_bar(ts, o, ASIAN_HIGH if i % 2 == 0 else 1.1002,
                         ASIAN_LOW if i % 2 == 0 else 1.0994,
                         1.0996 if i % 2 == 0 else 1.1000))
    for j in range(9):                                       # 08:00..10:00 inside bars
        ts = day + timedelta(hours=8, minutes=15 * j)
        bars.append(_bar(ts, 1.0998, 1.1002, 1.0994, 1.0998))
    ns = _eval(bars, bars[-1].ts_open_utc)
    assert isinstance(ns, NoSignal) and ns.reason == "insufficient_asian_range"


def test_stand_down_blocks():
    bars, now = with_window_bars([SWEEP_SHORT])
    ns = AsianSweepFade(CFG).evaluate(bars, now, ContextBias.STAND_DOWN, None)
    assert isinstance(ns, NoSignal) and ns.reason == "stand_down"


# ---------------------------------------------------------------- wiring
def test_registry_builds_asian_sweep_fade():
    s = build_strategy({"name": "AsianSweepFade"})
    assert isinstance(s, AsianSweepFade) and s.name == "AsianSweepFade"


def test_manage_inherited_hold_with_null_be():
    bars, now = with_window_bars([SWEEP_SHORT])
    strat = AsianSweepFade(CFG)
    class T:  # minimal open-trade stub
        entry_price = 1.1000; sl_price = 1.1012; direction = "short"
    assert strat.manage(T(), bars, now).kind == "hold"
