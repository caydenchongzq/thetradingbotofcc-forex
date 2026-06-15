"""Resting-stop OCO model (RESTING_STOP_FIX §3): arm at OR-end, fill on intrabar touch.

Covers the strategy arming contract, the decide.py OCO pair, and the backtester touch-fill
(single side, both-sides-in-one-bar, and no-touch expiry)."""

from __future__ import annotations

from datetime import date, timedelta, timezone

from src.common.config import RiskConfig
from src.engine.strategy_resting import SessionBreakoutERResting as SessionBreakoutER
from src.engine.decide import decide_entry
from src.engine.types import ArmSignal, Direction, NoSignal
from src.backtest.engine import EventDrivenBacktester, _Armed, _ArmedSide
from src.backtest.costs import CostModel
from src.backtest.types import BacktestRequest, BTBar, WFSpec
from src.risk.governor import RiskGovernor
from src.risk.types import AccountState, ContextBias, DayState, SymbolMeta
from tests.engine.conftest import ARM_CFG, make_arm_series, make_series

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)
COST = CostModel(pip_size=0.0001, pip_value_per_lot_usd=10.0)


def _bt(bars):
    return [BTBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                  close=b.close, volume=b.volume, spread_pips=0.4) for b in bars]


def _engine(cfg=ARM_CFG):
    return EventDrivenBacktester(SessionBreakoutER(cfg), RiskGovernor(RiskConfig()), SM,
                                 COST, initial_balance=100_000.0)


def _req(bt):
    return BacktestRequest(strategy_name="SessionBreakoutER", config_version=0, config={},
                           data_set="fix", period=(bt[0].ts_open_utc, bt[-1].ts_open_utc),
                           walk_forward=WFSpec(1, 1, 1), trial_count=1)


# --- strategy arming contract ------------------------------------------------
def test_arms_on_final_or_bar_both_sides():
    arm_bars, now, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    res = SessionBreakoutER(ARM_CFG).evaluate(arm_bars, now, ContextBias.NORMAL, None)
    assert isinstance(res, ArmSignal)
    assert res.long is not None and res.long.direction is Direction.LONG
    assert res.short is not None and res.short.direction is Direction.SHORT
    assert res.long.entry_price > res.short.entry_price          # long above, short below
    assert res.long.entry_type == "stop" and res.short.entry_type == "stop"


