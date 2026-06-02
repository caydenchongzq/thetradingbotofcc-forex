"""Execution / MT5 adapter types (spec 03 §3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class IntentStatus(str, Enum):
    INTENDED = "intended"    # written BEFORE the broker call (persist-before-act)
    SENT = "sent"            # order_send returned, awaiting confirm
    FILLED = "filled"        # confirmed position/deal exists
    REJECTED = "rejected"    # retcode != DONE
    CANCELLED = "cancelled"  # pending expired/cancelled
    UNKNOWN = "unknown"      # crash between INTENDED and confirm -> reconcile decides


@dataclass(frozen=True)
class OrderIntent:
    client_id: str           # unique, deterministic — the idempotency key
    magic: int               # the bot's magic number; identifies OUR positions
    instrument: str
    side: str                # buy | sell
    order_kind: str          # market | stop | limit
    volume_lots: float
    price: float | None      # for stop/limit
    sl_price: float
    tp_prices: tuple[float, ...]
    expire_utc: datetime | None
    comment: str             # carries client_id for cross-identification in the terminal


@dataclass(frozen=True)
class ExecResult:
    client_id: str
    status: IntentStatus
    retcode: int | None
    broker_order_id: int | None
    broker_position_id: int | None
    fill_price: float | None
    fill_volume: float | None
    slippage_pips: float | None
    spread_at_send_pips: float | None
    commission_usd: float | None
    ts_utc: datetime
    error: str | None


@dataclass(frozen=True)
class ReconcileReport:
    matched: int
    adopted: int             # pre-existing positions on our magic, adopted into state
    orphaned_intents: int    # INTENDED/SENT/UNKNOWN with no matching broker object
    flatten_required: bool   # ambiguity that cannot be reconciled -> hold/flatten
    detail: dict


@dataclass(frozen=True)
class Health:
    """Liveness/freshness snapshot the watchdog (spec 07) polls. A stale/false health is
    the trigger for the R3 fail-safe (hold/flatten, never a new trade)."""

    terminal_connected: bool
    trade_allowed: bool
    account_reachable: bool
    data_fresh: bool
    last_tick_age_s: float | None
    note: str = ""

    @property
    def ok(self) -> bool:
        return (self.terminal_connected and self.account_reachable and self.data_fresh)
