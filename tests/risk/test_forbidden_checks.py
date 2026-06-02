"""The 13-item forbidden-practice checklist + request budget + manage (spec 02 §6/§7/§8)."""

from src.risk import Decision, RiskGovernor
from src.risk.types import ManageAction, SymbolMeta
from tests.risk.conftest import NOW, account, day, signal


def _approve(cfg, eurusd, **sig):
    g = RiskGovernor(cfg)
    return g.evaluate_entry(signal(**sig), account(), day(), NOW, eurusd)


# 1 — feed error / stale tick
def test_feed_error_veto(cfg, eurusd):
    # signal price diverges from latest quote by > tolerance (2 pips).
    d = _approve(cfg, eurusd, signal_price=1.0900, reference_price=1.0880)  # 20 pips
    assert d.decision is Decision.VETO and d.reason == "feed_error_or_stale_tick"
    assert d.checks["no_feed_error"] is False


def test_feed_ok_within_tolerance(cfg, eurusd):
    d = _approve(cfg, eurusd, signal_price=1.08742, reference_price=1.08745)
    assert d.approved


# 2 — request budget
def test_request_soft_cap_vetoes_entry(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(), account(),
                         day(requests_used_today=cfg.request_soft_cap), NOW, eurusd)
    assert d.decision is Decision.VETO and d.reason == "request_budget_low"


def test_requests_remaining_reported(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(), account(), day(requests_used_today=100), NOW, eurusd)
    assert d.requests_remaining == cfg.request_hard_cap - 100


# 3 — news blackout
def test_news_blackout_veto(cfg, eurusd):
    d = _approve(cfg, eurusd, news_blackout_active=True)
    assert d.decision is Decision.VETO and d.reason == "news_blackout"


# 4 — gap rule
def test_gap_rule_veto(cfg, eurusd):
    d = _approve(cfg, eurusd, near_session_gap=True)
    assert d.decision is Decision.VETO and d.reason == "gap_rule"


# 5 — consistent sizing
def test_inconsistent_size_veto(cfg, eurusd):
    g = RiskGovernor(cfg)
    # trailing median ~ 35 USD; a ~350 USD trade is way outside +/-50% band.
    d = g.evaluate_entry(signal(), account(),
                         day(recent_risk_usds=(35.0, 36.0, 34.0)), NOW, eurusd)
    assert d.decision is Decision.VETO and d.reason == "inconsistent_position_size"


def test_consistent_size_ok(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(), account(),
                         day(recent_risk_usds=(340.0, 350.0, 360.0)), NOW, eurusd)
    assert d.approved


# 6 — hedging
def test_hedging_veto(cfg, eurusd):
    d = _approve(cfg, eurusd, opposing_position_open=True)
    assert d.decision is Decision.VETO and d.reason == "hedging_forbidden"


# 7 — martingale
def test_martingale_veto(cfg, eurusd):
    d = _approve(cfg, eurusd, adds_to_losing_same_dir=True)
    assert d.decision is Decision.VETO and d.reason == "martingale_forbidden"


# 8 — grid
def test_grid_veto(cfg, eurusd):
    d = _approve(cfg, eurusd, pending_orders_count=cfg.max_concurrent_pendings)
    assert d.decision is Decision.VETO and d.reason == "grid_forbidden"


# 9 — max concurrent risk
def test_max_concurrent_risk_veto(cfg, eurusd):
    g = RiskGovernor(cfg)
    # max_concurrent = 1% of 100k = 1000 ; existing open risk 900 + new ~350 > 1000.
    d = g.evaluate_entry(signal(), account(), day(open_risk_usd=900.0), NOW, eurusd)
    assert d.decision is Decision.VETO and d.reason == "max_concurrent_risk_exceeded"


# 10 — max trades/day
def test_max_trades_per_day_veto(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(), account(),
                         day(trades_opened_today=cfg.max_trades_per_day), NOW, eurusd)
    assert d.decision is Decision.VETO and d.reason == "max_trades_per_day_reached"


# 11 — min stop / stops level
def test_sl_below_stops_level_veto(cfg):
    g = RiskGovernor(cfg)
    sm = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, stops_level_pips=15.0)
    d = g.evaluate_entry(signal(sl_pips=10.0), account(), day(), NOW, sm)
    assert d.decision is Decision.VETO and d.reason == "sl_below_broker_stops_level"


# 12 — stale account
def test_stale_account_veto(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(), account(fresh=False), day(), NOW, eurusd)
    assert d.decision is Decision.VETO and d.reason == "stale_account"


# 13 — floor protection backstop (deep drawdown so the overall floor binds)
def test_floor_protection_backstop_veto(cfg, eurusd):
    g = RiskGovernor(cfg)
    # equity 91k, overall floor 90k; large existing open risk makes projected loss
    # cross the floor -> must veto.
    d = g.evaluate_entry(signal(), account(equity=91_000, balance=91_000),
                         day(balance_0000=92_000, open_risk_usd=1_500.0), NOW, eurusd)
    assert d.decision is Decision.VETO
    assert d.reason in ("would_breach_floor", "killswitch_allowance_exceeded",
                        "max_concurrent_risk_exceeded")


def test_all_checks_recorded_in_audit(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(), account(), day(), NOW, eurusd)
    # The full checklist is recorded for audit even on approval.
    for key in ("no_feed_error", "request_budget_ok", "news_blackout_clear",
                "gap_rule_clear", "consistent_sizing", "no_hedging", "no_martingale",
                "no_grid", "max_concurrent_risk", "max_trades_per_day",
                "min_stop_compliance", "no_stale_account", "floor_protection"):
        assert key in d.checks


# ---- manage actions ----
def test_risk_reducing_manage_always_allowed_even_halted(cfg):
    g = RiskGovernor(cfg)
    from src.risk.types import KillSwitchState
    d = g.evaluate_manage(ManageAction(kind="close", risk_increasing=False),
                          account(equity=20_000, balance=100_000),
                          day(killswitch=KillSwitchState.FLATTEN,
                              requests_used_today=cfg.request_hard_cap + 50), NOW)
    assert d.approved and d.reason == "risk_reducing_allowed"


def test_risk_increasing_manage_blocked_when_halted(cfg):
    from src.risk.types import KillSwitchState
    g = RiskGovernor(cfg)
    d = g.evaluate_manage(ManageAction(kind="add", risk_increasing=True),
                          account(), day(killswitch=KillSwitchState.HALTED), NOW)
    assert d.decision is Decision.VETO
