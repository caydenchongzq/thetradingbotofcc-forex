# Implementation Specs

> Deep, implementation-ready specs for the FTMO EURUSD bot — one file per component. These turn the resolved research findings (`docs/research/`) and the project README into something buildable: interfaces, algorithms, config schemas, error/fail-safe behaviour, and test plans.
>
> **Status:** drafted 2026-06-02, reflecting the two rollout decisions (local-first host; Max-subscription AI runtime first). No code committed yet.

## Reading order

Start with the roadmap, then build bottom-up along the dependency graph.

| # | Spec | Component | Source track |
|---|---|---|---|
| 00 | [phase-roadmap](00-phase-roadmap.md) | **Read first** — phases A/B/C, build order, milestones & exit criteria | rollout decisions |
| 01 | [strategy-engine](01-strategy-engine.md) | Deterministic signal/regime engine (session breakout + ER/ATR gate) | R1 |
| 02 | [risk-governor](02-risk-governor.md) | Sizing, kill-switch, FTMO limits, 13 forbidden-practice checks | R4 |
| 03 | [execution-mt5](03-execution-mt5.md) | MT5 adapter: orders, magic, idempotent intent, reconciliation | R3 |
| 04 | [journal-state](04-journal-state.md) | JSONL/SQLite/Parquet journal — the live↔improvement contract | R5 §4 |
| 05 | [backtest-harness](05-backtest-harness.md) | Event-driven loop + vectorbt; FTMO sim; gates; anti-overfit | R6 |
| 06 | [improvement-loop](06-improvement-loop.md) | AI agents; **pluggable runtime (Cowork/Max → API)**; proposals; config versioning | R5 |
| 07 | [ops-deployment](07-ops-deployment.md) | Supervision, watchdog, alerting, secrets, backups; **local→VPS phasing** | R7 |
| 08 | [research-engine](08-research-engine.md) | Automated daily strategy R&D: online research → knowledge base → dev-isolated build → backtest → report | extends 06 |

## Build order (from 00)

```
04 journal/state → 02 risk governor → 03 execution → 05 backtest → 01 strategy → 06 improvement loop → 07 ops
```

Journal first (it's the contract); risk before reward; strategy built last in the spine and validated through the backtester before it trades; improvement loop and ops wrap the working spine.

## Invariants every spec upholds

1. AI is never inline on a live trade.
2. The R6 backtester — not the LLM — is the arbiter of any change.
3. Zero simulated FTMO breaches is a hard, binary promotion gate.
4. A human approves every promotion through Phase A and the funded cut-over.
5. MT5 is the source of truth on restart; on ambiguity, hold/flatten.
6. Same artifact, env-driven config, across hosts and phases.
7. Continuous, append-only audit trail (journal, trial ledger, versioned config).

## Phasing at a glance

- **Phase A** — local Windows PC + AI loop as Cowork scheduled tasks on the Max plan (dev → demo → free-trial → challenge).
- **Phase B** — migrate live engine to a London Windows VPS before the funded account.
- **Phase C** — swap the agent runtime to the Claude Agent SDK + Batch API on a separate Linux box.

The phasing changes *where things run* and *how the AI loop is powered* — never the deterministic spine or the agent contract.
