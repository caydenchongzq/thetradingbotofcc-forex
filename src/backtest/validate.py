"""Promotion-grade verdict (spec 05 §6/§7) — one definition, shared by the runner and the
improvement loop so they can never disagree on what 'passes'.

The composite verdict = in-sample gates PASS, no stitched-OOS collapse, no severe losing
fold, >=60% folds profitable, and the held-out lockbox clears the core gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def lockbox_passes(lb: dict | None) -> bool:
    """A held-out lockbox clears the core gates (or there is none configured)."""
    if not lb:
        return True
    return (lb.get("expectancy_r", 0.0) >= 0.10 and lb.get("profit_factor", 0.0) >= 1.3
            and lb.get("trade_count", 0) >= 30)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    in_sample_passed: bool
    stitched_collapse: bool
    severe_collapse: bool
    majority_ok: bool
    lockbox_ok: bool
    folds_profitable: int
    folds_scored: int


def walkforward_verdict(in_sample_passed: bool, wfr) -> Verdict:
    maj_need = max(1, math.ceil(0.6 * wfr.folds_scored)) if wfr.folds_scored else 1
    majority_ok = wfr.folds_profitable >= maj_need
    lockbox_ok = lockbox_passes(wfr.lockbox_metrics)
    passed = (in_sample_passed and not wfr.stitched_collapse and not wfr.severe_collapse
              and majority_ok and lockbox_ok)
    return Verdict(passed=passed, in_sample_passed=in_sample_passed,
                   stitched_collapse=wfr.stitched_collapse, severe_collapse=wfr.severe_collapse,
                   majority_ok=majority_ok, lockbox_ok=lockbox_ok,
                   folds_profitable=wfr.folds_profitable, folds_scored=wfr.folds_scored)
