"""Per-bar live decision (spec 01 + 02 wiring) — pure, the same chain the backtester runs.

This is the bridge that turns an engine ``Signal`` into a risk-approved ``OrderIntent``
for the execution adapter. Keeping it pure (no MT5, no I/O) means the live decision is
unit-tested and provably identical to what the backtester validated: live == backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.engine.strategy import ManageDecision, to_risk_signal
from src.engine.types import ArmSignal, NoSignal, Signal
from src.execution.types import OrderIntent
from src.risk.governor import RiskGovernor
from src.risk.types import AccountState, ContextBias, DayState, RiskDecision, SymbolMeta

_SIDE = {"long": "buy", "short": "sell"}


@dataclass
class LiveDecision:
    action: str                       # enter | arm | vetoed | no_signal | close | modify_sl | hold
    reason: str = ""
    intent: OrderIntent | None = None
    risk_decision: RiskDecision | None = None
    signal: Signal | None = None
    new_sl: float | None = None
    # Resting-stop OCO arm (action == "arm"): both pending legs + their sizing, sharing one
    # oco_group. ``arm`` is the originating ArmSignal (regime/levels for journaling).
    intents: tuple[OrderIntent, ...] = ()
    risk_decisions: tuple[RiskDecision, ...] = ()
    oco_group: str | None = None
    arm: ArmSignal | None = None


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

    Returns action 'no_signal' (engine declined), 'vetoed' (Governor refused), 'enter'
    (a single market/stop OrderIntent), or 'arm' (a resting-stop OCO pair). Identical to
    the backtester's entry path."""
    sig = strategy.evaluate(bars, now, context_bias, calendar)
    if isinstance(sig, ArmSignal):
        return _decide_arm(
            sig, governor, account, day, symbol_meta, now,
            client_id=client_id, magic=magic, reference_price=reference_price,
            opposing_position_open=opposing_position_open,
            adds_to_losing_same_dir=adds_to_losing_same_dir,
            pending_orders_count=pending_orders_count, near_session_gap=near_session_gap)
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


def _decide_arm(
    arm: ArmSignal, governor: RiskGovernor, account: AccountState, day: DayState,
    symbol_meta: SymbolMeta, now: datetime, *, client_id: str, magic: int,
    reference_price: float | None, opposing_position_open: bool,
    adds_to_losing_same_dir: bool, pending_orders_count: int, near_session_gap: bool,
) -> LiveDecision:
    """Size each armable side through the Governor and build an OCO pair of pending stop
    OrderIntents. Lots are fixed HERE (at arm/OR-end); each leg fills later on an intrabar
    touch. The pair shares one ``oco_group`` so the runner cancels the sibling on the first
    fill. A side that the Governor vetoes (or that sits inside the broker stops_level) is
    simply dropped — the other side can still rest."""
    group = client_id
    intents: list[OrderIntent] = []
    decisions: list[RiskDecision] = []
    pend = pending_orders_count
    for side_sig in (arm.long, arm.short):
        if side_sig is None:
            continue
        ref = reference_price if reference_price is not None else side_sig.entry_price
        # Broker minimum stop distance: a stop within stops_level of the market is illegal
        # to rest. Skip that side (live-only micro-guard; vanishingly rare for EURUSD).
        if symbol_meta.stops_level_pips and symbol_meta.pip_size:
            dist_pips = abs(side_sig.entry_price - ref) / symbol_meta.pip_size
            if dist_pips < symbol_meta.stops_level_pips:
                continue
        rsig = to_risk_signal(
            side_sig, reference_price=ref, news_blackout_active=False,
            near_session_gap=near_session_gap, opposing_position_open=opposing_position_open,
            adds_to_losing_same_dir=adds_to_losing_same_dir, pending_orders_count=pend)
        dec = governor.evaluate_entry(rsig, account, day, now, symbol_meta)
        if not dec.approved or dec.lots <= 0:
            continue
        cid = f"{client_id}-{side_sig.direction.value}"
        intents.append(OrderIntent(
            client_id=cid, magic=magic, instrument=side_sig.instrument,
            side=_SIDE[side_sig.direction.value], order_kind="stop", volume_lots=dec.lots,
            price=side_sig.entry_price, sl_price=side_sig.exit_plan.initial_sl_price,
            tp_prices=tuple(side_sig.exit_plan.targets), expire_utc=arm.expire_utc,
            comment=cid, oco_group=group))
        decisions.append(dec)
        pend += 1
    if not intents:
        return LiveDecision("vetoed", reason="arm_unsized_or_blocked", arm=arm)
    return LiveDecision(
        "arm", reason="armed", intents=tuple(intents), risk_decisions=tuple(decisions),
        oco_group=group, arm=arm, risk_decision=decisions[0], intent=intents[0])


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
