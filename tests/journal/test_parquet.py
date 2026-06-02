"""Parquet snapshot integration (spec 04 §8)."""

from __future__ import annotations

import pandas as pd

from src.journal import Journal
from tests.conftest import trade_entry, trade_exit


def test_snapshot_parquet_reproduces_trade_outcomes(state_dir):
    j = Journal(state_dir)
    j.append(trade_entry("T1"))
    j.update_trade("T1", trade_exit("T1", outcome={"r_multiple": 1.5}))
    j.append(trade_entry("T2", ts_utc="2026-06-03T14:00:00Z"))
    j.update_trade("T2", trade_exit("T2", ts_utc="2026-06-03T15:00:00Z",
                                    outcome={"r_multiple": -1.0}))
    j.snapshot_parquet()
    j.close()

    df = pd.read_parquet(state_dir / "parquet" / "trades" / "snapshot.parquet")
    assert len(df) == 2
    r = df["outcome.r_multiple"].dropna().tolist()
    assert sorted(r) == [-1.0, 1.5]
