"""Backtest harness (spec 05) — the deterministic arbiter of any change."""

from .costs import CostModel
from .engine import EventDrivenBacktester, VectorbtSweeper
from .ftmo_sim import FtmoTracker
from .gates import GatesConfig, all_passed, deflated_sharpe, evaluate_gates
from .metrics import summarize
from .types import BacktestReport, BacktestRequest, BTBar, GateResult, SimTrade, WFSpec
from .walkforward import make_splits, walk_forward
from .validate import Verdict, lockbox_passes, walkforward_verdict

__all__ = [
    "CostModel", "EventDrivenBacktester", "VectorbtSweeper", "FtmoTracker",
    "GatesConfig", "all_passed", "deflated_sharpe", "evaluate_gates", "summarize",
    "BacktestReport", "BacktestRequest", "BTBar", "GateResult", "SimTrade", "WFSpec",
    "make_splits", "walk_forward",
    "Verdict", "lockbox_passes", "walkforward_verdict",
]
