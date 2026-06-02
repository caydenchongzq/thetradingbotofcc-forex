"""Property-based crash-recovery test (spec 04 §8).

For any sequence of appends plus a crash at a random byte offset, startup recovery
yields a consistent state with no duplicated or lost *committed* records. A committed
record is one whose JSONL line was fully written (ends in a newline); a record whose
trailing bytes were lost to the crash is, by definition, not committed.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.journal import Journal
from src.journal.schema import to_jsonl
from tests.conftest import reject, trade_entry


def _build_records(n: int) -> list[dict]:
    recs: list[dict] = []
    for i in range(n):
        if i % 2 == 0:
            recs.append(trade_entry(f"T{i}", ts_utc="2026-06-02T14:00:00Z"))
        else:
            recs.append(reject(record_id=f"reject-EURUSD-2026-06-02T13:00:00Z-{i}"))
    return recs


@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(n=st.integers(min_value=1, max_value=12), cut=st.floats(0.0, 1.0))
def test_random_crash_offset_recovers_consistently(tmp_path_factory, n, cut):
    state_dir = tmp_path_factory.mktemp("st")
    records = _build_records(n)

    # Write the full canonical JSONL by hand into a single day file.
    journal_dir = state_dir / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / "2026-06-02.jsonl"
    full = "".join(to_jsonl(r) + "\n" for r in records).encode("utf-8")

    # Truncate at a random byte offset to simulate a crash mid-stream.
    offset = int(len(full) * cut)
    with open(path, "wb") as fh:
        fh.write(full[:offset])

    # Committed records = those whose full line (with newline) fits in [:offset].
    committed_bytes = full[:offset]
    last_nl = committed_bytes.rfind(b"\n")
    committed_text = committed_bytes[: last_nl + 1].decode("utf-8") if last_nl >= 0 else ""
    committed_keys = set()
    for line in committed_text.splitlines():
        if not line.strip():
            continue
        import json

        rec = json.loads(line)
        key = rec["trade_id"] if rec["record_type"] == "trade" else rec["record_id"]
        committed_keys.add(key)

    # Recovery happens on open.
    j = Journal(state_dir)
    trade_ids = {row["trade_id"] for row in
                 j._conn.execute("SELECT trade_id FROM trades").fetchall()}
    reject_ids = {row["record_id"] for row in
                  j._conn.execute("SELECT record_id FROM rejects").fetchall()}
    recovered = trade_ids | reject_ids

    # No committed record lost, no phantom (uncommitted) record present.
    assert recovered == committed_keys
    j.close()
