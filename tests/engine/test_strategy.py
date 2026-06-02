"""SessionBreakoutER behaviour (spec 01 §3, §6)."""

from datetime import date, timedelta

from src.engine import Direction, NoSignal, SessionBreakoutER, Signal
from src.risk.types import ContextBias
from tests.engine.conftest import DEFAULT_CFG, make_series

SUMMER = date(2026, 6, 2)
WINTER = date(2026, 1, 15)


def _strat():
    return SessionBreakoutER(DEFAULT_CFG)


def test_long_breakout_emits_signal():
    bars, now = make_series(SUMMER, "trend_up")
    sig = _strat().evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.entry_type == "stop"
    assert sig.exit_plan.initial_sl_price < sig.entry_price       # stop below entry
    assert sig.exit_plan.targets[0] > sig.entry_price            # target above
    assert sig.regime.regime_gate_passed


def test_short_breakout_emits_signal():
    bars, now = make_series(SUMMER, "trend_down")
    sig = _strat().evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.SHORT
    assert sig.exit_plan.initial_sl_price > sig.entry_price


def test_chop_fails_regime_gate():
    bars, now = make_series(SUMMER, "chop")
    res = _strat().evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(res, NoSignal)
    assert res.reason == "regime_gate_failed"


def test_dst_winter_same_utc_is_outside_session():
    # Same UTC clock times that are inside the session in summer fall BEFORE it in winter
    # (London = UTC in winter), proving the gate is DST-aware, not a fixed offset.
    bars, now = make_series(WINTER, "trend_up")
    res = _strat().evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(res, NoSignal)
    assert res.reason == "outside_session"


def test_stand_down_suppresses_entries():
    bars, now = make_series(SUMMER, "trend_up")
    res = _strat().evaluate(bars, now, ContextBias.STAND_DOWN, None)
    assert isinstance(res, NoSignal) and res.reason == "stand_down"


def test_insufficient_history():
    bars, now = make_series(SUMMER, "trend_up")
    res = _strat().evaluate(bars[:5], now, ContextBias.NORMAL, None)
    assert isinstance(res, NoSignal) and res.reason == "insufficient_history"


def test_blackout_active_blocks():
    class Cal:
        def has_high_impact(self, *a, **k):
            return True
    bars, now = make_series(SUMMER, "trend_up")
    res = _strat().evaluate(bars, now, ContextBias.NORMAL, Cal())
    assert isinstance(res, NoSignal) and res.reason == "news_blackout"


def test_blackout_calendar_failure_fails_closed():
    class BadCal:
        def has_high_impact(self, *a, **k):
            raise RuntimeError("calendar down")
    bars, now = make_series(SUMMER, "trend_up")
    res = _strat().evaluate(bars, now, ContextBias.NORMAL, BadCal())
    assert isinstance(res, NoSignal) and res.reason == "news_blackout"


def test_determinism_same_input_same_signal():
    bars, now = make_series(SUMMER, "trend_up")
    s = _strat()
    a = s.evaluate(bars, now, ContextBias.NORMAL, None)
    b = s.evaluate(bars, now, ContextBias.NORMAL, None)
    assert a == b   # pure: identical inputs -> identical Signal


def test_exit_plan_sl_is_max_of_structure_and_atr():
    bars, now = make_series(SUMMER, "trend_up")
    sig = _strat().evaluate(bars, now, ContextBias.NORMAL, None)
    atr_sl = 1.2 * sig.regime.atr_pips
    # structure stop = distance from breakout level to the opposite OR edge.
    assert sig.exit_plan.initial_sl_pips >= atr_sl - 1e-9


def test_cautious_bias_only_tags_does_not_change_signal_levels():
    bars, now = make_series(SUMMER, "trend_up")
    s = _strat()
    normal = s.evaluate(bars, now, ContextBias.NORMAL, None)
    cautious = s.evaluate(bars, now, ContextBias.CAUTIOUS, None)
    # The engine never silently shrinks a trade; only the tag differs (sizing is risk's job).
    assert cautious.context_bias is ContextBias.CAUTIOUS
    assert cautious.entry_price == normal.entry_price
    assert cautious.exit_plan.initial_sl_price == normal.exit_plan.initial_sl_price


def test_manage_moves_to_break_even_after_r():
    s = _strat()

    class TV:
        direction = "long"
        entry_price = 1.1000
        sl_price = 1.0980      # 20-pip risk
    bars, _ = make_series(SUMMER, "trend_up")
    # price now 1R (20 pips) above entry -> move SL to break-even.
    bars[-1] = bars[-1].__class__(**{**bars[-1].__dict__, "close": 1.1020})
    dec = s.manage(TV(), bars, bars[-1].ts_open_utc + timedelta(minutes=10))
    assert dec.kind == "move_sl"
    assert dec.sl_price == 1.1000
