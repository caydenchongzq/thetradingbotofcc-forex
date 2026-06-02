# 06 — Improvement Loop (R5)

> The AI desk around the deterministic trader. Three scheduled agents read the journal and backtest reports, detect drift, propose **versioned config diffs**, and gate them through the backtester (05) before a **human-approved** promotion. The LLM's entire authorized surface is **READ logs/backtests** and **PROPOSE a diff** — it never touches a live trade, never decides if a change is good, never mutates live config (R5 boundary).
>
> **Runtime is pluggable and phased** (the 2026-06-02 decision): Phase A runs the agents as **Claude Desktop / Cowork scheduled tasks on the Max subscription** (≈ $0 marginal); Phase C swaps to the **Claude Agent SDK + Batch API** behind the same seam. The *logic* below is identical in both phases.

---

## 1. The three agents (R5 §1.2)

| Agent | Cadence | Model tier | Reads | Emits | Forbidden |
|---|---|---|---|---|---|
| **Performance Reviewer** (bookkeeper / drift sentinel) | after each session + daily roll-up | cheap (Haiku) | journal (read-only) | run-summary + drift flags | inventing strategy; computing the verdict |
| **Strategy Researcher** (proposer) | weekly + on drift-trigger | strong (Sonnet/Opus) | Reviewer summary, recent backtests, current config, allowed-lever library | ≤ N **proposal diffs** w/ rationale | running backtests; applying changes |
| **Backtest Analyst** (gatekeeper) | event-driven (when a hypothesis exists) | mostly **deterministic** + cheap narration | a proposal + history | pass/fail report → promotion proposal | overriding a gate |

The drift **statistics** (CUSUM on per-trade R, expectancy-degradation, regime-mix) are **deterministic code**; the Reviewer LLM only reads the computed numbers, writes prose, and routes (raise a flag or not). The gate logic in the Analyst is **code the LLM cannot edit**; a cheap LLM call only narrates pass/fail. The Researcher is the only place real reasoning (and real model cost) lives, and it runs a handful of times a month.

---

## 2. The runtime seam (Cowork/Max → API)

The one abstraction that makes phasing a swap, not a rewrite:

```python
# src/agents/runtime.py
from typing import Protocol

class AgentRuntime(Protocol):
    def run_agent(self, agent: "AgentSpec", inputs: "AgentInputs") -> "AgentArtifact":
        """Execute one agent: feed it read-only inputs, get back a typed artifact
        (run-summary | proposal-diff | backtest-narration). Pure w.r.t. live state:
        the runtime may ONLY read the journal/config and write artifacts to the
        proposal/ledger store — never the live config or the broker."""
```

`AgentSpec` holds the agent's prompt, model tier, allowed tools (read + emit only), and output schema. `AgentInputs` are file/DB references (journal reader handle, current config, backtest reports). `AgentArtifact` is one of the typed outputs (§3/§4). Two implementations:

