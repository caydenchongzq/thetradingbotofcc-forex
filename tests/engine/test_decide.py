"""Per-bar live decision chain (live == backtest). spec 01+02 wiring (market entry)."""

from datetime import date, datetime, timezone

from src.common.config import RiskConfig
from src.engine.decide import decide_entry, decide_manage
from src.engine.strategy import ManageDecision
from src.risk.governor import RiskGovernor
from src.risk.types import AccountState, ContextBias, DayState, KillSwitchState, SymbolMeta
from tests.engine.conftest import DEFAULT_CFG, make_series
from src.engine import SessionBreakoutER

SM = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=50.0,
                lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001)
MAGIC = 770042


def _acct(eq=100_000.0, fresh=True):
    return AccountState(equity=eq, balance=eq, currency="USD",
                        ts_utc=datetime(2026, 6, 2, tzinfo=timezone.utc), is_fresh=fresh)


def _day(**over):
    return DayState(balance_0000=100_000.0, initial=100_000.0, **over)


def _decide(kind, acct=None, day=None, client_id="EURUSD-T1"):
    bars, now = make_series(date(2026, 6, 2), kind)
    return decide_entry(SessionBreakoutER(DEFAULT_CFG), RiskGovernor(RiskConfig()), bars,
                        acct or _acct(), day or _day(), SM, now, ContextBias.NORMAL, None,
                        client_id=client_id, magic=MAGIC)


def test_entry_chain_produces_market_order_intent():
    d = _decide("trend_up")
    assert d.action == "enter"
    assert d.intent is not None
    assert d.intent.side == "buy"
    assert d.intent.order_kind == "market"
    assert d.intent.volume_lots > 0
    assert d.intent.sl_price < d.intent.price
    assert d.intent.client_id == "EURUSD-T1" and d.intent.magic == MAGIC


def test_entry_vetoed_when_killswitch_halted():
    d = _decide("trend_up", day=_day(killswitch=KillSwitchState.HALTED))
    assert d.action == "vetoed" and d.intent is None


def test_no_signal_when_engine_declines():
    d = _decide("chop")
    assert d.action == "no_signal" and d.reason == "regime_gate_failed"


def test_stale_account_vetoes_entry():
    d = _decide("trend_up", acct=_acct(fresh=False))
    assert d.action == "vetoed" and d.reason == "stale_account"


class _CloseStrategy:
    def manage(self, ot, bars, now):
        return ManageDecision("close")


class _MoveSLStrategy:
    def manage(self, ot, bars, now):
        return ManageDecision("move_sl", sl_price=1.1000)


def test_manage_close_allowed_even_when_halted():
    gov = RiskGovernor(RiskConfig())
    d = decide_manage(_CloseStrategy(), gov, object(), [],
                      datetime(2026, 6, 2, tzinfo=timezone.utc),
                      _acct(), _day(killswitch=KillSwitchState.FLATTEN))
    assert d.action == "close"


def test_manage_move_sl_returns_new_sl():
    gov = RiskGovernor(RiskConfig())
    d = decide_manage(_MoveSLStrategy(), gov, object(), [],
                      datetime(2026, 6, 2, tzinfo=timezone.utc), _acct(), _day())
    assert d.action == "modify_sl" and d.new_sl == 1.1000
