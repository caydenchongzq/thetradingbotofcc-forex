"""Drift detection + graduated-response policy (spec 06 §5) — deterministic.

A CUSUM on trade expectancy flags decay; the policy table maps the state to an action.
Crucially, risk-reducing actions (reduce / stand-down) are OWNED BY THE RISK GOVERNOR
(spec 02), not executed by the agent layer — the AI only explains and proposes."""

from __future__ import annotations

from dataclasses import dataclass


def cusum_low(values, target: float, k: float) -> float:
    """Peak of the one-sided lower CUSUM — grows when values run below ``target`` by > k.
    Detects sustained downward drift in expectancy."""
    s = 0.0
    peak = 0.0
    for x in values:
        s = max(0.0, s + (target - k - x))
        peak = max(peak, s)
    return peak


def cusum_state(values, target: float, k: float, h_warn: float, h_alarm: float) -> str:
    peak = cusum_low(values, target, k)
    if peak >= h_alarm:
        return "alarm"
    if peak >= h_warn:
        return "warning"
    return "ok"


@dataclass(frozen=True)
class DriftAction:
    action: str   # "log" | "flag_retune" | "reduce_shadow" | "stand_down"
    owner: str    # "none" | "researcher" | "governor"
    note: str = ""


def drift_action(state: str, *, breach_risk: bool = False,
                 regime_break: bool = False) -> DriftAction:
    """Map a drift state to an action and its OWNER (spec 06 §5).

    Stand-down and risk reduction are routed to the Governor, never executed here."""
    if breach_risk or regime_break:
        return DriftAction("stand_down", "governor",
                           "deterministic Governor halts new entries (spec 02)")
    if state == "alarm":
        return DriftAction("reduce_shadow", "governor",
                           "Governor rule may cut risk_fraction; candidate retune in shadow")
    if state == "warning":
        return DriftAction("flag_retune", "researcher",
                           "raise flag -> Researcher proposes; nothing changes live")
    return DriftAction("log", "none", "within tolerance")
