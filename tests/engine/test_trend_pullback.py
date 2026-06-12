"""TrendPullbackEMA unit tests (research-engine candidate, spec 08, 2026-06-12).

Winter date (London == UTC) so the 15:00 London entry bar maps 1:1 to 15:00 UTC. The regime
gate is made permissive in CFG (er_threshold 0, wide ATR band) so these tests isolate the
pullback->resume ENTRY logic and the exit geometry; a dedicated test exercises the inherited
regime gate's degenerate fail-safe. Fixtures compute the real EMA and place the pullback wick /
resume close RELATIVE to it, so the assertions do not depend on hand-tuned EMA arithmetic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.engine.indicators import ema_series
from src.engine.registry import build_strategy
from src.engine.strategy_trend_pullback import TrendPullbackEMA
from src.engine.types import Bar, Direction, NoSignal, Signal
from src.risk.types import ContextBias

PIP = 0.0001

CFG = {
    "name": "TrendPullbackEMA",
    "pip_size": PIP,
    "timeframe_minutes": 15,
    "session": {"tz": "Europe/London", "window_start": "13:00", "window_end": "16:00",
                "one_shot_per_side": True},
    "pullback": {"ema_window": 20, "slope_lookback": 5, "pullback_lookback": 6,
                 "atr_mult_sl": 1.0, "target_r": 2.0, "move_be_after_r": 1.0},
    # Permissive regime so ENTRY logic is isolated (regime gate tested separately):
    "regime": {"er_window": 14, "er_threshold": 0.0, "atr_window": 14,
               "atr_floor_pips": 0.5, "atr_ceiling_pips": 1000.0,
               "atr_low_pct": 0.0, "atr_high_pct": 1.0},
}

# Last bar opens 15:00 London (winter == UTC) => inside the 13:00-16:00 overlap window.
LAST_TS = datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc)
N = 42


def _bar(ts, o, h, l, c):
    return Bar(ts_open_utc=ts, open=o, high=h, low=l, close=c, volume=1000, is_closed=True)


def _trend_bars(step_pip, base=1.1000, n=N, last_ts=LAST_TS):
    """`n` gently-trending M15 bars; close moves `step_pip` pips/bar. Highs/lows are a tight
    +-1 pip envelope so the EMA tracks closely. Returns the raw bar list (no pullback yet)."""
    start = last_ts - timedelta(minutes=15 * (n - 1))
    bars = []
    for i in range(n):
        ts = start + timedelta(minutes=15 * i)
        c = base + i * step_pip * PIP
        o = c - step_pip * PIP
        h = max(o, c) + 1 * PIP
        l = min(o, c) - 1 * PIP
        bars.append(_bar(ts, o, h, l, c))
    return bars


def long_pullback_bars():
    """Uptrend + a pullback wick into the EMA on bar[-2] + a resume close on bar[-1].

    The fast EMA lags ~9 pips below a +1 pip/bar uptrend, so the pullback is modelled as a
    deep wick on bar[-2] (its LOW reaches the EMA) while its close stays on-trend; the resume
    bar then closes above bar[-2]'s HIGH (and trivially above the far-below EMA)."""
    bars = _trend_bars(step_pip=+1.0)
    es = ema_series([b.close for b in bars], CFG["pullback"]["ema_window"])
    ema_pb = es[-2]   # EMA aligned to bar[-2]
    pb = bars[-2]
    prev_high = pb.close + 1 * PIP
    # Pullback: dip the LOW 5 pips below its EMA (the retrace touch); close stays on-trend.
    bars[-2] = _bar(pb.ts_open_utc, pb.open, prev_high, ema_pb - 5 * PIP, pb.close)
    # Resume: a clean bull bar that closes ABOVE the prior high (momentum reasserts).
    res_open = prev_high
    res_close = prev_high + 2 * PIP
    res_high = res_close + 1 * PIP
    res_low = pb.close            # stays well above the (far-below) EMA
    bars[-1] = _bar(LAST_TS, res_open, res_high, res_low, res_close)
    return bars


def short_pullback_bars():
    """Mirror: downtrend + a pullback wick UP into the EMA + a resume close below prior low."""
    bars = _trend_bars(step_pip=-1.0, base=1.1060)
    es = ema_series([b.close for b in bars], CFG["pullback"]["ema_window"])
    ema_pb = es[-2]
    pb = bars[-2]
    prev_low = pb.close - 1 * PIP
    bars[-2] = _bar(pb.ts_open_utc, pb.open, ema_pb + 5 * PIP, prev_low, pb.close)
    res_open = prev_low
    res_close = prev_low - 2 * PIP
    res_low = res_close - 1 * PIP
    res_high = pb.close           # stays well below the (far-above) EMA
    bars[-1] = _bar(LAST_TS, res_open, res_high, res_low, res_close)
    return bars


def _eval(bars, now=LAST_TS, cfg=CFG, bias=ContextBias.NORMAL):
    return TrendPullbackEMA(cfg).evaluate(bars, now, bias, None)


