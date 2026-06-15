"""SessionBreakoutER behaviour — close-confirmation, MARKET entry (RESTING_STOP_FIX option 2)."""

from datetime import date, timedelta

from src.engine import Direction, NoSignal, SessionBreakoutER, Signal
from src.risk.types import ContextBias
from tests.engine.conftest import DEFAULT_CFG, make_series

SUMMER = date(2026, 6, 2)
WINTER = date(2026, 1, 15)


def _strat():
    return SessionBreakoutER(DEFAULT_CFG)


def _eval(kind, base=SUMMER, bias=ContextBias.NORMAL, calendar=None, cut=None):
    bars, now = make_series(base, kind)
    if cut is not None:
        bars = bars[:cut]
    return _strat().evaluate(bars, now, bias, calendar), bars


def test_long_breakout_emits_market_signal():
    sig, bars = _eval("trend_up")
    assert isinstance(sig, Signal)
    assert sig.direction is Direction.LONG
    assert sig.entry_type == "market"
    assert sig.entry_price == bars[-1].close            # filled at the confirmed close
    assert sig.exit_plan.initial_sl_price < sig.entry_price
    assert sig.regime.regime_gate_passed


def test_short_breakout_emits_market_signal():
    sig, _ = _eval("trend_down")
    assert isinstance(sig, Signal) and sig.direction is Direction.SHORT
    assert sig.entry_type == "market"
    assert sig.exit_plan.initial_sl_price > sig.entry_price


def test_chop_fails_regime_gate():
    sig, _ = _eval("chop")
    assert isinstance(sig, NoSignal) and sig.reason == "regime_gate_failed"


def test_dst_winter_same_utc_is_outside_session():
    sig, _ = _eval("trend_up", base=WINTER)
    assert isinstance(sig, NoSignal) and sig.reason == "outside_session"


def test_stand_down_suppresses_entries():
    sig, _ = _eval("trend_up", bias=ContextBias.STAND_DOWN)
    assert isinstance(sig, NoSignal) and sig.reason == "stand_down"


def test_insufficient_history():
    sig, _ = _eval("trend_up", cut=5)
    assert isinstance(sig, NoSignal) and sig.reason == "insufficient_history"


def test_blackout_active_blocks():
    class Cal:
        def has_high_impact(self, *a, **k):
            return True
    sig, _ = _eval("trend_up", calendar=Cal())
    assert isinstance(sig, NoSignal) and sig.reason == "news_blackout"


def test_blackout_calendar_failure_fails_closed():
    class BadCal:
        def has_high_impact(self, *a, **k):
            raise RuntimeError("calendar down")
    sig, _ = _eval("trend_up", calendar=BadCal())
    assert isinstance(sig, NoSignal) and sig.reason == "news_blackout"


def test_determinism_same_input_same_signal():
    bars, now = make_series(SUMMER, "trend_up")
    s = _strat()
    assert s.evaluate(bars, now, ContextBias.NORMAL, None) == \
        s.evaluate(bars, now, ContextBias.NORMAL, None)


def test_exit_plan_sl_is_max_of_structure_and_atr():
    sig, _ = _eval("trend_up")
    atr_sl = 1.2 * sig.regime.atr_pips
    assert sig.exit_plan.initial_sl_pips >= atr_sl - 1e-9


def test_cautious_bias_only_tags_does_not_change_levels():
    bars, now = make_series(SUMMER, "trend_up")
    s = _strat()
    normal = s.evaluate(bars, now, ContextBias.NORMAL, None)
    cautious = s.evaluate(bars, now, ContextBias.CAUTIOUS, None)
    assert cautious.context_bias is ContextBias.CAUTIOUS
    assert cautious.entry_price == normal.entry_price
    assert cautious.exit_plan.initial_sl_price == normal.exit_plan.initial_sl_price


def test_stop_mode_lever_fills_at_level():
    # The A/B lever: entry.mode="stop" reproduces the pre-fix (un-live-placeable) level fill.
    cfg = {**DEFAULT_CFG, "entry": {"mode": "stop"}}
    bars, now = make_series(SUMMER, "trend_up")
    sig = SessionBreakoutER(cfg).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(sig, Signal) and sig.entry_type == "stop"
    assert sig.entry_price == sig.breakout_level       # fills AT the level


def test_manage_moves_to_break_even_after_r():
    s = _strat()

    class TV:
        direction = "long"
        entry_price = 1.1000
        sl_price = 1.0980
    bars, _ = make_series(SUMMER, "trend_up")
    bars[-1] = bars[-1].__class__(**{**bars[-1].__dict__, "close": 1.1020})
    dec = s.manage(TV(), bars, bars[-1].ts_open_utc + timedelta(minutes=10))
    assert dec.kind == "move_sl" and dec.sl_price == 1.1000
