"""Execution / MT5 adapter (spec 03)."""

from .adapter import AccountMismatch, MT5Execution
from .broker import Broker, BrokerOrder, OrderSendResult, RealMT5Broker
from .logic import classify_reconciliation, classify_retcode, slippage_pips
from .types import ExecResult, Health, IntentStatus, OrderIntent, ReconcileReport

__all__ = [
    "MT5Execution", "AccountMismatch",
    "Broker", "BrokerOrder", "OrderSendResult", "RealMT5Broker",
    "classify_reconciliation", "classify_retcode", "slippage_pips",
    "ExecResult", "Health", "IntentStatus", "OrderIntent", "ReconcileReport",
]
