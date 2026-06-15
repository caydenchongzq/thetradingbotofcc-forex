"""Builders for strategy-engine tests (session breakout fixtures)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.types import Bar

PIP = 0.0001


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def make_series(base_date, kind="trend_up", breakout=True, n_warmup=16):
    """Build 15m bars from 08:00 UTC: warmup + 2 opening-range bars + 1 breakout bar.

    In summer the default London window (13:00-16:00) maps to 12:00-15:00 UTC, so the OR
    bars land at 12:00/12:15 UTC and the breakout bar at 12:30 UTC (London 13:30).
    Returns (bars, now_utc)."""
    start = datetime(base_date.year, base_date.month, base_date.day, 8, 0, tzinfo=timezone.utc)
    bars = []
    base = 1.1000
    total = n_warmup + 3
    for i in range(total):
        ts = start + timedelta(minutes=15 * i)
        o = base + 0.0003 * i
        is_last = (i == total - 1)
        if kind == "chop":
            # Oscillate around a FLAT base so the Efficiency Ratio is low (choppy).
            o = base + (0.0005 if i % 2 == 0 else -0.0005)
            c = base + (-0.0005 if i % 2 == 0 else 0.0005)
            h, l = base + 0.0009, base - 0.0009
            if is_last and breakout:
                c = base + 0.0015; h = c + 0.0002; l = base - 0.0009
        elif kind == "trend_down":
            o = base - 0.0003 * i
            c = o - 0.0003; h = o + 0.0003; l = o - 0.0005
            if is_last and breakout:
                c = o - 0.0010; l = c - 0.0002; h = o + 0.0002
        else:  # trend_up
            c = o + 0.0003; h = o + 0.0005; l = o - 0.0003
            if is_last and breakout:
                c = o + 0.0010; h = c + 0.0002; l = o - 0.0002
        bars.append(_bar(ts, o, h, l, c))
    now = bars[-1].ts_open_utc + timedelta(minutes=10)
    return bars, now


DEFAULT_CFG = {
    "instrument": "EURUSD", "pip_size": 0.0001, "timeframe_minutes": 15,
    "session": {"tz": "Europe/London", "window_start": "13:00", "window_end": "16:00",
                "opening_range_minutes": 30, "one_shot_per_side": True},
    "breakout": {"buffer_pips": 1.5},
    "regime": {"er_window": 14, "er_threshold": 0.30, "atr_window": 14,
               "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
               "atr_low_pct": 0.10, "atr_high_pct": 0.95},
    "exits": {"atr_mult_sl": 1.2, "target_r_multiples": [1.0, 2.0],
              "partial_fractions": [0.5, 0.5], "move_be_after_r": 1.0},
}


# --- resting-stop (arming) fixtures (RESTING_STOP_FIX) -----------------------
# Regime must pass AT OR-end now (a bar earlier than the old breakout bar); the synthetic
# trend series saturates the ATR percentile there, so relax the high-vol ceiling for arm
# fixtures. This only affects the vol-band classification, not the arming/fill mechanics.
ARM_CFG = {**DEFAULT_CFG, "regime": {**DEFAULT_CFG["regime"], "atr_high_pct": 1.0}}


def make_arm_series(base_date, kind="trend_up"):
    """(arm_bars, now, breakout_bar). ``arm_bars`` ends on the FINAL opening-range bar so
    ``evaluate`` arms; ``now`` is just after it; ``breakout_bar`` is the first post-OR bar
    whose intrabar range touches a level (append it to drive a touch-fill)."""
    bars, _ = make_series(base_date, kind)
    arm_bars = bars[:-1]                       # drop the breakout bar -> last == final OR bar
    now = arm_bars[-1].ts_open_utc + timedelta(minutes=5)
    return arm_bars, now, bars[-1]
