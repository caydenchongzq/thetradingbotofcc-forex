"""Drift CUSUM + graduated-response policy (spec 06 §5/§8)."""

from src.agents.drift import cusum_state, drift_action


def test_cusum_ok_when_expectancy_holds():
    vals = [0.30, 0.28, 0.32, 0.31, 0.29]
    assert cusum_state(vals, target=0.25, k=0.02, h_warn=0.3, h_alarm=0.6) == "ok"


def test_cusum_warns_then_alarms_on_sustained_decay():
    decaying = [0.0, -0.05, -0.1, -0.12, -0.15, -0.2]   # well below target
    st = cusum_state(decaying, target=0.25, k=0.02, h_warn=0.3, h_alarm=0.6)
    assert st == "alarm"


def test_policy_routes_reduce_and_standdown_to_governor():
    # warning -> researcher retune; nothing changes live
    assert drift_action("warning").action == "flag_retune"
    assert drift_action("warning").owner == "researcher"
    # alarm -> Governor reduces risk (not the agent)
    assert drift_action("alarm").owner == "governor"
    assert drift_action("alarm").action == "reduce_shadow"
    # breach risk / regime break -> Governor stand-down, regardless of CUSUM state
    sd = drift_action("ok", breach_risk=True)
    assert sd.action == "stand_down" and sd.owner == "governor"


def test_ok_state_is_log_only():
    a = drift_action("ok")
    assert a.action == "log" and a.owner == "none"
