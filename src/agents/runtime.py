"""Pluggable agent runtime seam (spec 06 §2).

The agent contract is runtime-agnostic: read the journal -> emit a versioned proposal
diff -> the deterministic backtester is the arbiter -> human-approved promotion. Phase A
runs agents as Cowork scheduled tasks on the Max plan; Phase C swaps to the Claude Agent
SDK + Batch API behind this same seam — a harness swap, not a redesign.

INVARIANT (R5 boundary): the runtime may ONLY read the journal/config and write artifacts
to the proposal/ledger store. It can NEVER write live config or reach the broker.

STATUS: seam + types complete; concrete runtimes deferred (milestone A6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AgentSpec:
    name: str            # "performance_reviewer" | "strategy_researcher" | "backtest_analyst"
    prompt: str
    model_tier: str      # "haiku" | "sonnet" | "opus"
    allowed_tools: tuple[str, ...]  # read + emit only (e.g. ("Read", "Grep"))
    output_schema: str   # "run_summary" | "proposal_diff" | "backtest_narration"


@dataclass(frozen=True)
class AgentInputs:
    journal_reader_state_dir: str  # path the JournalReader (read-only) opens
    current_config_path: str
    backtest_report_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentArtifact:
    kind: str            # matches AgentSpec.output_schema
    path: str            # where the typed artifact was written
    summary: str


class AgentRuntime(Protocol):
    def run_agent(self, agent: AgentSpec, inputs: AgentInputs) -> AgentArtifact:
        """Execute one agent: read-only inputs in, a typed artifact out. Pure w.r.t.
        live state."""
        ...


class CoworkScheduledRuntime:
    """Phase A: each agent is a Cowork scheduled task on the Max plan (spec 06 §2.1)."""

    def run_agent(self, agent: AgentSpec, inputs: AgentInputs) -> AgentArtifact:
        raise NotImplementedError("CoworkScheduledRuntime — milestone A6 (spec 06 §2.1)")


class ClaudeAgentSDKRuntime:
    """Phase C: Claude Agent SDK + Batch API on a separate Linux box (spec 06 §2.2)."""

    def run_agent(self, agent: AgentSpec, inputs: AgentInputs) -> AgentArtifact:
        raise NotImplementedError("ClaudeAgentSDKRuntime — Phase C (spec 06 §2.2)")
