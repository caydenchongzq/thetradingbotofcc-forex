"""Trial ledger (spec 06 §5/§8) — append-only, cannot decrement, feeds the DSR."""

from src.agents.ledger import TrialLedger, iso_week
from datetime import datetime, timezone


def test_cumulative_count_dedupes_by_proposal_id(tmp_path):
    led = TrialLedger(tmp_path)
    led.record("p1", "2026-W23", "researcher", "proposed")
    led.record("p1", "2026-W23", "researcher", "failed")     # same proposal, 2 entries
    led.record("p2", "2026-W23", "researcher", "proposed")
    led.record("p2", "2026-W23", "researcher", "passed")
    assert led.cumulative_count() == 2                        # two distinct hypotheses
    assert led.count_in_period("2026-W23") == 2


def test_budget_remaining_and_no_decrement_method(tmp_path):
    led = TrialLedger(tmp_path)
    for i in range(4):
        led.record(f"p{i}", "2026-W23", "researcher", "failed")
    assert led.budget_remaining("2026-W23", cap=4) == 0
    # different week is unaffected
    assert led.budget_remaining("2026-W24", cap=4) == 4
    # there is no API to decrement / reset the count
    assert not hasattr(led, "delete") and not hasattr(led, "reset")


def test_count_persists_across_instances(tmp_path):
    TrialLedger(tmp_path).record("p1", "2026-W23", "r", "proposed")
    assert TrialLedger(tmp_path).cumulative_count() == 1   # reload from disk


def test_iso_week_format():
    assert iso_week(datetime(2026, 6, 2, tzinfo=timezone.utc)).startswith("2026-W")
