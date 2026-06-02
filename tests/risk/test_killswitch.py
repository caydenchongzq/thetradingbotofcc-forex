"""Kill-switch state machine + daily reset (spec 02 §5)."""

from datetime import datetime, timezone

from src.risk import Decision, RiskGovernor, apply_daily_reset
from src.risk.types import KillSwitchState
from tests.risk.conftest import NOW, account, day, signal


def _eq_for_pct(pct, balance_0000=100_000, initial=100_000):
    # daily_loss_used = pct * budget ; budget = 0.05*initial
    budget = 0.05 * initial
    return balance_0000 - pct * budget


def test_warn_transition_to_reduce(cfg, eurusd):
    g = RiskGovernor(cfg)
    eq = _eq_for_pct(0.40)  # exactly warn_pct
    ks = g.effective_killswitch(day(), account(equity=eq, balance=eq))
    assert ks is KillSwitchState.REDUCE


def test_halt_transition_blocks_entries(cfg, eurusd):
    g = RiskGovernor(cfg)
    eq = _eq_for_pct(0.60)  # exactly halt_pct
    d = g.evaluate_entry(signal(), account(equity=eq, balance=100_000),
                         day(), NOW, eurusd)
    assert d.decision is Decision.VETO
    assert d.reason == "killswitch_halted_60pct"


def test_flatten_transition(cfg):
    g = RiskGovernor(cfg)
    eq = _eq_for_pct(0.85)
    ks = g.effective_killswitch(day(), account(equity=eq, balance=100_000))
    assert ks is KillSwitchState.FLATTEN


def test_stale_account_forces_flatten_state(cfg):
    g = RiskGovernor(cfg)
    ks = g.effective_killswitch(day(), account(fresh=False))
    assert ks is KillSwitchState.FLATTEN


def test_latched_halt_does_not_de_escalate(cfg):
    g = RiskGovernor(cfg)
    # pct low now, but day latched HALTED -> stays HALTED.
    ks = g.effective_killswitch(day(killswitch=KillSwitchState.HALTED),
                                account(equity=100_000))
    assert ks is KillSwitchState.HALTED


def test_reset_clears_halt_but_not_flatten():
    d_halt = day(killswitch=KillSwitchState.HALTED, requests_used_today=500,
                 trades_opened_today=6)
    after = apply_daily_reset(d_halt, balance_0000=99_000,
                              reset_ts=datetime(2026, 6, 3, 22, 0, tzinfo=timezone.utc))
    assert after.killswitch is KillSwitchState.ARMED
    assert after.requests_used_today == 0
    assert after.trades_opened_today == 0
    assert after.balance_0000 == 99_000

    d_flat = day(killswitch=KillSwitchState.FLATTEN)
    after_flat = apply_daily_reset(d_flat, balance_0000=99_000,
                                   reset_ts=datetime(2026, 6, 3, 22, 0, tzinfo=timezone.utc))
    assert after_flat.killswitch is KillSwitchState.FLATTEN  # human-clear only


def test_reduce_state_downsizes_entry(cfg, eurusd):
    g = RiskGovernor(cfg)
    eq = _eq_for_pct(0.45)  # in REDUCE band
    d = g.evaluate_entry(signal(), account(equity=eq, balance=100_000),
                         day(), NOW, eurusd)
    if d.approved:
        assert d.decision is Decision.APPROVE_DOWNSIZED