### 2.1 Phase A — `CoworkScheduledRuntime`
- Each agent is a **Cowork scheduled task** (see `skills/schedule`) whose prompt is the `AgentSpec` prompt plus pointers to the journal/config/proposal paths in the workspace folder.
- The task runs on the **Max subscription**, on the local Windows PC, **outside** the London/NY-overlap session (so a backtest can't starve the live engine — R7 host-phasing).
- The scheduled task's instructions require it to **write the same artifacts the API path writes**: the proposal JSON (§3), a trial-ledger entry (§5), and a run-summary row in the journal. This is the discipline that keeps Phase C a drop-in swap and the audit trail continuous.
- Promotion stays **human-in-the-loop**: the task surfaces a passed proposal for Cayden to approve; approval triggers the version bump (§6).

**Cadence wiring (Phase A):**
- Reviewer: a scheduled task at session close + a daily task at (a safe margin after) the 00:00 CE(S)T reset.
- Researcher: a weekly scheduled task; plus a "drift-triggered" task that the Reviewer's flag enables (in Phase A, simplest is a daily check that runs the Researcher only if an unprocessed drift flag exists).
- Analyst: runs whenever an unprocessed proposal exists (daily check task), invoking the deterministic backtester then narrating.

### 2.2 Phase C — `ClaudeAgentSDKRuntime`
- The 200-line Python orchestrator (cron on a **separate Linux box**) invokes the **Claude Agent SDK** with `plan`/`dontAsk` permission modes that **structurally** restrict the agent to `Read`/`Grep` + emitting a file — a misbehaving or prompt-injected model still cannot reach a trade (R5 §2.2).
- LLM calls go through the **Batch API** with model tiering; prompt caching on the bounded journal context. Monthly token budget + alert as a belt-and-braces cap (R5 §6). Expected **$5–30/mo**.

**The migration is config:** point the orchestrator at `ClaudeAgentSDKRuntime` instead of `CoworkScheduledRuntime`. The agents, prompts, schemas, gates, ledger, and promotion flow are unchanged. Trigger to migrate (R5 §2.4): Researcher cadence outgrows hand-scheduled runs; need to run with the desktop closed / headless; or fair-use friction.

---

## 3. Proposal representation (the PR-like artifact, R5 §2.3)

Every proposal is a versioned config diff — auditable, reversible:

```json
{
  "proposal_id": "2026-06-02-w23-001",
  "parent_config_version": 47,
  "author": "strategy_researcher",
  "runtime": "cowork|agent_sdk",
  "created_utc": "2026-06-02T18:05:00Z",
  "hypothesis": "London-open ER gate too loose in low-vol regimes; tightening should cut chop losses.",
  "diff": [
    {"param": "regime.er_threshold", "from": 0.30, "to": 0.38},
    {"param": "session.london_open_buffer_min", "from": 5, "to": 10}
  ],
  "expected_effect": "fewer false breakouts in ER<0.38 regimes; slight trade-count drop",
  "trial_budget_id": "2026-W23",
  "status": "proposed",                  // proposed → backtested → passed/failed → promoted/rejected
  "backtest_report_ref": null,
  "approval": {"rule_gate": null, "human": null}
}
```

`diff` may only touch params in the **allowed-lever library** (the R1 parameter surface: session windows, ER/ATR thresholds, stop/TP R-multiples, trailing step). A diff referencing any other key is rejected by deterministic validation before it ever reaches a backtest — the LLM cannot widen its own authority.

---

## 4. Pipeline (one cycle, R5 §3)

```
[session close]
  → Performance Reviewer: journal → run-summary + drift flags          (cheap LLM)
      └─(flag raised OR weekly tick)→ Strategy Researcher: → ranked config diffs   (strong LLM)
            └→ Backtest Analyst: EventDrivenBacktester.run() + vectorbt sweep
                  → apply gates verbatim (expectancy/PF/Sharpe/WFO/DSR/zero-breach)   (DETERMINISTIC)
                     ├─ fail → mark rejected, record in trial ledger, stop
                     └─ pass → emit Promotion Proposal                  (cheap LLM narrates)
                           └→ human (Phase A/B) / rule (narrow ranges) approval → config version bump
                                 └→ live box loads new config at next session start ONLY
```

State passes between runs **only** via the state DB + versioned config store (§6) — no agent depends on another being in memory, so every run is idempotent and re-runnable for audit.

---

## 5. Overfitting & drift governance (R5 §5 — deterministic, not LLM goodwill)

1. **Trial ledger.** Every hypothesis the Researcher emits — pass or fail — is recorded against a period budget. The backtester's deflated-Sharpe/PBO computation (05 §8) is fed the **true cumulative trial count**, so more proposals ⇒ a stricter bar. Code-maintained; the LLM cannot reset it.
2. **Hard trial budget.** Researcher capped at a small N per run/week — fewer, economically-motivated hypotheses beat a flood.
3. **OOS lockbox.** Walk-forward + a held-out window the LLM **never sees**; proposals must survive data they couldn't fit (05 §7).
4. **Zero-FTMO-breach gate is binary and non-negotiable** (05 §5) — no profitability or advocacy promotes a breaching config.

**Drift detection** (Reviewer: deterministic stats + LLM routing) — graduated response table:
- *Within tolerance* → log, no action.
- *CUSUM warning* (mild expectancy decay / costs creeping) → raise flag → Researcher proposes a retune; nothing changes live.
- *CUSUM alarm* (sustained degradation / realized slippage ≫ modeled) → **reduce/shadow**: the **Risk Governor's own deterministic rule** may cut `risk_fraction` (not the LLM), candidate retune runs in shadow.
- *Breach-risk / regime break* → **stand-down**: the deterministic Governor halts new entries (spec 02). The AI only explains and proposes; it never keeps trading. Stand-down is owned by R4/02, not by R5.

---

## 6. Config versioning & promotion (the only write path back)

- **Versioned config store**: a git repo (or a `strategy_config` table) with monotonic `version`, `author`, `parent`, `diff`, `approval`, `status`. Every promotion is a commit; rollback is `checkout previous_version` (R5 §1.3).
- **Promotion mutex / lease**: only one proposal holds the `in_promotion` lease; the Researcher branches every proposal from the **current committed** version, and the Analyst re-validates against that version before promotion. A proposal with a stale `parent_config_version` is re-queued for re-backtest, **never blind-merged** (optimistic concurrency / compare-and-swap on version) — so the LLM never has to reason about concurrency.
- **The live box loads config only at a session boundary** (or an explicit, logged hot-reload), so a half-finished or unapproved proposal can never leak into an open trade mid-session.
- **Approval**: human in Phase A/B (and always for the funded cut-over); a *rule* may auto-approve only changes within pre-registered narrow parameter ranges, and even then only after passing every gate.
- Every promotion is **reversible**: revert to `parent_config_version`, and the next session boundary adopts the rollback.

---

## 7. Configuration schema

```yaml
improvement_loop:
  runtime: cowork                 # cowork (Phase A) | agent_sdk (Phase C)
  models:
    reviewer: haiku
    researcher: sonnet            # or opus for harder reviews
    analyst_narration: haiku
  cadence:
    reviewer: ["session_close", "daily_post_reset"]
    researcher: ["weekly", "on_drift_flag"]
    analyst: ["on_unprocessed_proposal"]
  trial_budget_per_week: 4        # hard cap on Researcher proposals
  allowed_levers:                 # the ONLY params a diff may touch
    - regime.er_threshold
    - regime.atr_floor_pips
    - regime.atr_ceiling_pips
    - session.opening_range_minutes
    - exits.atr_mult_sl
    - exits.target_r_multiples
    - exits.move_be_after_r
  promotion:
    approver: human               # human | rule_within_ranges
    auto_approve_ranges: {}       # empty in Phase A; narrowly populated only once trusted
  cost_cap_usd_per_month: 30      # Phase C belt-and-braces; alert + halt agent runs if exceeded
  off_session_only: true          # Phase A: never run heavy agent jobs during the trading session
```

---

## 8. Test plan

**Unit:**
- Proposal validation: a diff touching a non-allowed-lever key is rejected; an in-range diff is accepted.
- Trial-ledger increments on every emitted hypothesis (pass and fail) and is read by the backtester (05 §8); cannot be decremented by an agent.
- Promotion mutex: a second concurrent proposal cannot take the lease; a stale-parent proposal is re-queued, not merged.
- Config version bump is monotonic; rollback restores the exact parent config.
- Drift policy table maps each CUSUM state to the correct action; stand-down/reduce are routed to the **Governor**, not executed by the agent layer.

**Runtime-seam (the phasing guarantee):**
- A **golden proposal fixture**: feed identical `AgentInputs` to a stubbed `CoworkScheduledRuntime` and a stubbed `ClaudeAgentSDKRuntime`; assert both write **byte-equivalent** proposal JSON + trial-ledger entries (proves the artifact contract is runtime-independent → Phase C is a true drop-in).
- The improvement loop holds only a **read-only** `JournalReader` + the config store; assert it has no handle that can write live state or place an order.

**Integration (milestone A6):**
- End-to-end on demo data: journal → Reviewer summary → (drift) Researcher diff → Analyst runs the real backtester → gates → human approval → version bump → live box adopts at next session start. Trial ledger and config history reflect every step.
- Kill the runtime mid-cycle; re-run; confirm idempotency (no duplicate proposals, ledger consistent).
