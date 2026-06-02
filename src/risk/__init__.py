"""Risk Governor (spec 02) — deterministic gatekeeper with veto power."""

from .governor import RiskGovernor, apply_daily_reset
from .envelope import Envelope, compute_envelope
from .types import (
    AccountState,
    ContextBias,
    Decision,
    DayState,
    ExitPlan,
    KillSwitchState,
    ManageAction,
    RiskDecision,
    Signal,
    SymbolMeta,
)

__all__ = [
    "RiskGovernor",
    "apply_daily_reset",
    "Envelope",
    "compute_envelope",
    "AccountState",
    "ContextBias",
    "Decision",
    "DayState",
    "ExitPlan",
    "KillSwitchState",
    "ManageAction",
    "RiskDecision",
    "Signal",
    "SymbolMeta",
]
