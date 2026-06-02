"""MT5 adapter behaviour via FakeBroker (spec 03 §4, §7, §9)."""

from datetime import datetime, timezone

import pytest

from src.common.config import ExecutionConfig, MT5Config
from src.execution import IntentStatus, MT5Execution, OrderIntent
from src.execution.broker import TRADE_RETCODE_DONE
from tests.execution.conftest import MAGIC, FakeBroker, SpyJournal


def _intent(client_id="cid-1", kind="market", side="buy"):
    return OrderIntent(
        client_id=client_id, magic=MAGIC, instrument="EURUSD", side=side, order_kind=kind,
        volume_lots=0.1, price=1.16527, sl_price=1.16300, tp_prices=(1.16800,),
        expire_utc=None, comment=f"entry {client_id}",
    )


def _adapter(broker, journal, fund=lambda n, rr: True):
    return MT5Execution(
        broker=broker, journal=journal,
        mt5_cfg=MT5Config(login=1513571406, password="x", server="FTMO-Demo"),
        exec_cfg=ExecutionConfig(magic=MAGIC, symbol="EURUSD"),
        fund_request=fund,
    )


def test_connect_verifies_account(state_dir):
    j = SpyJournal(state_dir, [])
    a = _adapter(FakeBroker(), j)
    a.connect(sleep=lambda s: None)  # no raise -> account matched
    j.close()


def test_connect_rejects_wrong_account(state_dir):
    from src.execution.adapter import AccountMismatch
    b = FakeBroker()
    b.account = b.account.__class__(login=999, server="FTMO-Demo", currency="USD",
                                    balance=1, equity=1, trade_mode=0)
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j)
    with pytest.raises(AccountMismatch):
        a.connect(sleep=lambda s: None)
    j.close()


def test_place_persists_intended_before_order_send(state_dir):
    events: list = []
    b = FakeBroker()
    b.events = events
    j = SpyJournal(state_dir, events)
    a = _adapter(b, j)
    res = a.place(_intent())
    assert res.status is IntentStatus.FILLED
    # The first INTENDED journal write precedes the first order_send (persist-before-act).
    first_intended = next(i for i, e in enumerate(events)
                          if e[0] == "journal" and e[2] == "intended")
    first_send = next(i for i, e in enumerate(events) if e[0] == "order_send")
    assert first_intended < first_send
    j.close()


def test_place_is_idempotent_no_double_position(state_dir):
    b = FakeBroker()
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j)
    a.place(_intent("cid-9"))
    sends_after_first = sum(1 for e in b.events if e[0] == "order_send")
    a.place(_intent("cid-9"))   # same client_id -> must detect existing, not resend
    sends_after_second = sum(1 for e in b.events if e[0] == "order_send")
    assert sends_after_first == 1
    assert sends_after_second == 1               # no second send
    assert len(b.positions_get("EURUSD")) == 1   # only one position ever opened
    j.close()


def test_terminal_reject_marks_rejected(state_dir):
    b = FakeBroker()
    b.retcode_sequence = [10019]  # no money -> terminal
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j)
    res = a.place(_intent())
    assert res.status is IntentStatus.REJECTED
    j.close()


def test_retryable_then_success(state_dir):
    b = FakeBroker()
    b.retcode_sequence = [10004, TRADE_RETCODE_DONE]  # requote, then done
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j)
    res = a.place(_intent())
    assert res.status is IntentStatus.FILLED
    j.close()


def test_unfunded_entry_refused_no_send(state_dir):
    b = FakeBroker()
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j, fund=lambda n, rr: rr)  # only risk-reducing gets funded
    res = a.place(_intent())
    assert res.status is IntentStatus.REJECTED
    assert res.error == "request_budget_unfunded"
    assert not any(e[0] == "order_send" for e in b.events)  # never sent
    j.close()


def test_close_always_funded_even_when_entries_unfunded(state_dir):
    b = FakeBroker()
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j, fund=lambda n, rr: rr)  # entries unfunded; closes funded
    pos = b.add_position("entry x")
    res = a.close(pos.ticket)
    assert res.status is IntentStatus.FILLED
    assert b.positions_get("EURUSD") == []     # position closed
    j.close()


def test_reconcile_marks_filled_and_reports(state_dir):
    b = FakeBroker()
    j = SpyJournal(state_dir, [])
    # An open intent + a live position carrying that client_id -> FILLED on reconcile.
    j.append({"record_type": "intent", "schema_version": 3,
              "ts_utc": "2026-06-02T14:00:00Z", "client_id": "cid-1",
              "status": "sent", "order_kind": "market", "magic": MAGIC})
    b.add_position("entry cid-1")
    a = _adapter(b, j)
    report = a.reconcile_on_startup()
    assert report.matched == 1
    assert report.flatten_required is False
    j.close()


def test_health_freshness_is_advance_based(state_dir):
    # Freshness must track whether ticks ADVANCE, not wall-clock delta (FTMO ticks are
    # in server time, so absolute deltas are offset by hours).
    b = FakeBroker()
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j)

    # First sighting -> fresh.
    h1 = a.health(now_epoch=1_000_000.0)
    assert h1.data_fresh is True

    # Same tick, long wall-time later -> stale (feed frozen).
    h2 = a.health(now_epoch=1_000_000.0 + 10_000)
    assert h2.data_fresh is False

    # Tick advances -> fresh again, regardless of the (server-tz) absolute timestamp.
    b.symbol = b.symbol.__class__(**{**b.symbol.__dict__,
                                     "tick_time_epoch": b.symbol.tick_time_epoch + 1})
    h3 = a.health(now_epoch=1_000_000.0 + 10_010)
    assert h3.data_fresh is True
    j.close()


def test_confirm_reads_fill_by_ticket_not_comment(state_dir):
    # Broker drops the comment; confirmation must still capture fill price + position id
    # via the order/deal tickets returned by order_send.
    b = FakeBroker()
    orig_send = b.order_send

    def send_dropping_comment(order):
        res = orig_send(order)
        # simulate FTMO clearing the comment on the stored position
        b._positions = [p.__class__(**{**p.__dict__, "comment": ""}) for p in b._positions]
        return res

    b.order_send = send_dropping_comment
    j = SpyJournal(state_dir, [])
    a = _adapter(b, j)
    res = a.place(_intent("cid-tick"))
    assert res.status is IntentStatus.FILLED
    assert res.fill_price is not None and res.fill_price > 0
    assert res.broker_position_id is not None
    assert abs(res.slippage_pips) < 5  # sane slippage, not a garbage value
    j.close()


def test_reconcile_matches_by_ticket_when_comment_lost(state_dir):
    b = FakeBroker()
    j = SpyJournal(state_dir, [])
    # Intent recorded with a broker_position_id but the live position has NO comment.
    pos = b.add_position("", ticket=5555)
    j.append({"record_type": "intent", "schema_version": 3,
              "ts_utc": "2026-06-02T14:00:00Z", "client_id": "cid-x", "status": "sent",
              "order_kind": "market", "magic": MAGIC, "broker_position_id": 5555})
    a = _adapter(b, j)
    report = a.reconcile_on_startup()
    assert report.matched == 1            # matched by ticket, not comment
    assert report.adopted == 0
    assert report.flatten_required is False
    j.close()
