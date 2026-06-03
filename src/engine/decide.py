"""Per-bar live decision (spec 01 + 02 wiring) — pure, the same chain the backtester runs.

This is the bridge that turns an engine ``Signal`` into a risk-approved ``OrderIntent``
for the execution adapter. Keeping it pure (no MT5, no I/O) means the live decision is
unit-tested and provably identical to what the backtester validated: live == backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.engine.strategy import ManageDecision, to_risk_signal
from src.engine.types import NoSignal, Signal
from src.execution.types import OrderIntent
from src.risk.governor import RiskGovernor
from src.risk.types import AccountState, ContextBias, DayState, RiskDecision, SymbolMeta

_SIDE = {"long": "buy", "short": "sell"}


@dataclass
class LiveDecision:
    action: str                       # enter | vetoed | no_signal | close | modify_sl | hold
    reason: str = ""
    intent: OrderIntent | None = None
    risk_decision: RiskDecision | None = None
    signal: Signal | None = None
    new_sl: float | None = None


def build_entry_intent(sig: Signal, dec: RiskDecision, magic: int, client_id: str,
                       expire_utc: datetime | None = None) -> OrderIntent:
    """Translate an approved breakout Signal + sized RiskDecision into an OrderIntent."""
    return OrderIntent(
        client_id=client_id, magic=magic, instrument=sig.instrument,
        side=_SIDE[sig.direction.value], order_kind=sig.entry_type,  # "stop" breakout
        volume_lots=dec.lots, price=sig.entry_price,
        sl_price=sig.exit_plan.initial_sl_price, tp_prices=tuple(sig.exit_plan.targets),
        expire_utc=expire_utc, comment=client_id,
    )


def decide_entry(
    strategy, governor: RiskGovernor, bars, account: AccountState, day: DayState,
    symbol_meta: SymbolMeta, now: datetime, context_bias: ContextBias, calendar,
    *, client_id: str, magic: int, reference_price: float | None = None,
    opposing_position_open: bool = False, adds_to_losing_same_dir: bool = False,
    pending_orders_count: int = 0, near_session_gap: bool = False,
    expire_utc: datetime | None = None,
) -> LiveDecision:
    """Run the full entry chain: evaluate -> to_risk_signal -> Governor -> OrderIntent.

    Returns action 'no_signal' (engine declined), 'vetoed' (Governor refused), or 'enter'
    (an OrderIntent the adapter should place). Identical to the backtester's entry path."""
    sig = strategy.evaluate(bars, now, context_bias, calendar)
    if not isinstance(sig, Signal):
        reason = sig.reason if isinstance(sig, NoSignal) else "no_signal"
        return LiveDecision("no_signal", reason=reason)

    rsig = to_risk_signal(
        sig, reference_price=reference_price if reference_price is not None else sig.entry_price,
        news_blackout_active=False, near_session_gap=near_session_gap,
        opposing_position_open=opposing_position_open,
        adds_to_losing_same_dir=adds_to_losing_same_dir,
        pending_orders_count=pending_orders_count,
    )
    dec = governor.evaluate_entry(rsig, account, day, now, symbol_meta)
    if not dec.approved or dec.lots <= 0:
        return LiveDecision("vetoed", reason=dec.reason, risk_decision=dec, signal=sig)

    intent = build_entry_intent(sig, dec, magic=magic, client_id=client_id,
                                expire_utc=expire_utc)
    return LiveDecision("enter", reason="approved", intent=intent, risk_decision=dec, signal=sig)


def decide_manage(
    strategy, governor: RiskGovernor, open_trade_view, bars, now: datetime,
    account: AccountState, day: DayState,
) -> LiveDecision:
    """Run the management chain. Risk-reducing actions (close / move-SL toward BE) are
    always allowed by the Governor; only risk-increasing ones are gated (spec 02 §3)."""
    from src.risk.types import ManageAction
    md = strategy.manage(open_trade_view, bars, now)
    if not isinstance(md, ManageDecision) or md.kind == "hold":
        return LiveDecision("hold", reason="hold")
    if md.kind in ("close", "close_all"):
        d = governor.evaluate_manage(ManageAction("close", risk_increasing=False),
                                     account, day, now)
        return LiveDecision("close" if d.approved else "hold", reason=d.reason)
    if md.kind == "move_sl":
        d = governor.evaluate_manage(ManageAction("move_sl", risk_increasing=False),
                                     account, day, now)
        return LiveDecision("modify_sl" if d.approved else "hold", reason=d.reason,
                            new_sl=md.sl_price)
    return LiveDecision("hold", reason=f"unhandled:{md.kind}")
