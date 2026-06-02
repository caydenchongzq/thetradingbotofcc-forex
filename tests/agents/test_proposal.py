"""Proposal allowed-lever validation (spec 06 §3) — the 'LLM cannot widen authority' boundary."""

from src.agents.proposal import Proposal, validate_proposal


def _prop(diff, parent=47, status="proposed"):
    return Proposal.from_dict({
        "proposal_id": "2026-06-02-w23-001",
        "parent_config_version": parent,
        "author": "strategy_researcher",
        "created_utc": "2026-06-02T18:05:00Z",
        "hypothesis": "tighten ER gate",
        "diff": diff,
        "status": status,
    })


def test_valid_lever_diff_passes():
    p = _prop([{"param": "regime.er_threshold", "from": 0.30, "to": 0.38},
               {"param": "session.opening_range_minutes", "from": 30, "to": 45}])
    res = validate_proposal(p, parent_config_version=47)
    assert res.ok, res.errors


def test_touching_risk_namespace_is_rejected():
    p = _prop([{"param": "risk.base_risk_fraction", "from": 0.0035, "to": 0.01}])
    res = validate_proposal(p, parent_config_version=47)
    assert not res.ok
    assert any("forbidden" in e for e in res.errors)


def test_touching_gates_is_rejected():
    p = _prop([{"param": "gates.min_expectancy", "from": 0.10, "to": 0.0}])
    res = validate_proposal(p, parent_config_version=47)
    assert not res.ok


def test_unknown_param_rejected():
    p = _prop([{"param": "regime.secret_backdoor", "from": 1, "to": 2}])
    res = validate_proposal(p, parent_config_version=47)
    assert not res.ok
    assert any("allowed-lever" in e for e in res.errors)


def test_stale_parent_version_rejected():
    p = _prop([{"param": "regime.er_threshold", "from": 0.30, "to": 0.38}], parent=40)
    res = validate_proposal(p, parent_config_version=47)
    assert not res.ok


def test_empty_diff_rejected():
    res = validate_proposal(_prop([]), parent_config_version=47)
    assert not res.ok


def test_bad_status_rejected():
    p = _prop([{"param": "breakout.buffer_pips", "from": 1.5, "to": 2.0}], status="promoted_lol")
    res = validate_proposal(p, parent_config_version=47)
    assert not res.ok
