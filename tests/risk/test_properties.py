"""Property-based guarantees (spec 02 §10) — the load-bearing safety tests.

The single most important test in the codebase: for randomized account/order state,
**if the Governor does not VETO, a full stop-out cannot cross either FTMO floor.**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.risk import Decision, RiskGovernor
from src.risk.envelope import compute_envelope
from src.risk.types import ContextBias
from tests.risk.conftest import NOW, account, day, signal


def _g():
    from src.common.config import RiskConfig
    return RiskGovernor(RiskConfig())


@settings(max_examples=400, deadline=None)
@given(
    equity=st.floats(min_value=90_500, max_value=110_000, allow_nan=False),
    balance_0000=st.floats(min_value=95_500, max_value=110_000, allow_nan=False),
    sl_pips=st.floats(min_value=1.0, max_value=200.0, allow_nan=False),
    open_risk=st.floats(min_value=0.0, max_value=900.0, allow_nan=False),
    bias=st.sampled_from(list(ContextBias)),
)
def test_no_approved_order_can_breach_a_floor(equity, balance_0000, sl_pips, open_risk, bias):
    from src.risk.types import SymbolMeta
    sm = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, pip_size=0.0001)
    g = _g()
    d = g.evaluate_entry(
        signal(sl_pips=sl_pips, context_bias=bias),
        account(equity=equity, balance=balance_0000),
        day(balance_0000=balance_0000, initial=100_000, open_risk_usd=open_risk),
        NOW, sm,
    )
    if d.decision is Decision.VETO:
        return
    env = compute_envelope(balance_0000, 100_000, equity)
    projected_loss = d.risk_usd + open_risk
    after = equity - projected_loss
    # STRICT: a full stop-out (buffered) plus existing open risk stays above both floors.
    assert after > env.daily_floor_equity
    assert after > env.overall_floor_equity


@settings(max_examples=200, deadline=None)
@given(
    sl_small=st.floats(min_value=5.0, max_value=20.0),
    delta=st.floats(min_value=1.0, max_value=50.0),
)
def test_larger_sl_never_increases_lots(sl_small, delta):
    from src.risk.types import SymbolMeta
    sm = SymbolMeta(symbol="EURUSD", pip_value_per_lot_usd=10.0, pip_size=0.0001)
    g = _g()
    small = g.evaluate_entry(signal(sl_pips=sl_small), account(), day(), NOW, sm)
    large = g.evaluate_entry(signal(sl_pips=sl_small + delta), account(), day(), NOW, sm)
    # Monotonic: a wider stop can only reduce (or hold) lot size.
    assert large.lots <= small.lots + 1e-9


@settings(max_examples=150, deadline=None)
@given(
    equity=st.floats(min_value=88_000, max_value=101_000),
    requests=st.integers(min_value=0, max_value=2_500),
)
def test_risk_reducing_manage_never_vetoed_by_killswitch(equity, requests):
    from src.risk.types import KillSwitchState, ManageAction
    g = _g()
    d = g.evaluate_manage(
        ManageAction(kind="close", risk_increasing=False),
        account(equity=equity, balance=100_000),
        day(killswitch=KillSwitchState.FLATTEN, requests_used_today=requests),
        NOW,
    )
    assert d.approved
