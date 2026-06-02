"""Gated proposal pipeline (spec 06 §4/§6) — deterministic orchestration.

A proposal flows: validate (allowed-lever) -> branch from HEAD -> backtest the candidate
config (with the true cumulative trial count for the DSR) -> apply the gates VERBATIM ->
record in the trial ledger (pass AND fail) -> on pass, a human-approved version bump.
The backtester is the arbiter; the LLM cannot change a verdict. No live state is written
until a human approves and the store commits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .config_store import ConfigStore, apply_diff
from .ledger import TrialLedger
from .proposal import Proposal, validate_proposal


@dataclass
class ProposalOutcome:
    status: str                 # rejected_validation|budget_exhausted|failed|passed
    trial_count: int
    candidate_config: dict | None
    report: Any = None
    reason: str = ""


# backtest_fn(candidate_config: dict, trial_count: int) -> object with `.passed: bool`
BacktestFn = Callable[[dict, int], Any]


def process_proposal(
    proposal: dict, store: ConfigStore, ledger: TrialLedger, backtest_fn: BacktestFn,
    *, period: str, author: str = "strategy_researcher", weekly_cap: int = 4,
) -> ProposalOutcome:
    prop = Proposal.from_dict(proposal)
    head = store.head_version()

    vres = validate_proposal(prop, head)
    if not vres.ok:
        return ProposalOutcome("rejected_validation", ledger.cumulative_count(), None,
                               reason="; ".join(vres.errors))

    if ledger.budget_remaining(period, weekly_cap) <= 0:
        return ProposalOutcome("budget_exhausted", ledger.cumulative_count(), None,
                               reason=f"weekly trial budget {weekly_cap} exhausted")

    # Record the hypothesis BEFORE backtesting so the trial count can't be gamed by
    # abandoning losers — and so the DSR sees an honest cumulative count.
    ledger.record(prop.proposal_id, period, author, "proposed")
    trial_count = ledger.cumulative_count()

    candidate = apply_diff(store.get_config(head), prop.diff)
    report = backtest_fn(candidate, trial_count)
    passed = bool(getattr(report, "passed", False))
    ledger.record(prop.proposal_id, period, author, "passed" if passed else "failed")

    return ProposalOutcome("passed" if passed else "failed", trial_count,
                           candidate if passed else None, report=report)


def approve_and_promote(proposal: dict, store: ConfigStore, candidate_config: dict,
                        approver: str = "human") -> int:
    """Human (Phase A/B) approval -> compare-and-swap version bump. Acquires the
    promotion lease; ``promote`` releases it. Raises on stale parent / held lease."""
    prop = Proposal.from_dict(proposal)
    store.acquire_lease(prop.proposal_id)
    try:
        return store.promote(prop.parent_config_version, prop.diff, prop.author,
                             approver, config=candidate_config)
    except Exception:
        store.release_lease()
        raise
