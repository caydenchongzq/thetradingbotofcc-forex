"""Strategy engine types (spec 01 §2).

These are the *emitted* types of the deterministic signal producer. The engine is a
pure function of (bars, now, context_bias, calendar): identical input => identical
Signal. Prices are floats here for the stub; spec 01 calls for Decimal/scaled ints at
the pip level in the real implementation to avoid float drift.

NOTE on the Signal seam: the engine's ``Signal`` (below) is what the strategy emits.
The Risk Governor (spec 02) consumes a *risk-evaluation request* — ``src.risk.types.Signal``
— which additionally carries engine-tagged deterministic context flags (news blackout,
opposing-position, pending count, latest quote) that the Governor re-verifies as
defence-in-depth. The live loop bridges the two via ``strategy.to_risk_signal()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class VolState(str, Enum):
    LOW = "low"        # ATR below band -> too quiet, breakout unreliable
    NORMAL = "normal"  # ATR inside band -> tradeable
    HIGH = "high"      # ATR above band -> too wild for fixed-R sizing safety


# Re-exported from the risk layer so the engine and governor agree on one enum.
from src.risk.types import ContextBias  # noqa: E402


@dataclass(frozen=True)
class Bar:
    ts_open_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True  # engine only ever acts on CLOSED bars


@dataclass(frozen=True)
class RegimeState:
    er: float
    er_threshold: float
    atr_pips: float
    atr_percentile: float
    vol_state: VolState
    regime_gate_passed: bool


@dataclass(frozen=True)
class TrailRule:
    activate_after_r: float
    step_pips: float
    distance_pips: float
    min_seconds_between_modifies: int


@dataclass(frozen=True)
class ExitPlan:
    initial_sl_price: float
    initial_sl_pips: float
    targets: tuple[float, ...]
    target_r_multiples: tuple[float, ...]
    partial_fractions: tuple[float, ...]
    move_be_after_r: Optional[float]
    trail: Optional[TrailRule]


@dataclass(frozen=True)
class Signal:
    instrument: str
    ts_decision_utc: datetime
    direction: Direction
    entry_type: str               # "stop" (breakout)
    entry_price: float
    exit_plan: ExitPlan
    regime: RegimeState
    session: str
    breakout_level: float
    entry_reason: str
    context_bias: ContextBias
    config_version: int


@dataclass(frozen=True)
class ArmSignal:
    """A two-sided *resting* breakout arm (resting-stop model, RESTING_STOP_FIX §3).

    Emitted ONCE per session at opening-range end (regime + news gate read AT OR-end).
    It carries a fully-formed per-side stop ``Signal`` for each side that can legally rest
    a pending stop (``long`` rests above the range, ``short`` below). A side is ``None``
    when price has already traded through that level at OR-end (a stop cannot rest on the
    wrong side of the market). Whichever side's level is touched intrabar fills; the sibling
    is cancelled (OCO). ``expire_utc`` is the session window-end in UTC — the resting orders
    are cancelled then. This restores live == backtest at the entry seam: live actually rests
    the stop in advance, exactly as the backtester models the intrabar touch.
    """
    instrument: str
    ts_decision_utc: datetime
    long: Optional[Signal]    # LONG stop Signal at long_level (entry_price == level), or None
    short: Optional[Signal]   # SHORT stop Signal at short_level, or None
    expire_utc: datetime
    regime: RegimeState
    config_version: int


@dataclass(frozen=True)
class NoSignal:
    ts_decision_utc: datetime
    reason: str  # "outside_session" | "regime_gate_failed" | "no_range_break" | ...
