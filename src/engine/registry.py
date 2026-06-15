"""Strategy registry (spec 01) — the SINGLE place a strategy is constructed by name.

Live and backtest BOTH build strategies through ``build_strategy``, so a config selects
which strategy runs and ``live == backtest`` is preserved (same class, same config).

Isolation guarantee: the live runner builds from the ConfigStore HEAD config, so it only
ever runs the *promoted* strategy. A strategy under development is registered here and can
be backtested by name (``run_backtest.py --strategy NAME`` or ``--config-file dev.yaml``)
WITHOUT being promoted — testing it can never disturb live production.

Adding a strategy: implement the ``Strategy`` protocol in ``src/engine`` then add one
``register(...)`` line below (see CLAUDE.md → "add a new indicator / concept / strategy").
"""

from __future__ import annotations

from typing import Callable

from .strategy import SessionBreakoutER, Strategy

# name -> factory(config_dict) -> Strategy
_REGISTRY: dict[str, Callable[[dict], Strategy]] = {}

DEFAULT_STRATEGY = "SessionBreakoutER"


def register(name: str, factory: Callable[[dict], Strategy]) -> None:
    """Register a strategy factory under ``name`` (idempotent re-registration is refused)."""
    if name in _REGISTRY and _REGISTRY[name] is not factory:
        raise ValueError(f"strategy {name!r} already registered to a different factory")
    _REGISTRY[name] = factory


def available() -> list[str]:
    """Sorted list of registered strategy names."""
    return sorted(_REGISTRY)


def build_strategy(config: dict) -> Strategy:
    """Construct the strategy named by ``config['name']`` (defaults to SessionBreakoutER).

    This is the ONLY supported way live and backtest instantiate a strategy."""
    name = (config or {}).get("name", DEFAULT_STRATEGY)
    if name not in _REGISTRY:
        raise KeyError(f"unknown strategy {name!r}; registered: {available()}")
    return _REGISTRY[name](config)


# ---- built-in strategies ----
register(DEFAULT_STRATEGY, SessionBreakoutER)

# ---- research-engine candidates (dev-registered, NOT promoted — spec 08 §5.1) ----
from .strategy_asian_sweep import AsianSweepFade  # noqa: E402
from .strategy_asian_sweep_rr import AsianSweepFadeRR  # noqa: E402
from .strategy_breakout_retest import BreakoutRetestER  # noqa: E402
from .strategy_compression import SessionBreakoutERCompression  # noqa: E402
from .strategy_resting import SessionBreakoutERResting  # noqa: E402
from .strategy_late_drift import LateSessionDrift  # noqa: E402
from .strategy_second_entry import SecondEntryORB  # noqa: E402
from .strategy_trend_aligned import TrendAlignedORB  # noqa: E402
from .strategy_trend_pullback import TrendPullbackEMA  # noqa: E402

register("SessionBreakoutERCompression", SessionBreakoutERCompression)
register("SessionBreakoutERResting", SessionBreakoutERResting)
register("AsianSweepFade", AsianSweepFade)
register("AsianSweepFadeRR", AsianSweepFadeRR)
register("BreakoutRetestER", BreakoutRetestER)
register("LateSessionDrift", LateSessionDrift)
register("SecondEntryORB", SecondEntryORB)
register("TrendAlignedORB", TrendAlignedORB)
register("TrendPullbackEMA", TrendPullbackEMA)
