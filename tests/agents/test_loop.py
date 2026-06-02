"""Gated proposal pipeline (spec 06 §4/§6/§8) — backtester is the arbiter."""

from dataclasses import dataclass

from src.agents.config_store import ConfigStore
from src.agents.ledger import TrialLedger
from src.agents.loop import approve_and_promote, process_proposal

BASE = {"config_version": 1, "regime": {"er_threshold": 0.30}, "exits": {"atr_mult_sl": 1.2}}


@dataclass
class FakeReport:
    passed: bool


def _proposal(pid="2026-06-02-w23-001", parent=1, to=0.38, param="regime.er_threshold"):
    return {"proposal_id": pid, "parent_config_version": parent, "author": "researcher",
            "created_utc": "2026-06-02T18:00:00Z", "hypothesis": "tighten ER",
            "diff": [{"param": param, "from": 0.30, "to": to}], "status": "proposed"}


def _stores(tmp_path):
    return ConfigStore(tmp_path, BASE), TrialLedger(tmp_path)


def test_invalid_lever_rejected_before_backtest(tmp_path):
    store, led = _stores(tmp_path)
    called = []
    out = process_proposal(_proposal(param="risk.base_risk_fraction"), store, led,
                           lambda c, n: called.append(1) or FakeReport(True),
                           period="2026-W23")
    assert out.status == "rejected_validation"
    assert called == []                       # never reached the backtester
    assert led.cumulative_count() == 0        # not counted as a trial


def test_passing_proposal_records_trial_and_yields_candidate(tmp_path):
    store, led = _stores(tmp_path)
    out = process_proposal(_proposal(), store, led, lambda c, n: FakeReport(True),
                           period="2026-W23")
    assert out.status == "passed"
    assert out.candidate_config["regime"]["er_threshold"] == 0.38
    assert led.cumulative_count() == 1
    # trial_count fed to the backtester reflects the cumulative count
    assert out.trial_count == 1


def test_failing_proposal_still_counts_as_a_trial(tmp_path):
    store, led = _stores(tmp_path)
    out = process_proposal(_proposal(), store, led, lambda c, n: FakeReport(False),
                           period="2026-W23")
    assert out.status == "failed"
    assert out.candidate_config is None
    assert led.cumulative_count() == 1        # failures count too (anti-snooping)


def test_trial_count_rises_and_tightens_over_proposals(tmp_path):
    store, led = _stores(tmp_path)
    seen = []
    for i in range(3):
        process_proposal(_proposal(pid=f"p{i}"), store, led,
                         lambda c, n: seen.append(n) or FakeReport(False),
                         period="2026-W23", weekly_cap=10)
    assert seen == [1, 2, 3]                   # DSR bar rises with each hypothesis


def test_weekly_budget_blocks_further_proposals(tmp_path):
    store, led = _stores(tmp_path)
    for i in range(4):
        process_proposal(_proposal(pid=f"p{i}"), store, led, lambda c, n: FakeReport(False),
                         period="2026-W23", weekly_cap=4)
    out = process_proposal(_proposal(pid="p5"), store, led, lambda c, n: FakeReport(True),
                           period="2026-W23", weekly_cap=4)
    assert out.status == "budget_exhausted"


def test_passed_then_human_approve_promotes(tmp_path):
    store, led = _stores(tmp_path)
    out = process_proposal(_proposal(), store, led, lambda c, n: FakeReport(True),
                           period="2026-W23")
    new_v = approve_and_promote(_proposal(), store, out.candidate_config, approver="human")
    assert new_v == 2
    assert store.head_version() == 2
    assert store.get_config(2)["regime"]["er_threshold"] == 0.38