# ---------------------------------------------------------------- signals
def test_long_pullback_signal_geometry():
    bars = long_pullback_bars()
    strat = TrendPullbackEMA(CFG)
    sig = strat.evaluate(bars, LAST_TS, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal), getattr(sig, "reason", sig)
    assert sig.direction is Direction.LONG
    assert sig.entry_type == "market"
    assert sig.entry_price == bars[-1].close
    assert sig.exit_plan.initial_sl_price < sig.entry_price
    assert len(sig.exit_plan.targets) == 1
    assert sig.exit_plan.targets[0] > sig.entry_price
    rr = (sig.exit_plan.targets[0] - sig.entry_price) / PIP
    assert abs(rr - 2.0 * sig.exit_plan.initial_sl_pips) < 1e-6
    assert sig.exit_plan.move_be_after_r == 1.0


def test_short_pullback_signal_geometry():
    bars = short_pullback_bars()
    sig = TrendPullbackEMA(CFG).evaluate(bars, LAST_TS, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal), getattr(sig, "reason", sig)
    assert sig.direction is Direction.SHORT
    assert sig.exit_plan.initial_sl_price > sig.entry_price
    assert sig.exit_plan.targets[0] < sig.entry_price
    rr = (sig.entry_price - sig.exit_plan.targets[0]) / PIP
    assert abs(rr - 2.0 * sig.exit_plan.initial_sl_pips) < 1e-6


def test_stop_is_not_the_inherited_1_2_atr():
    """Exit geometry is this strategy's own (structural / 1.0xATR floor), never the
    incumbent's reflexive 1.2xATR (spec 08 5.8)."""
    bars = long_pullback_bars()
    strat = TrendPullbackEMA(CFG)
    sig = strat.evaluate(bars, LAST_TS, ContextBias.NORMAL, None)
    regime = strat._regime(bars)
    assert abs(sig.exit_plan.initial_sl_pips - 1.2 * regime.atr_pips) > 1e-6


# ---------------------------------------------------------------- rejections
def test_no_pullback_no_signal():
    """A clean trend with NO recent EMA touch must not fire (needs the retrace)."""
    bars = _trend_bars(step_pip=+1.0)
    ns = _eval(bars)
    assert isinstance(ns, NoSignal) and ns.reason in ("no_pullback_resume", "no_ema")


def test_outside_session_no_signal():
    bars = long_pullback_bars()
    shifted = [_bar(b.ts_open_utc - timedelta(hours=4), b.open, b.high, b.low, b.close)
               for b in bars]
    ns = TrendPullbackEMA(CFG).evaluate(shifted, LAST_TS - timedelta(hours=4),
                                        ContextBias.NORMAL, None)
    assert isinstance(ns, NoSignal) and ns.reason == "outside_session"


def test_stand_down_blocks():
    bars = long_pullback_bars()
    ns = TrendPullbackEMA(CFG).evaluate(bars, LAST_TS, ContextBias.STAND_DOWN, None)
    assert isinstance(ns, NoSignal) and ns.reason == "stand_down"


def test_insufficient_history_blocks():
    bars = _trend_bars(step_pip=+1.0, n=10)
    ns = _eval(bars, now=bars[-1].ts_open_utc)
    assert isinstance(ns, NoSignal) and ns.reason == "insufficient_history"


def test_degenerate_regime_blocks():
    """Flat (zero-TR) bars => ATR degenerate => inherited regime gate fails (fail safe)."""
    cfg = {**CFG, "regime": {**CFG["regime"], "er_threshold": 0.30,
                             "atr_floor_pips": 4.0, "atr_ceiling_pips": 22.0,
                             "atr_low_pct": 0.20, "atr_high_pct": 0.90}}
    bars = [_bar(LAST_TS - timedelta(minutes=15 * (N - 1 - i)), 1.10, 1.10, 1.10, 1.10)
            for i in range(N)]
    ns = TrendPullbackEMA(cfg).evaluate(bars, LAST_TS, ContextBias.NORMAL, None)
    assert isinstance(ns, NoSignal) and ns.reason == "regime_gate_failed"


def test_stale_data_blocks():
    # Truncate so the last bar opens 14:30 London (still in-session) but evaluate at 15:00:
    # a 30-min-old closed M15 bar during an active session is stale (> 1.5 x timeframe).
    bars = long_pullback_bars()[:-2]
    ns = _eval(bars, now=LAST_TS)
    assert isinstance(ns, NoSignal) and ns.reason == "stale_data"


# ---------------------------------------------------------------- wiring
def test_registry_builds_trend_pullback():
    s = build_strategy({"name": "TrendPullbackEMA"})
    assert isinstance(s, TrendPullbackEMA) and s.name == "TrendPullbackEMA"


def test_warmup_covers_ema_window():
    s = TrendPullbackEMA(CFG)
    assert s.warmup_bars() >= s.ema_window + s.slope_lookback + s.pullback_lookback


# ---------------------------------------------------------------- indicator
def test_ema_series_alignment_and_failsafe():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    es = ema_series(vals, 3)
    assert len(es) == len(vals) - 3 + 1
    assert ema_series(vals, 10) == []
    assert ema_series([], 3) == []