def test_breakout_bar_is_not_an_arm_bar():
    # The full series' last bar is the FIRST post-OR bar -> arming already happened a bar ago.
    bars, now = make_series(date(2026, 6, 2), "trend_up")
    res = SessionBreakoutER(ARM_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(res, NoSignal) and res.reason == "not_arm_bar"


def test_building_opening_range_before_final_or_bar():
    arm_bars, _, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    # Drop the final OR bar -> last is now the FIRST OR bar (range still building).
    bars = arm_bars[:-1]
    now = bars[-1].ts_open_utc + timedelta(minutes=5)
    res = SessionBreakoutER(ARM_CFG).evaluate(bars, now, ContextBias.NORMAL, None)
    assert isinstance(res, NoSignal) and res.reason == "building_opening_range"


def test_gap_through_level_skips_that_side():
    arm_bars, now, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    # Force the final OR bar's CLOSE above the long level so a buy_stop cannot rest there.
    last = arm_bars[-1]
    arm_bars[-1] = last.__class__(**{**last.__dict__, "close": last.high + 0.0050})
    res = SessionBreakoutER(ARM_CFG).evaluate(arm_bars, now, ContextBias.NORMAL, None)
    assert isinstance(res, ArmSignal)
    assert res.long is None            # already through -> skipped
    assert res.short is not None


def test_expire_is_session_window_end_utc():
    arm_bars, now, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    res = SessionBreakoutER(ARM_CFG).evaluate(arm_bars, now, ContextBias.NORMAL, None)
    # Summer: London 16:00 window-end == 15:00 UTC.
    assert res.expire_utc.astimezone(timezone.utc).hour == 15


# --- decide.py OCO pair ------------------------------------------------------
def test_decide_entry_arms_oco_pair():
    arm_bars, now, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    d = decide_entry(SessionBreakoutER(ARM_CFG), RiskGovernor(RiskConfig()), arm_bars,
                     AccountState(equity=100_000.0, balance=100_000.0, currency="USD",
                                  ts_utc=now, is_fresh=True),
                     DayState(balance_0000=100_000.0, initial=100_000.0), SM, now,
                     ContextBias.NORMAL, None, client_id="EURUSD-T1", magic=42)
    assert d.action == "arm"
    assert len(d.intents) == 2
    sides = {i.side for i in d.intents}
    assert sides == {"buy", "sell"}
    assert all(i.order_kind == "stop" for i in d.intents)
    assert all(i.oco_group == "EURUSD-T1" for i in d.intents)         # shared OCO group
    assert all(i.expire_utc is not None for i in d.intents)
    assert {i.client_id for i in d.intents} == {"EURUSD-T1-long", "EURUSD-T1-short"}


# --- backtester touch-fill ---------------------------------------------------
def _with_followthrough(kind):
    bars, _ = make_series(date(2026, 6, 2), kind)
    bt = _bt(bars)
    last = bt[-1]; px = last.close; step = 0.0008 if kind == "trend_up" else -0.0008
    for k in range(1, 8):
        ts = last.ts_open_utc + timedelta(minutes=15 * k); px += step
        bt.append(BTBar(ts_open_utc=ts, open=px - step * 0.6, high=px + abs(step) * 0.5,
                        low=px - abs(step) * 0.5, close=px, spread_pips=0.4))
    return bt


def test_backtest_fills_long_on_upside_touch():
    bt = _with_followthrough("trend_up")
    rep = _engine().run_on_bars(bt, _req(bt))
    trades = rep.artifacts["trades"]
    assert rep.metrics["trade_count"] == 1
    assert trades[0].direction == "long"
    assert rep.ftmo["breaches"] == 0


def test_backtest_fills_short_on_downside_touch():
    bt = _with_followthrough("trend_down")
    rep = _engine().run_on_bars(bt, _req(bt))
    assert rep.metrics["trade_count"] == 1
    assert rep.artifacts["trades"][0].direction == "short"


def test_no_touch_in_window_means_no_trade():
    # OR bars then quiet post-OR bars that never reach either level before the window ends.
    arm_bars, _, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    bt = _bt(arm_bars)
    last = bt[-1]
    mid = last.close
    for k in range(1, 10):                      # tiny oscillation well inside the range
        ts = last.ts_open_utc + timedelta(minutes=15 * k)
        bt.append(BTBar(ts_open_utc=ts, open=mid, high=mid + 0.0001, low=mid - 0.0001,
                        close=mid, spread_pips=0.4))
    rep = _engine().run_on_bars(bt, _req(bt))
    assert rep.metrics["trade_count"] == 0


def test_both_sides_touched_one_bar_resolves_by_nearest_to_open():
    # Drive _try_fill_armed directly with a bar that spans BOTH levels.
    arm_bars, now, _ = make_arm_series(date(2026, 6, 2), "trend_up")
    arm = SessionBreakoutER(ARM_CFG).evaluate(arm_bars, now, ContextBias.NORMAL, None)
    eng = _engine()
    armed = _Armed(long=_ArmedSide(arm.long, 0.1), short=_ArmedSide(arm.short, 0.1),
                   expire_utc=arm.expire_utc)
    long_lvl, short_lvl = arm.long.entry_price, arm.short.entry_price
    day = DayState(balance_0000=100_000.0, initial=100_000.0)
    # Open sits nearer the SHORT level -> short should fill first.
    bar = BTBar(ts_open_utc=arm_bars[-1].ts_open_utc + timedelta(minutes=15),
                open=short_lvl + 0.0001, high=long_lvl + 0.0005, low=short_lvl - 0.0005,
                close=short_lvl, spread_pips=0.4)
    pos, _ = eng._try_fill_armed(armed, bar, bar.ts_open_utc, day, 99)
    assert pos is not None and pos.side == "short"
