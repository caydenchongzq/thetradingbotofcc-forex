"""Builders for Risk Governor tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.common.config import RiskConfig
from src.risk.types import (
    AccountState,
    ContextBias,
    DayState,
    ExitPlan,
    KillSwitchState,
    Signal,
    SymbolMeta,
)

NOW = datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc)


@pytest.fixture
def cfg() -> RiskConfig:
    return RiskConfig()  # spec-default values


@pytest.fixture
def eurusd() -> SymbolMeta:
    return SymbolMeta(
        symbol="EURUSD", pip_value_per_lot_usd=10.0, min_lot=0.01, max_lot=100.0,
        lot_step=0.01, stops_level_pips=0.0, digits=5, pip_size=0.0001,
    )


def account(equity=100_000.0, balance=100_000.0, currency="USD", fresh=True) -> AccountState:
    return AccountState(equity=equity, balance=balance, currency=currency,
                        ts_utc=NOW, is_fresh=fresh)


def day(balance_0000=100_000.0, initial=100_000.0, **over) -> DayState:
    kwargs = dict(balance_0000=balance_0000, initial=initial)
    kwargs.update(over)
    return DayState(**kwargs)


def signal(sl_pips=11.0, **over) -> Signal:
    base = dict(
        instrument="EURUSD", direction="long", exit_plan=ExitPlan(sl_pips),
        signal_price=1.08742, context_bias=ContextBias.NORMAL,
        reference_price=1.08742,
    )
    base.update(over)
    return Signal(**base)
