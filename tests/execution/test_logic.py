"""Pure execution logic (spec 03 §4-§6)."""

from src.execution.broker import DealView, PendingView, PositionView, TRADE_RETCODE_DONE
from src.execution.logic import (
    classify_reconciliation,
    classify_retcode,
    find_existing_for_client,
    slippage_pips,
)
from src.execution.types import IntentStatus

MAGIC = 770042


def _pos(comment, magic=MAGIC, ticket=1):
    return PositionView(ticket=ticket, symbol="EURUSD", magic=magic, type=0, volume=0.1,
                        price_open=1.16, sl=1.158, tp=1.165, comment=comment)


def _deal(comment, magic=MAGIC, ticket=1):
    return DealView(ticket=ticket, order=ticket, position_id=ticket, symbol="EURUSD",
                    magic=magic, volume=0.1, price=1.16, commission=-3.5, time_epoch=1,
                    comment=comment, entry=0)


def test_classify_retcode():
    assert classify_retcode(TRADE_RETCODE_DONE) == "done"
    assert classify_retcode(10004) == "rejected_retryable"   # requote
    assert classify_retcode(10019) == "rejected_terminal"    # no money


def test_slippage_sign():
    # Buy filled higher than requested -> positive (worse).
    assert slippage_pips(1.10000, 1.10003, 0.0001, "buy") > 0
    # Sell filled higher than requested -> negative slippage convention (better).
    assert slippage_pips(1.10000, 1.10003, 0.0001, "sell") < 0
    assert slippage_pips(None, 1.1, 0.0001, "buy") is None


def test_find_existing_by_client_id():
    assert find_existing_for_client("cid-1", [_pos("entry cid-1")], [])
    assert find_existing_for_client("cid-1", [], [_deal("entry cid-1")])
    assert not find_existing_for_client("cid-2", [_pos("entry cid-1")], [])


# --- reconciliation matrix (the crown jewel) ---
def test_crash_after_intended_before_send_market_holds():
    # Market intent, no position, no deal -> UNKNOWN + flatten_required (never resend).
    intents = [{"client_id": "cid-1", "status": "intended", "order_kind": "market"}]
    out = classify_reconciliation(intents, [], [], [], MAGIC)
    assert out.flatten_required is True
    assert out.resolutions[0].resolved_status is IntentStatus.UNKNOWN
    assert out.resolutions[0].needs_attention is True


def test_crash_after_send_before_confirm_with_position_is_filled():
    intents = [{"client_id": "cid-1", "status": "sent", "order_kind": "market"}]
    out = classify_reconciliation(intents, [_pos("entry cid-1")], [], [], MAGIC)
    assert out.resolutions[0].resolved_status is IntentStatus.FILLED
    assert out.flatten_required is False
    assert out.matched == 1


def test_pending_expired_no_fill_is_cancelled():
    intents = [{"client_id": "cid-1", "status": "sent", "order_kind": "stop"}]
    out = classify_reconciliation(intents, [], [], [], MAGIC)
    assert out.resolutions[0].resolved_status is IntentStatus.CANCELLED
    assert out.flatten_required is False


def test_pending_still_live_stays_sent():
    pend = PendingView(ticket=5, symbol="EURUSD", magic=MAGIC, type=4, volume_current=0.1,
                       price_open=1.17, sl=1.16, tp=1.18, comment="entry cid-1")
    intents = [{"client_id": "cid-1", "status": "sent", "order_kind": "stop"}]
    out = classify_reconciliation(intents, [], [pend], [], MAGIC)
    assert out.resolutions[0].resolved_status is IntentStatus.SENT


def test_live_position_no_intent_is_adopted():
    out = classify_reconciliation([], [_pos("manual")], [], [], MAGIC)
    assert len(out.adopted_positions) == 1


def test_foreign_magic_position_is_ignored():
    out = classify_reconciliation([], [_pos("someone else", magic=999999)], [], [], MAGIC)
    assert out.adopted_positions == []
    assert out.live_positions == []
