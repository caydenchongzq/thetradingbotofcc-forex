"""JournalReader read-only + analytics tests (spec 04 §4/§8)."""

from __future__ import annotations

import pytest

from src.journal import Journal
from src.journal.reader import JournalReader, ReadOnlyViolation
from tests.conftest import trade_entry, trade_exit


def _seed(state_dir):
    j = Journal(state_dir)
    j.append(trade_entry("T1"))
    j.update_trade("T1", trade_exit("T1", outcome={"r_multiple": 1.5, "mae_pips": 3.0}))
    j.append(trade_entry("T2", ts_utc="2026-06-03T14:00:00Z"))
    j.update_trade("T2", trade_exit("T2", ts_utc="2026-06-03T15:00:00Z",
                                    outcome={"r_multiple": -1.0, "mae_pips": 11.0}))
    j.close()


def test_reader_is_read_only(state_dir):
    _seed(state_dir)
    r = JournalReader(state_dir)
    # No write methods exist; attribute assignment is blocked.
    with pytest.raises(ReadOnlyViolation):
        r.something = 1  # type: ignore[attr-defined]
    assert not hasattr(r, "append")
    r.close()


def test_reader_cannot_write_sqlite(state_dir):
    _seed(state_dir)
    r = JournalReader(state_dir)
    with pytest.raises(Exception):  # sqlite raises on write to a ro connection
        r._conn.execute("DELETE FROM trades")
    r.close()


def test_expectancy_numbers(state_dir):
    _seed(state_dir)
    r = JournalReader(state_dir)
    exp = r.expectancy()
    assert exp["n"] == 2
    assert exp["avg_r"] == pytest.approx(0.25)
    assert exp["win_rate"] == pytest.approx(0.5)
    assert exp["profit_factor"] == pytest.approx(1.5)  # 1.5 / 1.0
    r.close()


def test_trades_filter_by_since(state_dir):
    _seed(state_dir)
    r = JournalReader(state_dir)
    df = r.trades(since="2026-06-03T00:00:00Z")
    assert len(df) == 1
    assert df.iloc[0]["trade_id"] == "T2"
    r.close()
