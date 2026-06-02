"""Backtest harness types (spec 05 §9). The backtester — not the LLM — is the arbiter
of any change (cross-phase invariant #2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class WFSpec:
    train_months: int
    test_months: int
    step_months: int
    lockbox_months: int = 0


@dataclass(frozen=True)
class GateResult:
    name: str
    value: float
    threshold: float
    passed: bool
    note: str = ""


@dataclass(frozen=True)
class BTBar:
    """One closed OHLC bar plus the spread observed at decision time (in pips)."""
    ts_open_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread_pips: float = 0.4


@dataclass(frozen=True)
class SimTrade:
    entry_ts: datetime
    exit_ts: datetime
    direction: str               # "long" | "short"
    entry_price: float
    exit_price: float
    lots: float
    sl_price: float
    r_multiple: float
    pnl_usd: float
    gross_pips: float
    net_pips: float
    mae_pips: float
    mfe_pips: float
    exit_reason: str             # "sl" | "tp" | "manage_close" | "eod"
    commission_usd: float
    entry_slippage_pips: float
    spread_at_entry_pips: float
    regime_vol_state: str = "normal"


@dataclass(frozen=True)
class BacktestRequest:
    strategy_name: str
    config_version: int
    config: dict
    data_set: str                # "dukascopy_dev" | "mt5_final"
    period: tuple[datetime, datetime]
    walk_forward: WFSpec
    trial_count: int             # from the trial ledger — drives DSR
    monte_carlo_runs: int = 0


@dataclass(frozen=True)
class BacktestReport:
    request: BacktestRequest
    passed: bool                 # AND of every gate
    gates: dict                  # name -> GateResult
    metrics: dict
    ftmo: dict                   # breaches (must be 0), worst excursions, requests/day max
    oos: dict
    overfitting: dict            # DSR, PBO, trial_count used
    artifacts: dict = field(default_factory=dict)
