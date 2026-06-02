"""Risk Governor data types (spec 02 §3).

Pure data — no I/O. Shared with the journal (which persists ``DayState``) and the
execution layer (which consumes ``RiskDecision``). Kept dependency-free so the
journal can import it without creating a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class KillSwitchState(str, Enum):
    """Daily kill-switch state machine (spec 02 §5).

    ARMED -> REDUCE -> HALTED -> FLATTEN. HALTED/FLATTEN are latched for the day;
    only the 00:00 CE(S)T reset clears HALTED, and only a human clears FLATTEN.
    """

    ARMED = "armed"
    REDUCE = "reduce"
    HALTED = "halted"
    FLATTEN = "flatten"


@dataclass(frozen=True)
class AccountState:
    """Read LIVE from MT5 before every sizing decision; never cached across decisions."""

    equity: float
    balance: float
    currency: str
    ts_utc: datetime
    is_fresh: bool  # False if the read is stale/failed -> Governor must veto (fail-safe)


@dataclass(frozen=True)
class DayState:
    """Persisted in the journal/state DB; reset at 00:00 CE(S)T."""

    balance_0000: float
    initial: float
    requests_used_today: int = 0
    killswitch: "KillSwitchState" = KillSwitchState.ARMED
    open_risk_usd: float = 0.0
    trades_opened_today: int = 0
    reset_ts_utc: datetime | None = None
    # Trailing median of recent trade risk_usd, for the size-consistency check.
    recent_risk_usds: tuple[float, ...] = field(default_factory=tuple)


class Decision(str, Enum):
    APPROVE = "approve"
    APPROVE_DOWNSIZED = "approve_downsized"
    VETO = "veto"


@dataclass(frozen=True)
class RiskDecision:
    decision: Decision
    lots: float
    risk_usd: float
    reason: str
    daily_pct_used_after: float
    requests_remaining: int
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.decision in (Decision.APPROVE, Decision.APPROVE_DOWNSIZED)


class ContextBias(str, Enum):
    """Optional context-bias seam (README §2). Default NORMAL; the deferred fundamental
    overlay may later set CAUTIOUS/STAND_DOWN. The engine only tags; the Governor decides."""

    NORMAL = "normal"
    CAUTIOUS = "cautious"
    STAND_DOWN = "stand_down"


@dataclass(frozen=True)
class ExitPlan:
    initial_sl_pips: float


@dataclass(frozen=True)
class Signal:
    """The entry proposal the Governor sizes/vetoes.

    This is the minimal contract the Risk Governor (spec 02) needs. The strategy engine
    (spec 01) produces it and tags the deterministic context flags below; the Governor
    re-verifies them as defence-in-depth and owns the budget math.
    """

    instrument: str
    direction: str  # "long" | "short"
    exit_plan: ExitPlan
    signal_price: float
    context_bias: ContextBias = ContextBias.NORMAL
    reference_price: float | None = None       # latest quote, for the stale-tick check
    news_blackout_active: bool = False          # engine-tagged; Governor re-checks
    near_session_gap: bool = False              # <=2h before a 2h+ close/weekend
    opposing_position_open: bool = False        # hedging-the-same/correlated instrument
    adds_to_losing_same_dir: bool = False       # martingale / averaging into a loser
    pending_orders_count: int = 0               # for the grid check


@dataclass(frozen=True)
class ManageAction:
    """A modify/partial/close proposed by ``strategy.manage()`` (spec 01)."""

    kind: str  # "close" | "partial_close" | "move_sl" | "modify_tp" | "add"
    risk_increasing: bool  # True only for actions that could raise loss exposure


@dataclass(frozen=True)
class SymbolMeta:
    """Broker contract metadata for one instrument (from MT5 symbol_info)."""

    symbol: str
    pip_value_per_lot_usd: float  # value of 1 pip per 1.0 lot, in account currency
    contract_size: float = 100_000.0
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    stops_level_pips: float = 0.0  # broker minimum SL/TP distance, in pips
    digits: int = 5
    pip_size: float = 0.0001       # price move equal to one pip

    def pip_value_per_lot(self, account_currency: str) -> float:
        # USD-quoted majors: pip value is currency-agnostic for a USD account.
        # Non-USD accounts would convert here; left explicit for the EURUSD/USD case.
        return self.pip_value_per_lot_usd
