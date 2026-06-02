"""Shared fixtures and record builders for the test suite."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def state_dir(tmp_path):
    """A throwaway state directory for a Journal under test."""
    return tmp_path / "state"


def trade_entry(trade_id: str = "EURUSD-2026-06-02-0317", **over: Any) -> dict[str, Any]:
    rec = {
        "record_type": "trade",
        "trade_id": trade_id,
        "config_version": 47,
        "schema_version": 3,
        "ts_utc": "2026-06-02T14:03:17Z",
        "instrument": "EURUSD",
        "signal": {"session": "london_ny_overlap", "breakout_level": 1.08742,
                   "direction": "long", "er": 0.41, "atr_pips": 9.3,
                   "regime_gate_passed": True},
        "regime": {"er": 0.41, "atr_pips": 9.3, "atr_percentile": 0.62, "vol_state": "normal"},
        "sizing": {"risk_fraction": 0.0035, "equity_at_entry": 101230.50,
                   "risk_usd": 354.31, "sl_distance_pips": 11.0, "lots": 0.32},
        "rule_budget": {"daily_pct_used": 0.122, "requests_used_today": 184,
                        "killswitch_tripped": False},
    }
    rec.update(over)
    return rec


def trade_exit(trade_id: str = "EURUSD-2026-06-02-0317", **over: Any) -> dict[str, Any]:
    rec = {
        "record_type": "trade",
        "trade_id": trade_id,
        "config_version": 47,
        "schema_version": 3,
        "ts_utc": "2026-06-02T15:16:00Z",
        "outcome": {"r_multiple": 1.42, "pnl_usd": 502.10, "net_pips": 15.0,
                    "mae_pips": 4.1, "mfe_pips": 18.3, "duration_min": 73},
        "fills": {"exit_fill_price": 1.08901, "exit_reason": "trail_step"},
    }
    rec.update(over)
    return rec


def reject(record_id: str | None = None, **over: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "record_type": "reject",
        "config_version": 47,
        "schema_version": 3,
        "ts_utc": "2026-06-02T13:00:00Z",
        "instrument": "EURUSD",
        "stage": "engine",
        "reason": "regime_gate_failed",
        "context": {"er": 0.22, "er_threshold": 0.30, "atr_pips": 3.1, "vol_state": "low"},
        "risk_checks": None,
    }
    if record_id is not None:
        rec["record_id"] = record_id
    rec.update(over)
    return rec


def health(record_id: str | None = None, **over: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "record_type": "health",
        "schema_version": 3,
        "ts_utc": "2026-06-02T13:00:05Z",
        "engine_up": True,
        "mt5_connected": True,
        "data_fresh": True,
        "requests_used_today": 184,
        "killswitch_state": "armed",
        "open_positions": 1,
        "note": "",
    }
    if record_id is not None:
        rec["record_id"] = record_id
    rec.update(over)
    return rec


def intent(client_id: str = "cid-001", **over: Any) -> dict[str, Any]:
    rec = {
        "record_type": "intent",
        "record_id": f"intent-EURUSD-2026-06-02T14:03:00Z-{client_id}",
        "schema_version": 3,
        "ts_utc": "2026-06-02T14:03:00Z",
        "client_id": client_id,
        "magic": 770042,
        "status": "pending",
    }
    rec.update(over)
    return rec
