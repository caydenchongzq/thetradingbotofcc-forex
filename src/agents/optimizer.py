"""Generic, strategy-agnostic parameter optimizer (spec 06 §5).

Pure core: turn a declarative *search space* into candidate configs, apply them onto a base
config, and rank backtest results. Strategy-agnostic by construction — the space is just
dotted parameter paths (e.g. ``regime.er_threshold``, ``ma.period``) mapped to either a
numeric range ``{min,max,step}`` or an explicit ``{values: [...]}`` list. The harness that
runs the actual backtests lives in ``scripts/optimize.py``; everything here is deterministic
and unit-tested.

Anti-overfitting discipline (enforced by the caller): every candidate is judged at a DSR
trial_count equal to the sweep size, the lockbox is never used for ranking, and the winner
is emitted as a PROPOSAL for human approval — never auto-promoted.
"""

from __future__ import annotations

import copy
import itertools
import random
from typing import Any

from src.agents.proposal import DiffEntry

OBJECTIVES = ("oos_expectancy", "in_sample_expectancy", "sharpe", "profit_factor")


def _frange(lo: float, hi: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("step must be > 0")
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 10) for i in range(n + 1)]


def axis_values(spec: Any) -> list:
    """Expand one axis: a list, ``{values:[...]}``, or a numeric ``{min,max,step}`` range."""
    if isinstance(spec, (list, tuple)):
        return list(spec)
    if not isinstance(spec, dict):
        return [spec]
    if "values" in spec:
        return list(spec["values"])
    lo, hi, step = spec["min"], spec["max"], spec.get("step", 1)
    vals = _frange(float(lo), float(hi), float(step))
    if all(isinstance(x, int) for x in (lo, hi, step)):
        return [int(round(v)) for v in vals]
    return vals


def expand_grid(space: dict) -> list[dict]:
    """Every combination in the space (cartesian product) as a list of {param: value}."""
    if not space:
        return [{}]
    keys = list(space)
    axes = [axis_values(space[k]) for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*axes)]


def grid_size(space: dict) -> int:
    n = 1
    for k in space:
        n *= len(axis_values(space[k]))
    return n


def sample_random(space: dict, budget: int, seed: int = 0) -> list[dict]:
    """Up to ``budget`` distinct random combinations (full grid if it is smaller)."""
    if grid_size(space) <= budget:
        return expand_grid(space)
    rng = random.Random(seed)
    keys = list(space)
    axes = {k: axis_values(space[k]) for k in keys}
    seen: set[tuple] = set()
    out: list[dict] = []
    attempts = 0
    while len(out) < budget and attempts < budget * 100:
        attempts += 1
        combo = tuple(rng.choice(axes[k]) for k in keys)
        if combo in seen:
            continue
        seen.add(combo)
        out.append({k: combo[i] for i, k in enumerate(keys)})
    return out


def refine_space(space: dict, winner: dict, shrink: float = 0.5) -> dict:
    """A finer space centred on ``winner``: numeric axes get a half-step grid around the
    winning value; ``values`` axes are pinned to the winner (coarse-to-fine second pass)."""
    fine: dict = {}
    for k, spec in space.items():
        w = winner.get(k)
        if isinstance(spec, dict) and "min" in spec and "max" in spec:
            step = float(spec.get("step", 1)) * shrink
            if step <= 0:
                fine[k] = {"values": [w]}
                continue
            lo = max(float(spec["min"]), float(w) - float(spec.get("step", 1)))
            hi = min(float(spec["max"]), float(w) + float(spec.get("step", 1)))
            fine[k] = {"min": lo, "max": hi, "step": step}
        else:
            fine[k] = {"values": [w]}
    return fine


def enumerate_candidates(space: dict, method: str = "grid", budget: int = 40,
                         seed: int = 0) -> list[dict]:
    if method in ("grid", "coarse_to_fine"):   # coarse pass is a grid; refine done by caller
        return expand_grid(space)
    if method == "random":
        return sample_random(space, budget, seed)
    raise ValueError(f"unknown method {method!r} (grid | random | coarse_to_fine)")


def dotted_get(cfg: dict, path: str) -> Any:
    node: Any = cfg
    for p in path.split("."):
        node = node[p]
    return node


def apply_overrides(base: dict, candidate: dict) -> dict:
    """Deep-copy ``base`` and set each dotted ``candidate`` path."""
    cfg = copy.deepcopy(base)
    for path, val in candidate.items():
        parts = path.split(".")
        node = cfg
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val
    return cfg


def build_diff(base: dict, candidate: dict) -> list[DiffEntry]:
    out: list[DiffEntry] = []
    for path, val in candidate.items():
        try:
            frm = dotted_get(base, path)
        except (KeyError, TypeError):
            frm = None
        if frm == val:
            continue                       # no-op: param unchanged from base
        out.append(DiffEntry(param=path, from_value=frm, to_value=val))
    return out


def eligible(result: dict) -> bool:
    """A candidate is rankable only if it cleared the in-sample gates and showed no
    walk-forward collapse. (The lockbox is NEVER used for ranking.)"""
    return bool(result.get("gates_passed")
                and not result.get("severe_collapse")
                and not result.get("stitched_collapse"))


def rank(results: list[dict], objective: str = "oos_expectancy") -> list[dict]:
    """Eligible results sorted best-first by ``objective`` (must be in OBJECTIVES)."""
    if objective not in OBJECTIVES:
        raise ValueError(f"objective {objective!r} not in {OBJECTIVES}")
    return sorted((r for r in results if eligible(r)),
                  key=lambda r: r.get(objective, float("-inf")), reverse=True)
