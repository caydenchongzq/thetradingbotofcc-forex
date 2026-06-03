"""End-to-end live loop with a FakeBroker (no MT5): a breakout bar -> a placed order.

Exercises LiveEngine._on_tick through the real strategy + governor + execution adapter +
journal, proving the live path works before it ever touches a broker."""

from datetime import date, timedelta

from src.common.config import load_config
from src.engine.run import LiveEngine, session_date
from src.execution.adapter import MT5Execution
from src.execution.broker import RateBar
from src.journal import Journal
from tests.engine.conftest import DEFAULT_CFG, make_series
from tests.execution.conftest import FakeBroker


def _rate_from_bar(b):
    return RateBar(time=int(b.ts_open_utc.timestamp()), open=b.open, high=b.high,
                   low=b.low, close=b.close, tick_volume=b.volume, spread=4)


def test_live_loop_places_order_on_breakout(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")

    eng_bars, now = make_series(date(2026, 6, 2), "trend_up")
    broker = FakeBroker()
    broker.server_offset_s = 0   # server == UTC for a clean timing test
    broker.rates = [_rate_from_bar(b) for b in eng_bars]
    # add a still-forming bar at the end; recent_closed_bars must drop it
    last = eng_bars[-1]
    broker.rates.append(RateBar(time=int((last.ts_open_utc + timedelta(minutes=15)).timestamp()),
                                open=last.close, high=last.close + 0.0002,
                                low=last.close - 0.0002, close=last.close + 0.0001,
                                tick_volume=10, spread=4))

    journal = Journal(tmp_path / "state")
    from src.engine import SessionBreakoutER
    eng = LiveEngine(cfg)
    eng._exec = MT5Execution(broker, journal, cfg.mt5, cfg.execution,
                             fund_request=lambda n, rr: True)
    eng._strategy = SessionBreakoutER(DEFAULT_CFG)
    eng._active_version = 2
    eng._last_session_date = session_date(now, eng._strategy.tz)   # skip config reload

    sends_before = sum(1 for e in broker.events if e[0] == "order_send")
    eng._on_tick(now)
    sends_after = sum(1 for e in broker.events if e[0] == "order_send")

    assert sends_after == sends_before + 1                 # exactly one order placed
    ours = [p for p in broker.positions_get() if p.magic == cfg.execution.magic]
    assert len(ours) == 1                                  # a position now exists, by our magic
    # the trade entry was journaled (the R5 contract record)
    assert journal._get_trade_record(ours[0].comment) is not None or \
        any(True for _ in journal.open_intents())          # intent persisted at least
    journal.close()


def test_live_loop_idempotent_same_bar(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng_bars, now = make_series(date(2026, 6, 2), "trend_up")
    broker = FakeBroker(); broker.server_offset_s = 0
    broker.rates = [_rate_from_bar(b) for b in eng_bars]
    broker.rates.append(RateBar(time=int((eng_bars[-1].ts_open_utc + timedelta(minutes=15)).timestamp()),
                                open=1.10, high=1.1002, low=1.0998, close=1.10, tick_volume=5, spread=4))
    journal = Journal(tmp_path / "state")
    from src.engine import SessionBreakoutER
    eng = LiveEngine(cfg)
    eng._exec = MT5Execution(broker, journal, cfg.mt5, cfg.execution, fund_request=lambda n, rr: True)
    eng._strategy = SessionBreakoutER(DEFAULT_CFG)
    eng._active_version = 2
    eng._last_session_date = session_date(now, eng._strategy.tz)

    eng._on_tick(now)
    eng._on_tick(now)   # same bar again -> must NOT act twice
    sends = sum(1 for e in broker.events if e[0] == "order_send")
    assert sends == 1
    journal.close()
