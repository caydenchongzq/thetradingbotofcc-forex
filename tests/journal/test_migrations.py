"""Schema migration tests (spec 04 §5/§8)."""

from __future__ import annotations

from src.journal.migrations import migrate_to_latest
from src.journal.schema import SCHEMA_VERSION


def test_v2_trade_migrates_to_v3_with_model_vs_real():
    v2_trade = {
        "record_type": "trade",
        "trade_id": "EURUSD-2026-05-01-0001",
        "config_version": 40,
        "schema_version": 2,
        "ts_utc": "2026-05-01T10:00:00Z",
        "outcome": {"r_multiple": 0.8},
    }
    out = migrate_to_latest(v2_trade)
    assert out["schema_version"] == SCHEMA_VERSION == 3
    assert "model_vs_real" in out
    # Missing data is recorded as None, never fabricated.
    assert out["model_vs_real"]["realized_slippage_pips"] is None
    # Original data preserved.
    assert out["outcome"]["r_multiple"] == 0.8


def test_v3_record_is_unchanged():
    v3 = {"record_type": "reject", "schema_version": 3, "config_version": 1,
          "ts_utc": "2026-06-02T00:00:00Z", "record_id": "r1", "reason": "x"}
    assert migrate_to_latest(dict(v3)) == v3


def test_non_trade_v2_still_bumps_version():
    v2 = {"record_type": "reject", "schema_version": 2, "config_version": 1,
          "ts_utc": "2026-05-01T00:00:00Z", "record_id": "r1", "reason": "x"}
    out = migrate_to_latest(v2)
    assert out["schema_version"] == 3
    assert "model_vs_real" not in out  # only trades get that block
