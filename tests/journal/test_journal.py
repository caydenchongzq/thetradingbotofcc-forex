"""Journal unit tests (spec 04 §8)."""

from __future__ import annotations

import json

import pytest

from src.journal import Journal, SchemaError
from src.journal.schema import to_jsonl
from src.risk.types import DayState, KillSwitchState
from tests.conftest import health, intent, reject, trade_entry, trade_exit


def _read_jsonl_lines(journal_dir):
    lines = []
    for path in sorted(journal_dir.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as fh:
            lines.extend(line.rstrip("\n") for line in fh if line.strip())
    return lines


def test_roundtrip_all_record_types(state_dir):
    j = Journal(state_dir)
    recs = [trade_entry(), reject(), health(), intent()]
    for r in recs:
        j.append(r)

    # JSONL line is byte-stable for the canonical serialisation.
    lines = _read_jsonl_lines(j.journal_dir)
    assert to_jsonl(trade_entry()) in lines

    # Read back from SQLite.
    assert j._get_trade_record("EURUSD-2026-06-02-0317") is not None
    assert len(j.open_intents()) == 1
    j.close()


def test_staged_trade_merges_to_final_row(state_dir):
    j = Journal(state_dir)
    j.append(trade_entry())
    j.update_trade("EURUSD-2026-06-02-0317", trade_exit())

    rec = j._get_trade_record("EURUSD-2026-06-02-0317")
    # Entry fields survive...
    assert rec["signal"]["direction"] == "long"
    assert rec["sizing"]["lots"] == 0.32
    # ...and exit fields are merged in.
    assert rec["outcome"]["r_multiple"] == 1.42
    assert rec["fills"]["exit_reason"] == "trail_step"

    # The SQLite indexed columns reflect the merged outcome.
    row = j._conn.execute(
        "SELECT r_multiple, vol_state FROM trades WHERE trade_id=?",
        ("EURUSD-2026-06-02-0317",),
    ).fetchone()
    assert row["r_multiple"] == 1.42
    assert row["vol_state"] == "normal"
    j.close()


def test_rebuild_sqlite_from_jsonl_is_idempotent(state_dir):
    j = Journal(state_dir)
    j.append(trade_entry())
    j.update_trade("EURUSD-2026-06-02-0317", trade_exit())
    j.append(reject())
    j.append(health())

    def dump():
        return {
            "trades": j._conn.execute(
                "SELECT trade_id, record FROM trades ORDER BY trade_id"
            ).fetchall(),
            "rejects": j._conn.execute(
                "SELECT record_id FROM rejects ORDER BY record_id"
            ).fetchall(),
        }

    before = [dict(r) for r in dump()["trades"]]
    j.rebuild_sqlite_from_jsonl()
    after_once = [dict(r) for r in dump()["trades"]]
    j.rebuild_sqlite_from_jsonl()
    after_twice = [dict(r) for r in dump()["trades"]]

    assert before == after_once == after_twice
    j.close()


def test_partial_tail_truncation_recovery(state_dir):
    j = Journal(state_dir)
    j.append(trade_entry())
    path = next(j.journal_dir.glob("*.jsonl"))
    j.close()

    # Simulate a crash mid-append: write a partial (newline-less) line.
    with open(path, "ab") as fh:
        fh.write(b'{"record_type":"trade","trade_id":"PARTIAL"')  # no newline

    # Reopening must truncate the partial line and recover cleanly.
    j2 = Journal(state_dir)
    lines = _read_jsonl_lines(j2.journal_dir)
    assert all("PARTIAL" not in ln for ln in lines)
    assert j2._get_trade_record("EURUSD-2026-06-02-0317") is not None
    assert j2._get_trade_record("PARTIAL") is None
    j2.close()


def test_day_state_roundtrip(state_dir):
    from datetime import datetime, timezone

    j = Journal(state_dir)
    assert j.get_day_state() is None
    ds = DayState(
        balance_0000=100_000.0,
        initial=100_000.0,
        requests_used_today=12,
        killswitch=KillSwitchState.REDUCE,
        open_risk_usd=350.0,
        trades_opened_today=2,
        reset_ts_utc=datetime(2026, 6, 2, 22, 0, tzinfo=timezone.utc),
        recent_risk_usds=(354.31, 360.0),
    )
    j.put_day_state(ds)
    got = j.get_day_state()
    assert got.balance_0000 == 100_000.0
    assert got.killswitch is KillSwitchState.REDUCE
    assert got.requests_used_today == 12
    assert got.recent_risk_usds == (354.31, 360.0)
    j.close()


def test_append_rejects_malformed_record(state_dir):
    j = Journal(state_dir)
    with pytest.raises(SchemaError):
        j.append({"record_type": "trade", "ts_utc": "2026-06-02T14:00:00Z"})  # no trade_id
    with pytest.raises(SchemaError):
        j.append({"record_type": "bogus", "ts_utc": "2026-06-02T14:00:00Z",
                  "schema_version": 3, "record_id": "x"})
    j.close()


def test_no_unjournaled_state_survives_restart(state_dir):
    """Everything appended is durable across a fresh Journal (cold boot)."""
    j = Journal(state_dir)
    j.append(trade_entry())
    j.append(intent(client_id="cid-XYZ"))
    j.close()

    j2 = Journal(state_dir)
    assert j2._get_trade_record("EURUSD-2026-06-02-0317") is not None
    assert any(i["client_id"] == "cid-XYZ" for i in j2.open_intents())
    j2.close()
