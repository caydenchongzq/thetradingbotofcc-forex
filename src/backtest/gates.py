"""Promotion gates + deflated-Sharpe (spec 05 §6, §8) — pure, code-owned (not prompt).

A config passes only if ALL gates hold. The FTMO-breach gate is hard and binary: no
metric, profitability, or LLM advocacy can override it. The deflated-Sharpe bar rises
with the true cumulative trial count, converting proposal volume into statistical
conservatism (the LLM cannot reset the count)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

from .types import GateResult

_N01 = NormalDist()
_EULER = 0.5772156649015329


@dataclass(frozen=True)
class GatesConfig:
    min_expectancy_r: float = 0.10
    min_profit_factor: float = 1.3
    min_sharpe: float = 1.0
    min_sortino: float = 1.5
    min_trades: int = 200
    min_dsr: float = 0.95
    walkforward_oos_floor_frac: float = 0.5   # OOS expectancy >= this * in-sample


def deflated_sharpe(sr: float, n: int, skew: float, kurt: float, trials: int) -> float:
    """Probability the true Sharpe > 0 given n obs and `trials` cumulative trials.
    Monotonically DECREASING in `trials` (more trials -> higher bar). Bailey & LdP."""
    if n < 3 or trials < 1:
        return 0.0
    var_term = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    var_term = max(var_term, 1e-9)
    sigma_sr = math.sqrt(var_term / (n - 1))
    if trials == 1:
        sr0 = 0.0
    else:
        z1 = _N01.inv_cdf(1.0 - 1.0 / trials)
        z2 = _N01.inv_cdf(1.0 - 1.0 / (trials * math.e))
        sr0 = sigma_sr * ((1.0 - _EULER) * z1 + _EULER * z2)
    return _N01.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(var_term))


def evaluate_gates(
    metrics: dict, ftmo_breaches: int, trial_count: int,
    oos_expectancy: float | None = None, in_sample_expectancy: float | None = None,
    cfg: GatesConfig | None = None,
) -> dict[str, GateResult]:
    cfg = cfg or GatesConfig()
    # DSR on the daily (non-annualised) Sharpe + daily-return count (falls back to the
    # per-period values when not provided, e.g. in unit tests).
    dsr = deflated_sharpe(metrics.get("_sr_for_dsr", metrics.get("sharpe", 0.0)),
                          metrics.get("_n_for_dsr", metrics.get("trade_count", 0)),
                          metrics.get("_skew", 0.0), metrics.get("_kurt", 3.0), trial_count)
    gates: dict[str, GateResult] = {}

    def g(name, value, threshold, passed, note=""):
        gates[name] = GateResult(name, float(value), float(threshold), bool(passed), note)

    g("expectancy_r", metrics.get("expectancy_r", 0.0), cfg.min_expectancy_r,
      metrics.get("expectancy_r", 0.0) >= cfg.min_expectancy_r)
    g("profit_factor", metrics.get("profit_factor", 0.0), cfg.min_profit_factor,
      metrics.get("profit_factor", 0.0) >= cfg.min_profit_factor)
    g("sharpe", metrics.get("sharpe", 0.0), cfg.min_sharpe,
      metrics.get("sharpe", 0.0) >= cfg.min_sharpe)
    g("sortino", metrics.get("sortino", 0.0), cfg.min_sortino,
      metrics.get("sortino", 0.0) >= cfg.min_sortino)
    g("sample_size", metrics.get("trade_count", 0), cfg.min_trades,
      metrics.get("trade_count", 0) >= cfg.min_trades)
    g("deflated_sharpe", dsr, cfg.min_dsr, dsr >= cfg.min_dsr,
      note=f"trial_count={trial_count}")
    # Hard, binary, non-overridable.
    g("ftmo_no_breach", ftmo_breaches, 0, ftmo_breaches == 0,
      note="HARD GATE: zero simulated breaches")
    if oos_expectancy is not None and in_sample_expectancy is not None:
        floor = cfg.walkforward_oos_floor_frac * in_sample_expectancy
        g("walk_forward", oos_expectancy, floor, oos_expectancy >= floor,
          note="OOS expectancy vs in-sample floor")
    return gates


def all_passed(gates: dict[str, GateResult]) -> bool:
    return all(gr.passed for gr in gates.values())
