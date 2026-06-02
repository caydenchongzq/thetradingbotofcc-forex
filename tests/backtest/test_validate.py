"""Shared promotion verdict (spec 05 §6/§7)."""

from dataclasses import dataclass, field

from src.backtest.validate import lockbox_passes, walkforward_verdict


@dataclass
class FakeWF:
    folds_profitable: int = 6
    folds_scored: int = 7
    stitched_collapse: bool = False
    severe_collapse: bool = False
    lockbox_metrics: dict | None = field(
        default_factory=lambda: {"expectancy_r": 0.29, "profit_factor": 2.0, "trade_count": 69})


def test_lockbox_gate():
    assert lockbox_passes({"expectancy_r": 0.2, "profit_factor": 1.5, "trade_count": 40})
    assert not lockbox_passes({"expectancy_r": 0.05, "profit_factor": 1.5, "trade_count": 40})
    assert not lockbox_passes({"expectancy_r": 0.2, "profit_factor": 1.1, "trade_count": 40})
    assert lockbox_passes(None)  # no lockbox configured -> not a blocker


def test_verdict_passes_when_all_conditions_hold():
    v = walkforward_verdict(True, FakeWF())
    assert v.passed and v.majority_ok and v.lockbox_ok


def test_in_sample_fail_sinks_verdict():
    assert not walkforward_verdict(False, FakeWF()).passed


def test_severe_or_stitched_collapse_sinks_verdict():
    assert not walkforward_verdict(True, FakeWF(severe_collapse=True)).passed
    assert not walkforward_verdict(True, FakeWF(stitched_collapse=True)).passed


def test_minority_of_profitable_folds_fails():
    assert not walkforward_verdict(True, FakeWF(folds_profitable=3, folds_scored=7)).passed
