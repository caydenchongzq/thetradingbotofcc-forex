"""End-to-end live loop with a FakeBroker (no MT5).

Incumbent SessionBreakoutER: close-confirmation -> a single MARKET order (live-placeable, no
retcode-10015). The resting-stop OCO lifecycle (arm both legs, cancel sibling on fill, expire
past window) is exercised via the DEV strategy SessionBreakoutERResting."""

from datetime import date, timedelta

from src.common.config import load_config
from src.engine.run import LiveEngine, session_date
from src.execution.adapter import MT5Execution
from src.execution.broker import RateBar
from src.journal import Journal
from tests.engine.conftest import ARM_CFG, DEFAULT_CFG, make_arm_series, make_series
from tests.execution.conftest import FakeBroker
from src.engine import SessionBreakoutER
from src.engine.strategy_resting import SessionBreakoutERResting


def _rate(b, spread=4):
    return RateBar(time=int(b.ts_open_utc.timestamp()), open=b.open, high=b.high,
                   low=b.low, close=b.close, tick_volume=b.volume, spread=spread)


def _engine(cfg, broker, journal, strategy):
    eng = LiveEngine(cfg)
    eng._exec = MT5Execution(broker, journal, cfg.mt5, cfg.execution,
                             fund_request=lambda n, rr: True)
    eng._strategy = strategy
    eng._active_version = 2
    return eng


# ============================ incumbent: single MARKET order ============================
def test_incumbent_places_one_market_order_on_breakout(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng_bars, now = make_series(date(2026, 6, 2), "trend_up")
    broker = FakeBroker(); broker.server_offset_s = 0
    broker.rates = [_rate(b) for b in eng_bars]
    broker.rates.append(RateBar(time=int((eng_bars[-1].ts_open_utc + timedelta(minutes=15)).timestamp()),
                                open=eng_bars[-1].close, high=eng_bars[-1].close + 0.0002,
                                low=eng_bars[-1].close - 0.0002, close=eng_bars[-1].close,
                                tick_volume=5, spread=4))
    journal = Journal(tmp_path / "state")
    eng = _engine(cfg, broker, journal, SessionBreakoutER(DEFAULT_CFG))
    eng._last_session_date = session_date(now, eng._strategy.tz)
    eng._on_tick(now)
    sends = sum(1 for e in broker.events if e[0] == "order_send")
    pos = [p for p in broker.positions_get() if p.magic == cfg.execution.magic]
    assert sends == 1 and len(pos) == 1
    ds = journal.get_day_state()
    assert ds.trades_opened_today == 1 and ds.open_risk_usd > 0
    journal.close()


def test_incumbent_idempotent_same_bar(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng_bars, now = make_series(date(2026, 6, 2), "trend_up")
    broker = FakeBroker(); broker.server_offset_s = 0
    broker.rates = [_rate(b) for b in eng_bars]
    broker.rates.append(RateBar(time=int((eng_bars[-1].ts_open_utc + timedelta(minutes=15)).timestamp()),
                                open=1.10, high=1.1002, low=1.0998, close=1.10, tick_volume=5, spread=4))
    journal = Journal(tmp_path / "state")
    eng = _engine(cfg, broker, journal, SessionBreakoutER(DEFAULT_CFG))
    eng._last_session_date = session_date(now, eng._strategy.tz)
    eng._on_tick(now); eng._on_tick(now)
    assert sum(1 for e in broker.events if e[0] == "order_send") == 1
    journal.close()


def test_deep_loss_flattens_and_latches(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng_bars, now = make_series(date(2026, 6, 2), "trend_up")
    broker = FakeBroker(); broker.server_offset_s = 0
    broker.rates = [_rate(b) for b in eng_bars]
    broker.rates.append(RateBar(time=int((eng_bars[-1].ts_open_utc + timedelta(minutes=15)).timestamp()),
                                open=1.10, high=1.1002, low=1.0998, close=1.10, tick_volume=5, spread=4))
    av = broker.account
    broker.account = av.__class__(login=av.login, server=av.server, currency="USD",
                                  balance=100_000.0, equity=95_740.0, trade_mode=0,
                                  leverage=100, name="x")
    broker.add_position("open-trade")
    journal = Journal(tmp_path / "state")
    from src.ops import killswitch_engaged
    eng = _engine(cfg, broker, journal, SessionBreakoutER(DEFAULT_CFG))
    eng._last_session_date = session_date(now, eng._strategy.tz)
    eng._on_tick(now)
    assert broker.positions_get("EURUSD") == []
    assert killswitch_engaged(tmp_path / "state")
    journal.close()


# ============================ resting-stop OCO lifecycle (dev strategy) ============================
def _arm_setup(tmp_path, cfg):
    arm_bars, now, breakout = make_arm_series(date(2026, 6, 2), "trend_up")
    broker = FakeBroker(); broker.server_offset_s = 0; broker.rest_pendings = True
    broker.rates = [_rate(b) for b in arm_bars] + [_rate(breakout)]
    journal = Journal(tmp_path / "state")
    eng = _engine(cfg, broker, journal, SessionBreakoutERResting(ARM_CFG))
    eng._last_session_date = session_date(now, eng._strategy.tz)
    return eng, broker, journal, now, breakout


def test_resting_arms_oco_pair(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng, broker, journal, now, _ = _arm_setup(tmp_path, cfg)
    eng._on_tick(now)
    assert sum(1 for e in broker.events if e[0] == "order_send") == 2
    assert len([o for o in broker.orders_get() if o.magic == cfg.execution.magic]) == 2
    assert [p for p in broker.positions_get() if p.magic == cfg.execution.magic] == []
    ds = journal.get_day_state()
    assert ds.requests_used_today == 2 and ds.trades_opened_today == 0 and ds.open_risk_usd == 0.0
    journal.close()


def test_resting_fill_cancels_sibling_and_accrues_risk(tmp_path, monkeypatch):
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng, broker, journal, now, breakout = _arm_setup(tmp_path, cfg)
    eng._on_tick(now)
    buy = next(o for o in broker.orders_get() if o.type == 0)
    broker.fill_pending(buy.ticket)
    broker.rates.append(RateBar(time=int((breakout.ts_open_utc + timedelta(minutes=15)).timestamp()),
                                open=breakout.close, high=breakout.close, low=breakout.close,
                                close=breakout.close, tick_volume=5, spread=4))
    eng._on_tick(breakout.ts_open_utc + timedelta(minutes=5))
    assert [o for o in broker.orders_get() if o.magic == cfg.execution.magic] == []
    assert len([p for p in broker.positions_get() if p.magic == cfg.execution.magic]) == 1
    assert journal.get_day_state().open_risk_usd > 0
    journal.close()


def test_resting_legs_carry_their_own_broker_expiry(tmp_path, monkeypatch):
    # The executor does NOT reach into the strategy's session window to expire orders. Each
    # resting leg is placed WITH its own expiry (expire_utc -> ORDER_TIME_SPECIFIED), so the
    # broker auto-expires it. This is the generic mechanism that replaced the window helper.
    monkeypatch.setenv("TBOT_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(config_file="config/default.yaml")
    eng, broker, journal, now, _ = _arm_setup(tmp_path, cfg)
    eng._on_tick(now)
    legs = [o for o in broker.sent_orders if o.action == "pending"]
    assert len(legs) == 2
    assert all(o.expire_epoch is not None for o in legs)     # broker will expire them
    journal.close()
