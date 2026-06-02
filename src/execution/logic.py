"""Pure execution logic (spec 03 §4–§6) — no MT5, no I/O, fully unit-testable.

These are the correctness-critical pieces: idempotency, fill confirmation, startup
reconciliation classification, retcode mapping, and slippage. They operate on the
neutral broker views so a FakeBroker can drive them in tests.

Matching is by broker TICKET first, then client_id-in-comment, because some brokers
(FTMO among them) do not preserve our order comment — so a ticket recorded at SENT is
the reliable idempotency/reconciliation key.
"""

from __future__ import annotations

from dataclasses import dataclass

from .broker import (
    RETRYABLE_RETCODES,
    TRADE_RETCODE_DONE,
    DealView,
    PendingView,
    PositionView,
)
from .types import IntentStatus

TERMINAL_STATUSES = frozenset({
    IntentStatus.FILLED, IntentStatus.REJECTED, IntentStatus.CANCELLED,
})


def classify_retcode(retcode: int) -> str:
    """Map an order_send retcode to a category (spec 03 §6)."""
    if retcode == TRADE_RETCODE_DONE:
        return "done"
    if retcode in RETRYABLE_RETCODES:
        return "rejected_retryable"
    return "rejected_terminal"


def slippage_pips(req_price: float | None, fill_price: float | None, pip_size: float,
                  side: str) -> float | None:
    """Signed slippage in pips: POSITIVE = worse than requested (paid up on a buy,
    received less on a sell). None when either price is missing."""
    if req_price is None or not fill_price or not pip_size:
        return None
    raw = (fill_price - req_price) / pip_size
    return raw if side == "buy" else -raw


def find_existing_for_client(
    client_id: str, positions: list[PositionView], deals: list[DealView],
    broker_position_id: int | None = None,
) -> bool:
    """Idempotency check: does a position/deal for this intent already exist? Matches by
    recorded ticket first (comment-independent), then by client_id in the comment."""
    if broker_position_id is not None:
        if any(p.ticket == broker_position_id for p in positions):
            return True
        if any(d.position_id == broker_position_id for d in deals):
            return True
    if client_id and any(client_id in (p.comment or "") for p in positions):
        return True
    return bool(client_id) and any(client_id in (d.comment or "") for d in deals)


@dataclass(frozen=True)
class IntentResolution:
    client_id: str
    resolved_status: IntentStatus
    position_ticket: int | None
    needs_attention: bool
    note: str


@dataclass(frozen=True)
class ReconcileOutcome:
    resolutions: list[IntentResolution]
    adopted_positions: list[PositionView]
    live_positions: list[PositionView]
    flatten_required: bool

    @property
    def matched(self) -> int:
        return sum(1 for r in self.resolutions if r.resolved_status is IntentStatus.FILLED)

    @property
    def orphaned_intents(self) -> int:
        return sum(1 for r in self.resolutions if r.needs_attention)


def _match_position(intent: dict, positions: list[PositionView]) -> PositionView | None:
    bpid = intent.get("broker_position_id")
    cid = str(intent.get("client_id", ""))
    if bpid is not None:
        hit = next((p for p in positions if p.ticket == bpid), None)
        if hit is not None:
            return hit
    if cid:
        return next((p for p in positions if cid in (p.comment or "")), None)
    return None


def classify_reconciliation(
    intents: list[dict],
    positions: list[PositionView],
    pendings: list[PendingView],
    deals: list[DealView],
    our_magic: int,
) -> ReconcileOutcome:
    """Reconcile persisted intents against MT5 (the source of truth), spec 03 §5.
    MT5 wins. We NEVER resend; ambiguity resolves to hold/flatten."""
    our_positions = [p for p in positions if p.magic == our_magic]
    our_pendings = [o for o in pendings if o.magic == our_magic]
    our_deals = [d for d in deals if d.magic == our_magic]

    resolutions: list[IntentResolution] = []
    flatten_required = False
    matched_tickets: set[int] = set()

    for intent in intents:
        status = IntentStatus(intent.get("status", "unknown"))
        if status in TERMINAL_STATUSES:
            continue
        cid = str(intent.get("client_id", ""))
        bpid = intent.get("broker_position_id")

        pos = _match_position(intent, our_positions)
        deal = next((d for d in our_deals
                     if (bpid is not None and d.position_id == bpid)
                     or (cid and cid in (d.comment or ""))), None)

        if pos is not None:
            matched_tickets.add(pos.ticket)
            resolutions.append(IntentResolution(cid, IntentStatus.FILLED, pos.ticket,
                                                False, "matched_live_position"))
        elif deal is not None:
            resolutions.append(IntentResolution(cid, IntentStatus.FILLED, None,
                                                False, "matched_recent_deal"))
        else:
            was_pending = intent.get("order_kind") in ("stop", "limit")
            live_pending = any(cid and cid in (o.comment or "") for o in our_pendings)
            if was_pending and not live_pending:
                resolutions.append(IntentResolution(cid, IntentStatus.CANCELLED, None,
                                                    False, "pending_expired_no_fill"))
            elif was_pending and live_pending:
                resolutions.append(IntentResolution(cid, IntentStatus.SENT, None,
                                                    False, "pending_still_live"))
            else:
                flatten_required = True
                resolutions.append(IntentResolution(cid, IntentStatus.UNKNOWN, None,
                                                    True, "no_position_or_deal_hold"))

    # OUR live positions with no matching intent -> adopt + alert.
    adopted = [p for p in our_positions if p.ticket not in matched_tickets
               and not any(str(i.get("client_id", "")) and str(i.get("client_id", "")) in (p.comment or "")
                           for i in intents)]
    return ReconcileOutcome(resolutions=resolutions, adopted_positions=adopted,
                            live_positions=our_positions, flatten_required=flatten_required)
