"""Proposal diff + allowed-lever validation (spec 06 §3).

Every improvement-loop proposal is a versioned config diff. ``diff`` may only touch
params in the **allowed-lever library** (the R1 parameter surface). A diff referencing
any other key — especially anything under ``risk.*`` or the backtest gates — is rejected
by this deterministic validation before it ever reaches a backtest. This is the boundary
that stops the LLM widening its own authority or editing the gates it must pass.

This module is pure and fully unit-tested — it is a safety boundary, not a stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The only parameters an agent proposal may change (spec 01 §7 / spec 06 §3).
ALLOWED_LEVERS: frozenset[str] = frozenset({
    # session windows
    "session.window_start", "session.window_end", "session.opening_range_minutes",
    "session.london_open_buffer_min", "session.one_shot_per_side",
    # breakout
    "breakout.buffer_pips",
    # ER / ATR regime thresholds
    "regime.er_window", "regime.er_threshold",
    "regime.atr_window", "regime.atr_floor_pips", "regime.atr_ceiling_pips",
    "regime.atr_low_pct", "regime.atr_high_pct",
    # stop / TP R-multiples
    "exits.atr_mult_sl", "exits.target_r_multiples", "exits.partial_fractions",
    "exits.move_be_after_r",
    # trailing
    "exits.trail.activate_after_r", "exits.trail.step_pips",
    "exits.trail.distance_pips", "exits.trail.min_seconds_between_modifies",
})

# Namespaces an agent may NEVER touch, regardless of the allow-list (defence in depth).
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "risk.", "account.", "schema_version", "config_version", "gates.", "backtest.",
)

VALID_STATUSES = frozenset({
    "proposed", "backtested", "passed", "failed", "promoted", "rejected",
})


@dataclass(frozen=True)
class DiffEntry:
    param: str
    from_value: Any
    to_value: Any


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    parent_config_version: int
    author: str
    created_utc: str
    hypothesis: str
    diff: tuple[DiffEntry, ...]
    status: str = "proposed"

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Proposal":
        diff = tuple(
            DiffEntry(param=e["param"], from_value=e.get("from"), to_value=e.get("to"))
            for e in d.get("diff", [])
        )
        return Proposal(
            proposal_id=d["proposal_id"],
            parent_config_version=int(d["parent_config_version"]),
            author=d.get("author", "unknown"),
            created_utc=d.get("created_utc", ""),
            hypothesis=d.get("hypothesis", ""),
            diff=diff,
            status=d.get("status", "proposed"),
        )


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_proposal(proposal: Proposal, parent_config_version: int) -> ValidationResult:
    """Deterministic gate run BEFORE any backtest. Rejects a proposal that:
      - targets the wrong parent config version,
      - has an empty or malformed diff,
      - touches any forbidden namespace (risk/account/gates/...),
      - touches any param outside the allowed-lever library,
      - has an unknown status.
    """
    errors: list[str] = []

    if proposal.parent_config_version != parent_config_version:
        errors.append(
            f"parent_config_version {proposal.parent_config_version} != "
            f"current {parent_config_version} (stale proposal)"
        )

    if proposal.status not in VALID_STATUSES:
        errors.append(f"unknown status {proposal.status!r}")

    if not proposal.diff:
        errors.append("empty diff: a proposal must change at least one lever")

    for entry in proposal.diff:
        param = entry.param
        if any(param == p.rstrip(".") or param.startswith(p) for p in FORBIDDEN_PREFIXES):
            errors.append(f"forbidden param {param!r}: agents cannot touch this namespace")
            continue
        if param not in ALLOWED_LEVERS:
            errors.append(
                f"param {param!r} is not in the allowed-lever library "
                f"(the LLM cannot widen its own authority)"
            )

    return ValidationResult(ok=not errors, errors=errors)
