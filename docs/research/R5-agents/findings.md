# R5 — AI Improvement-Loop Framework & Orchestration

**Track:** R5 — AI improvement-loop framework & orchestration
**Question:** How do we build AI agents that develop, test, and continuously improve the EURUSD strategy — strictly *off* the live hot path — without letting the LLM curve-fit, race itself, run away on cost, or ever touch a live trade?
**Date:** 2026-06-02
**Status:** Research complete

---

## Summary

This track designs the **improvement loop**: an asynchronous, scheduled pipeline of LLM-driven agents that read the trade journal and backtest results, detect drift and overfitting, propose strategy refinements, and gate them through the deterministic backtester (R6) before any human-approved promotion. The single hardest constraint is architectural, not algorithmic: **the live loop (R1 signal → R4 risk governor → R3/MT5 execution) must remain plain deterministic Python with no LLM inline, ever.** The improvement loop runs on a **separate Linux box** (per R7) and communicates with the live Windows trader **only through the trade journal / state DB** — it reads artifacts and writes *proposals*, never live state.

**Framework recommendation: plain Python orchestration + the Claude Agent SDK as the agent runtime, with LLM calls issued via Anthropic's Batch API and model tiering.** For a low-frequency batch pipeline that runs after sessions / daily / weekly — not a chat agent, not a real-time loop — the simplest auditable thing wins. We do **not** adopt a heavyweight multi-agent orchestrator (CrewAI, AutoGen/AG2) because their value is dynamic agent-to-agent negotiation we do not need; our pipeline is a fixed DAG with three roles whose hand-offs are *deterministic file/DB writes*, which a 200-line Python scheduler expresses more transparently than a framework. The Claude Agent SDK earns its place narrowly: it gives us the same agent loop, tool-permissioning, and **context-isolated subagents** that power Claude Code, programmable in Python, with a permission model (`plan`, `dontAsk`) that structurally prevents an agent from doing anything but read logs and emit a proposal artifact ([Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview); [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)). **LangGraph is the credible runner-up** — its checkpointing is genuinely best-in-class for stateful, resumable runs ([LangGraph](https://www.langchain.com/langgraph)) — but for a pipeline whose "state" is already a durable SQLite/Parquet journal, a graph engine's persistence layer is redundant weight. **DSPy is complementary, not an alternative**: we can use it later to *compile/optimize* the hypothesis-generation prompt against a metric, but it does not orchestrate ([DSPy guide](https://myengineeringpath.dev/tools/dspy-guide/)).

**The boundary, stated once and enforced everywhere:** the LLM is allowed to **read** (journals, backtest reports, equity curves) and **propose** (a versioned strategy-config diff — a pull-request-like artifact). The LLM is **forbidden** to: place or modify trades, mutate live parameters, decide whether a change is "good," or write anything the live loop reads. **The backtester (R6), not the LLM, is the arbiter** of whether a proposal survives — and the R6 gates (≥200–300 trades, walk-forward, deflated-Sharpe, and the hard *zero FTMO rule breaches* gate) are computed by deterministic code the LLM cannot edit. Promotion is a separate gated step requiring rule-or-human approval and a config version bump; everything is reversible because every change is a committed diff.

**Runtime phasing (decided 2026-06-02, refines this track).** *Where the LLM calls are issued* is separated from *what the agents do*. The contract below — read journal → emit a versioned proposal diff → deterministic backtester gates it → human-approved promotion — is **runtime-agnostic**, so we phase the runtime to match cost and maturity (see §2.4 and `docs/specs/00-phase-roadmap.md`): **Phase A** runs the three agents as **Claude Desktop / Cowork scheduled tasks on the existing Claude Max subscription** (marginal cost ≈ the already-paid plan, no per-token billing) while the loop is low-frequency and a human approves every promotion anyway; **Phase C** graduates to the **Claude Agent SDK + Batch API** described throughout this doc once cadence/volume justify fully-unattended programmatic orchestration. The Batch-API design remains the long-term target; Cowork/Max is the cheap, lower-effort on-ramp that exercises the same contract.

**Cadence:** Performance Reviewer runs **after each trading session and a daily roll-up** (cheap model, summarizes the journal, computes drift statistics); Strategy Researcher runs **weekly or on a drift-trigger** (stronger model, proposes hypotheses); Backtest Analyst runs **on-demand whenever a hypothesis exists** (mostly deterministic code + a cheap model to narrate results), and a promotion proposal is produced only when R6 gates pass. State is passed between runs through the **state DB + a versioned config repo**; a single **promotion mutex / lease** prevents concurrent param changes from racing. Expected LLM spend is **single-digit to low-tens of dollars per month** — batch + low-frequency + tiering makes cost a rounding error against a $30–50/mo VPS.

---

## 1. Architecture spec

### 1.1 Two loops, one contract

```
        WINDOWS LIVE BOX (R7)                         LINUX IMPROVEMENT BOX (R7)
   ┌──────────────────────────────┐            ┌────────────────────────────────────┐
   │  LIVE LOOP  (deterministic,   │            │  IMPROVEMENT LOOP (async, scheduled,│
   │  NO LLM, hot path)            │            │  LLM-driven, OFF the hot path)      │
   │                               │            │                                     │
   │  R1 signal  ─►  R4 risk gov   │            │   ┌─ Performance Reviewer (cheap) ─┐│
   │      │            │           │            │   │  reads journal, computes drift  ││
   │      ▼            ▼           │            │   └────────────────┬───────────────┘│
   │  R3 / MT5 execution           │            │                    ▼                 │
   │      │                        │            │   ┌─ Strategy Researcher (strong) ─┐ │
   │      ▼                        │            │   │  proposes hypotheses / diffs    │ │
   │  TRADE JOURNAL  ──────────────┼───reads────┼──►└────────────────┬───────────────┘ │
   │  + STATE DB (SQLite/Parquet)  │            │                    ▼                  │
   │      ▲                        │            │   ┌─ Backtest Analyst (R6 + cheap)─┐ │
   │      │                        │            │   │  runs DETERMINISTIC backtester, │ │
   │      │                        │            │   │  applies gates, ranks, narrates │ │
   │      │                        │            │   └────────────────┬───────────────┘ │
   │      │                        │            │                    ▼                  │
   │  CONFIG (versioned) ◄─promote─┼──human/rule┼──  PROMOTION PROPOSAL (config diff)   │
   │  loaded at session start only │   approval │   = PR-like artifact, reversible      │
   └──────────────────────────────┘            └────────────────────────────────────┘
                                  ▲                                   │
                                  └── the ONLY write path back is a   ┘
                                      gated config-version bump,
                                      never live mutation
```

The arrow that matters most is the one that **does not exist**: there is no path from any LLM agent into the live decision path. The improvement box reads the journal and writes proposals into a config/version store; the live box loads config **only at session start** (or on an explicit, logged hot-reload), so a half-finished or unapproved proposal can never leak into a live trade mid-session. This is the same decoupling R7 mandates ("the two communicate only through artefacts… changes are promoted by a human-reviewed config bump, never by live mutation").

### 1.2 The three agents

**Performance Reviewer (the bookkeeper / drift sentinel).** Runs most often, cheapest model. It does **not** invent strategy; it *summarizes and surveils*. Inputs: the trade journal (§4). Outputs: a structured run-summary (expectancy in R, win rate, profit factor, max adverse/favourable excursion distributions, realized-vs-modeled slippage, FTMO rule-budget state) plus **drift flags**. Crucially, the drift *math* (CUSUM on per-trade R, expectancy-degradation tests, regime-mix comparison) is **deterministic code**; the LLM's job is to read those computed statistics, write a plain-language summary, and decide whether to *raise a flag* that triggers the Researcher — it is a router and a scribe, not a statistician. This keeps the numeric judgement reproducible and the narrative cheap.

**Strategy Researcher (the proposer).** Runs weekly or on a Reviewer drift-trigger, stronger model. Inputs: the Reviewer's summary, recent backtest reports, the current strategy config, and a fixed library of allowed levers (session windows, ER/ATR regime-gate thresholds, stop/TP R-multiples, trailing step — i.e. the R1 parameter surface). Output: **one or a small ranked set of hypotheses**, each expressed as a **versioned config diff with a written rationale** (§2.3). It is explicitly *budgeted* to a small number of candidate changes per run (§5) to fight multiple-testing. It never runs a backtest itself and never sees the privilege to apply a change.

**Backtest Analyst (the gatekeeper).** Runs whenever a hypothesis exists. It is **mostly deterministic**: it invokes the R6 custom event-driven loop (system of record) and the vectorbt sweep engine, then applies the R6 acceptance gates verbatim (expectancy ≥ +0.10R net; PF ≥ 1.3; Sharpe ≥ 1.0 / Sortino ≥ 1.5; walk-forward non-collapse; parameter stability; **deflated-Sharpe** significance under the trial count; and the hard **zero FTMO rule breaches** gate across history and Monte-Carlo reshuffles). A cheap LLM call only *narrates* the pass/fail report into the promotion proposal. The Analyst is the agent that says no; the gate logic is code the LLM cannot rewrite. **The backtester, not the LLM, decides whether a change is good.**

*(Optional, deferred — R8 Research Analyst:* a fundamental-overlay agent that ingests macro/calendar context; it would feed the Researcher's context, never the live loop, and is out of scope until the technical loop is stable.)*

### 1.3 State & data flow

State lives in two durable stores, both readable by the improvement box and one writable back under gating:

- **State DB / journal** (SQLite for the live write-path; Parquet snapshots for analytics) — the live↔improvement contract (§4). Read-only to the improvement loop.
- **Versioned config repo** (a git repo, or a `strategy_config` table with monotonic version + author + parent + diff + approval status). Every promotion is a commit; rollback is `checkout previous_version`.

Between agent runs, **no state lives in the LLM**. Each agent run reconstructs its context from the DB/files, does its job, and writes a typed artifact back to the DB. This is deliberate: a stateless-between-runs design means a crashed or re-run agent is idempotent and auditable, and we do not depend on a framework's in-memory checkpoint to be correct. (This is precisely why LangGraph's headline feature — durable in-graph checkpointing across long sessions — buys us little: our durability is the database, not the agent runtime.)

---

## 2. Framework recommendation & the deterministic/LLM boundary

### 2.1 The landscape, weighed for *this* job

The 2025–2026 agent-framework space is crowded — OpenAI shipped its Agents SDK in March 2025 (replacing the experimental Swarm), Google added ADK, Anthropic shipped the Claude Agent SDK, and LangGraph reached 1.0 in October 2025 ([framework comparison, DeepResearch Ninja](https://deepresearch.ninja/2026/05/AI-Agent-Frameworks-A-Comparative-Analysis-of-DSPy-Claude-Agent-SDK-OpenAI-Agents-SDK-CrewAI-AutoGen-LangGraph-and-Google-ADK/); [2026 framework showdown, QubitTool](https://qubittool.com/blog/ai-agent-framework-comparison-2026)). The key realization is that most of these frameworks solve problems we do not have. Their differentiators are *orchestration models for dynamic, conversational, real-time multi-agent systems*: LangGraph's conditional graphs, CrewAI's role-based crews, OpenAI's explicit handoffs, AutoGen's GroupChat negotiation ([framework overview, gurusup](https://gurusup.com/blog/best-multi-agent-frameworks-2026)). Our pipeline is the opposite shape: a **fixed three-stage DAG, run on a schedule, with deterministic file/DB hand-offs and no agent-to-agent chatter**.

- **Plain Python + direct SDK calls** is the baseline and the bulk of the right answer. The orchestration ("after session, run Reviewer; if flag, run Researcher; if hypothesis, run Analyst") is a cron-driven script with a few function calls. It is the most auditable, has zero framework lock-in, and is trivial to reason about. Its only weakness is that you hand-roll tool-use loops and context management — which is exactly the gap the Claude Agent SDK fills cleanly.
- **Claude Agent SDK** gives "the same tools, agent loop, and context management that power Claude Code, programmable in Python," with built-in `Read/Grep/Glob/Bash/WebSearch` tools, a `ClaudeAgentOptions` permission model, and **context-isolated subagents** whose intermediate tool calls stay inside the subagent and only return a final message ([Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview); [Subagents in the SDK](https://docs.claude.com/en/docs/agent-sdk/subagents)). Two features map directly onto our needs: (1) permission modes like `plan` (planning without execution) and `dontAsk` (deny anything not pre-approved) let us run an agent that *cannot* do anything but read and propose — a structural, not prompt-based, guardrail ([Python reference](https://platform.claude.com/docs/en/agent-sdk/python)); (2) subagent context isolation keeps the Reviewer's noisy journal-reading from polluting the Researcher's reasoning context. It is explicitly positioned for **safety-critical domains including finance** ([CrewAI/AutoGen/Claude SDK comparison, CallSphere](https://callsphere.tech/blog/ai-agent-frameworks-crewai-autogen-comparison)). The honest trade-off: it locks us to Claude models and is lighter on multi-agent orchestration than LangGraph — both acceptable here, since we *want* a single model family for cost predictability and we are providing the orchestration ourselves.
- **LangGraph** is the strongest *general* choice and the runner-up. Its checkpointing saves state at every node so runs resume exactly where they failed, and it has the best observability story (LangSmith) ([LangGraph](https://www.langchain.com/langgraph); [checkpointing best practices](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)). But durable in-graph checkpointing is a solution to *long-running, in-memory, resumable* agent state — and our state is already durable in the DB, our runs are short (minutes), and resumption means "re-read the journal and re-run," which is free. Adopting LangGraph would add a dependency and a persistence layer that duplicates the database we must have anyway. **Keep it as the fallback** if the pipeline ever grows into genuinely long, branching, resumable workflows.
- **OpenAI Agents SDK / Swarm** — production-grade, handoff-centric ([framework overview](https://gurusup.com/blog/best-multi-agent-frameworks-2026)). Fine, but it pulls us toward OpenAI models and a handoff abstraction we do not need.
- **CrewAI** — lowest learning curve, role-based DSL ([comparison](https://gurusup.com/blog/best-multi-agent-frameworks-2026)). Tempting because "three roles" maps onto "a crew," but its value is autonomous role *collaboration*; our roles do not collaborate at runtime, they hand off artifacts. The DSL would obscure, not clarify, a deterministic DAG.
- **AutoGen / AG2** — **AutoGen is in maintenance mode (bug/security fixes only)** as of 2025–2026 ([comparison, gurusup](https://gurusup.com/blog/best-multi-agent-frameworks-2026)). Building a multi-year system on a maintenance-mode dependency repeats the R6 backtrader mistake. **Avoid as a foundation.**
- **LlamaIndex** — a retrieval/RAG framework first; we have no large-corpus retrieval problem (our "knowledge" is a structured journal), so it is the wrong tool.
- **DSPy** — **complementary, not competing.** DSPy *optimizes prompts programmatically against a metric*; it does not orchestrate pipelines ([DSPy vs orchestration, Morph](https://www.morphllm.com/llm-frameworks); [DSPy guide](https://myengineeringpath.dev/tools/dspy-guide/)). The natural fit is to later use DSPy to compile the Strategy Researcher's hypothesis prompt against a metric like "fraction of proposals that pass the R6 gates" — improving proposal quality without touching orchestration. There is also a broader 2026 "compiled AI" trend toward generating deterministic artifacts at compile time and executing without further model calls, prized exactly for *auditability and reduced runtime exposure* in safety-critical settings ([Compiled AI, arXiv](https://arxiv.org/html/2604.05150)) — philosophically aligned with our "LLM proposes, deterministic code executes" stance.

**Verdict:** plain Python scheduler + Claude Agent SDK runtime + Anthropic Batch API. Reach for LangGraph only if/when the workflow outgrows a linear DAG. Add DSPy later to tune the proposer prompt. This is the simplest auditable thing that works, with honest acknowledgement that the "framework" is mostly our own 200-line orchestrator.

### 2.2 The deterministic-vs-LLM boundary (the rule)

| Action | Allowed actor | Forbidden to LLM? |
|---|---|---|
| Generate live signal | R1 deterministic code | **Yes — no LLM** |
| Size position / enforce FTMO limits | R4 risk governor (deterministic) | **Yes — no LLM** |
| Place / modify / close a trade | R3 / MT5 execution (deterministic) | **Yes — no LLM** |
| Read trade journal & backtest reports | Any agent | No (read-only) |
| Compute drift/overfitting statistics | Deterministic code | LLM reads results, does not compute the verdict |
| Propose a parameter change | Strategy Researcher (LLM) | Output is a *diff*, applied to nothing |
| Decide if a change is good | **R6 backtester gates (deterministic)** | **Yes — the LLM is not the arbiter** |
| Apply / promote a change to live config | Gated promotion step (rule + human) | **Yes — never the LLM, never live mutation** |

The LLM's entire authorized surface is **READ logs/backtests** and **PROPOSE a diff**. Validation is done by the deterministic R6 backtester; promotion is a separate gated step. The Claude Agent SDK's `dontAsk`/`plan` permission modes let us enforce "this agent may run `Read`/`Grep` and emit a file, nothing else" at the runtime level, so a prompt-injection or a misbehaving model still *cannot* reach a trade.

### 2.3 How a "proposed change" is represented

Every proposal is a **versioned strategy-config diff** — a pull-request-like artifact — so it is auditable and reversible:

```json
{
  "proposal_id": "2026-06-02-w23-001",
  "parent_config_version": 47,
  "author": "strategy_researcher",
  "created_utc": "2026-06-02T18:05:00Z",
  "hypothesis": "London-open ER gate too loose in low-vol regimes; tightening should cut chop losses.",
  "diff": [
    {"param": "regime.er_threshold", "from": 0.30, "to": 0.38},
    {"param": "session.london_open_buffer_min", "from": 5, "to": 10}
  ],
  "expected_effect": "fewer false breakouts in ER<0.38 regimes; slight trade-count drop",
  "trial_budget_id": "2026-W23",            // ties to multiple-testing accounting (§5)
  "status": "proposed",                       // proposed -> backtested -> passed/failed -> promoted/rejected
  "backtest_report_ref": null,
  "approval": {"rule_gate": null, "human": null}
}
```

Stored in the versioned config store. `status` advances only as deterministic code (the Analyst's gate run) or an approver acts on it. Rollback is reverting to `parent_config_version`. Nothing here is interpreted by the live loop until it reaches `promoted` *and* the live box reloads config at a session boundary.

### 2.4 Runtime phasing — Cowork/Max on-ramp → Batch API (decided 2026-06-02)

The agent **logic** (prompts, the proposal-diff schema §2.3, the trial ledger §5, the gate sequence §1.2) is identical across runtimes; only the **harness that issues the LLM call and reads/writes the artifacts** changes. We therefore define a thin `AgentRuntime` seam and ship two implementations:

| Phase | Runtime | How agents are invoked | Cost | Trade-offs |
|---|---|---|---|---|
| **A** (default now) | **Claude Desktop / Cowork scheduled tasks** on the existing **Max** plan | A scheduled task fires each agent on cadence; the task prompt points at the journal/DB and the proposal/ledger files, and instructs the agent to read + emit the typed artifact | ≈ **$0 marginal** (covered by the already-paid Max subscription) | Subscription, not an SLA → keep within fair-use (our volume is tiny); runs on the **same local box** as the live trader in Phase A, so schedule them **outside active trading sessions** (§3) so a backtest can't starve the engine; promotion stays **human-approved** |
| **C** (later) | **Claude Agent SDK + Anthropic Batch API** | The 200-line Python orchestrator (§2.1) invokes the SDK with `plan`/`dontAsk` permission modes; LLM calls go through the Batch API with model tiering | **~$5–30/mo** (§6) | Fully unattended/programmatic; structural permission guardrails; needs a separate Linux box (R7 Phase B/C) for clean isolation |

**Why this is safe to phase rather than build the API path first:** the deterministic spine (R1 signal, R4 risk, R3 execution, R6 backtester and its gates) is **completely independent of the agent runtime** — the LLM never touches the live path in either phase, and the *arbiter* of any change is always the R6 backtester, which is plain CPU code. Cowork/Max simply substitutes a human-scheduled desktop session for a cron + Batch call. The one discipline Phase A must preserve to keep Phase C a drop-in swap: **every Cowork agent run must write the same artifacts the API path would** — the structured proposal JSON (§2.3), a trial-ledger entry (§5), and a run-summary row — so the audit trail and the multiple-testing accounting are continuous across the migration. The implementation spec pins this in `docs/specs/06-improvement-loop.md`.

**Migration trigger (A → C):** move when any of these holds — the Researcher's useful cadence exceeds what hand-scheduled Cowork runs comfortably cover; we want the loop running while the desktop app is closed / on a headless box; or fair-use friction appears. None are expected early; the journal volume and weekly Researcher cadence sit far inside Max limits.

---

## 3. Cadence & orchestration

**When each agent runs:**

- **Performance Reviewer:** *after every trading session* (London/NY overlap close) and a *daily roll-up* at the Prague-midnight FTMO reset. Cheap model. Computes/refreshes drift statistics, writes a run-summary, and decides whether to raise a drift flag.
- **Strategy Researcher:** *weekly* (scheduled deep review) **and** *on any Reviewer drift-trigger*. Stronger model. Emits ≤ N hypotheses (budgeted, §5).
- **Backtest Analyst:** *event-driven* — fires whenever an unprocessed hypothesis exists. Mostly deterministic; one cheap narration call per report.
- **Promotion:** never automatic for a live-affecting change. A passed proposal becomes a *promotion proposal*; a human (or, for narrowly-scoped pre-approved parameter ranges, a rule) approves, which bumps the config version. The live box adopts it only at the next session start.

**Pipeline (one cycle):**

```
[session close]
  → Performance Reviewer: journal → run-summary + drift flags        (cheap LLM)
      └─(flag raised OR weekly tick)→ Strategy Researcher: → ranked config diffs   (strong LLM)
            └→ Backtest Analyst: R6 event-loop + vectorbt sweep
                  → apply gates (expectancy/PF/Sharpe/WFO/DSR/zero-breach)  (DETERMINISTIC)
                     ├─ fail → mark rejected, record in trial ledger, stop
                     └─ pass → emit Promotion Proposal                  (cheap LLM narrates)
                           └→ human/rule approval → config version bump
                                 └→ live box loads new config at next session start
```

**State passing between runs:** entirely via the **state DB + versioned config store** (§1.3). No agent relies on another agent being in memory; each reconstructs context from durable storage. This makes every run idempotent and re-runnable for audit.

**Preventing racing param changes:** a single **promotion mutex / lease** on the config store. Concurrency rules:
1. Only one proposal may hold the `in_promotion` lease at a time; the Researcher must branch every new proposal from the *current committed* `config_version`, and the Analyst re-validates against that version before promotion. A proposal whose `parent_config_version` is stale is automatically re-queued for re-backtest, never blind-merged.
2. The live box reads config only at session boundaries (or explicit logged hot-reload), so even a mid-flight promotion cannot half-apply to an open trade.
3. All promotions serialize through the version counter (monotonic, append-only), giving a total order and a clean rollback target. This is the standard optimistic-concurrency pattern (compare-and-swap on version) and removes the need for the LLM to reason about concurrency at all.

---

## 4. Journaling / logging design — the live↔improvement contract

This schema is the **contract** between the deterministic live loop and the AI improvement loop. It must serve two masters: (a) make every live decision **auditable** after the fact, and (b) give the agents **clean, structured, machine-readable inputs** to learn from. A backtest is a snapshot; continuous live-vs-expected comparison is what turns it into a living benchmark ([drift monitoring rationale, Algo Studio](https://algo-studio.com/)).

**Format:** write-path = **append-only JSONL** per trading day on the live box (cheap, crash-safe, human-readable, easy to ship over the journal channel R7 describes) **mirrored into SQLite** for indexed queries; periodic **Parquet** snapshots for the agents' columnar analytics (expectancy distributions, MAE/MFE histograms). JSONL for the contract, SQLite for the live state, Parquet for analysis — each format where it is strongest.

**Per-trade record (minimum fields):**

```json
{
  "trade_id": "EURUSD-2026-06-02-0317",
  "config_version": 47,                       // which strategy version produced this — ties trades to params
  "schema_version": 3,
  // --- signal inputs (so the AI can re-derive WHY) ---
  "signal": {
    "session": "london_ny_overlap",
    "breakout_level": 1.08742, "direction": "long",
    "er": 0.41, "atr_pips": 9.3, "regime_gate_passed": true,
    "entry_reason": "range_high_break + ER>=thr + ATR in band"
  },
  // --- regime state at decision time ---
  "regime": {"er": 0.41, "atr_pips": 9.3, "atr_percentile": 0.62, "vol_state": "normal"},
  // --- sizing rationale (R4) ---
  "sizing": {"risk_fraction": 0.0035, "equity_at_entry": 101230.50,
             "risk_usd": 354.31, "sl_distance_pips": 11.0, "lots": 0.32,
             "slippage_spread_buffer": 0.20, "killswitch_state": "armed_60pct"},
  // --- fills & costs (the make-or-break for an intraday edge) ---
  "fills": {"entry_req_price": 1.08742, "entry_fill_price": 1.08745,
            "entry_slippage_pips": 0.3, "spread_at_entry_pips": 0.4,
            "commission_usd": 4.48, "exit_fill_price": 1.08901,
            "exit_slippage_pips": 0.2, "exit_reason": "trail_step"},
  // --- outcome ---
  "outcome": {"r_multiple": 1.42, "pnl_usd": 502.10, "gross_pips": 15.9, "net_pips": 15.0,
              "mae_pips": 4.1, "mfe_pips": 18.3,           // adverse/favourable excursion
              "duration_min": 73, "partial_tp_hit": true},
  // --- FTMO rule-budget state (audit + drift on rule pressure) ---
  "rule_budget": {"daily_loss_used_usd": 612.40, "daily_budget_usd": 5000.0,
                  "daily_pct_used": 0.122, "overall_dd_usd": 1870.0,
                  "killswitch_tripped": false, "requests_used_today": 184},
  // --- modeled-vs-realized (feeds slippage/cost drift detection) ---
  "model_vs_real": {"modeled_slippage_pips": 0.25, "realized_slippage_pips": 0.30,
                    "modeled_spread_pips": 0.40, "realized_spread_pips": 0.40},
  "timestamps": {"signal_utc": "...", "entry_utc": "...", "exit_utc": "..."}
}
```

Why each block matters to the AI: **signal + regime** let the Researcher segment performance by regime and propose gated changes (e.g. "ER threshold underperforms in `vol_state=low`"); **sizing** lets it verify R4 behaved and reason about risk-of-ruin without re-running R4; **fills + model_vs_real** are the single most important columns — they expose cost/slippage drift, the thing that silently kills an intraday breakout edge (R6's central warning); **outcome incl. MAE/MFE** drives expectancy and stop/target tuning; **rule_budget** lets the Reviewer detect creeping rule pressure *before* a breach. Logging `config_version` on every trade is what makes live-vs-backtest attribution honest — you always know which parameter set produced which outcome.

Alongside per-trade rows, the live box also logs **rejected signals** (signal fired but a gate/risk/news-blackout blocked it, with the reason) and **heartbeat/health** rows, so the AI can also learn from trades *not* taken and so the Reviewer can distinguish "no edge today" from "engine was down."

---

## 5. Overfitting & drift governance by the AI

The central danger of an LLM in the loop is that it is an *infinite hypothesis generator*: left unchecked it will propose tweak after tweak, and by sheer multiple testing some will pass any single backtest by luck. This is the classic data-snooping problem, and it is exactly what the deflated-Sharpe machinery exists to counter. Selecting the best backtest among many candidates inflates apparent significance; the **Deflated Sharpe Ratio** corrects the Sharpe for the *number of trials*, non-normal returns, and sample length, and López de Prado's related tools (CSCV → Probability of Backtest Overfitting) estimate how likely an in-sample winner is to fail out of sample ([Bailey & López de Prado, *The Deflated Sharpe Ratio* (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551); [DSR overview, Wikipedia](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio); [minimum backtest length & DSR, Jansen](https://stefan-jansen.github.io/machine-learning-for-trading/08_ml4t_workflow/01_multiple_testing/)). The LLM literature reinforces the warning: systematic, broad-cross-section backtests show that previously-reported LLM strategy advantages "deteriorate significantly" once data-snooping and survivorship bias are controlled ([*Can LLM Strategies Outperform the Market in the Long Run?* arXiv](https://arxiv.org/html/2505.07078v3); [overfitting & data-snooping, Surmount](https://surmount.ai/blogs/backtests-overfitting-data-snooping-avoid)).

**Governance mechanisms (all enforced by deterministic code, not LLM goodwill):**

1. **A trial ledger.** *Every* hypothesis the Researcher emits — pass or fail — is recorded against a period budget. The deflated-Sharpe / PBO computation in the Analyst is fed the **true cumulative trial count** for the period, so the more the LLM proposes, the higher the significance bar its winners must clear. This directly converts "the LLM tried 40 things this month" into a stricter gate, neutralizing data-snooping at the source. The trial count is code-maintained; the LLM cannot reset it.
2. **Hard trial budget.** The Researcher is capped at a small N proposals per run/week. Fewer, better-motivated hypotheses (each with a written economic rationale, not a parameter-sweep result) beat a flood.
3. **Out-of-sample lockbox.** R6's walk-forward + a held-out OOS window that the LLM **never sees in its context** — it only ever reads in-sample/development summaries. A proposal must survive OOS it could not have fit to.
4. **The zero-FTMO-breach gate is non-negotiable and binary.** No amount of profitability or LLM advocacy promotes a config whose simulated equity ever crosses a daily or overall FTMO floor (R4/R6). The LLM cannot argue around a hard gate.

**Drift detection (Performance Reviewer, deterministic stats + LLM routing):** the Reviewer continuously compares live realized performance against the backtest baseline using **CUSUM control charts on per-trade R** (early detection of small, sustained drifts, low compute) plus expectancy-degradation and regime-mix tests; CUSUM is the standard tool for catching exactly this kind of slow live-vs-expected divergence and regime shift ([CUSUM for sequential change detection, arXiv](https://arxiv.org/pdf/2206.06777); [volatility-regime shifting, Dozen Diamonds](https://www.dozendiamonds.com/volatility-regime-shifting/)). **Graduated response (a deterministic policy table, not an LLM whim):**

- **Within tolerance** → log, no action.
- **CUSUM warning (mild expectancy decay, costs creeping)** → raise a flag that triggers the Strategy Researcher to *propose a retune*; nothing changes live.
- **CUSUM alarm (sustained degradation or realized slippage ≫ modeled)** → **shadow / reduce**: optionally cut `risk_fraction` via the R4 governor's own deterministic rule (not the LLM) and run the candidate retune in shadow against live signals.
- **Breach-risk or regime break (rule-budget pressure rising, equity-curve break)** → **stand-down**: the deterministic governor halts new entries; the AI's role is only to *explain and propose*, never to keep trading. Stand-down is a live-loop safety action and is owned by R4, not R5 — the AI can recommend it but the deterministic governor enforces it. This is the fail-safe philosophy carried into the improvement loop.

The throughline: **statistics are computed by code, the verdict on a change is rendered by the backtester, and the only thing the LLM does is read, summarize, route, and propose.**

---

## 6. Token-cost budgeting

Because this is a **batch, low-frequency** pipeline, spend is small and easily bounded. Anthropic's current pricing (held steady into 2026): **Haiku 4.5 ≈ $1 / $5**, **Sonnet 4.6 ≈ $3 / $15**, **Opus 4.7 ≈ $5 / $25** per million input/output tokens; the **Batch API halves all token costs (~50% off)** and **prompt caching cuts cached input by ~90%**, stacking to ~95% off reused context ([Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing); [Anthropic pricing guide 2026, Finout](https://www.finout.io/blog/anthropic-api-pricing)).

**Model tiering (cheap for volume, strong for the rare hard call):**

- **Haiku (cheap) — Performance Reviewer summarization/journaling and the Backtest Analyst's report narration.** These are high-frequency, low-reasoning, high-structure tasks (read computed stats → write a summary). Runs after each session/daily.
- **Sonnet/Opus (strong) — Strategy Researcher hypothesis generation only.** This is the one place real reasoning earns its cost, and it runs *weekly or on-trigger* — a handful of times a month.

**Frequency × bound (order-of-magnitude):** Reviewer ≈ 1–2 runs/day (≈ 30–60/month) on Haiku, each a few-thousand-token summary → well under a dollar/month even before batch/caching. Researcher ≈ 4–8 runs/month on Sonnet/Opus, each maybe tens of thousands of tokens of context → low single-digit dollars/month. Analyst narration ≈ a few Haiku calls per hypothesis → negligible. The **hard cost cap** is structural: the trial budget (§5) limits Researcher runs, the journal context is bounded and **prompt-cached** across runs, and **the expensive part of the pipeline (backtesting) is deterministic CPU, not tokens.** Realistic envelope: **roughly $5–$30 / month**, a rounding error beside the $30–50/mo VPS (R7). Put a simple monthly token budget with an alert in the orchestrator as a belt-and-braces cap; there is no scenario where a low-frequency batch loop with tiering runs away on cost.

---

## Sources

- Anthropic — [Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview) · [Subagents in the SDK](https://docs.claude.com/en/docs/agent-sdk/subagents) · [Agent SDK Python reference](https://platform.claude.com/docs/en/agent-sdk/python) · [anthropics/claude-agent-sdk-python (GitHub)](https://github.com/anthropics/claude-agent-sdk-python)
- LangChain — [LangGraph product page](https://www.langchain.com/langgraph) · [LangGraph checkpointing best practices 2025](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- Framework comparisons — [DeepResearch Ninja: DSPy/Claude/OpenAI/CrewAI/AutoGen/LangGraph/ADK](https://deepresearch.ninja/2026/05/AI-Agent-Frameworks-A-Comparative-Analysis-of-DSPy-Claude-Agent-SDK-OpenAI-Agents-SDK-CrewAI-AutoGen-LangGraph-and-Google-ADK/) · [QubitTool 2026 showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026) · [gurusup best multi-agent frameworks 2026](https://gurusup.com/blog/best-multi-agent-frameworks-2026) · [CallSphere CrewAI/AutoGen/Claude SDK](https://callsphere.tech/blog/ai-agent-frameworks-crewai-autogen-comparison) · [Morph LLM frameworks (DSPy vs orchestration)](https://www.morphllm.com/llm-frameworks)
- DSPy & compiled AI — [DSPy guide, MyEngineeringPath](https://myengineeringpath.dev/tools/dspy-guide/) · [Compiled AI: deterministic code generation (arXiv)](https://arxiv.org/html/2604.05150)
- Overfitting / multiple testing — [Bailey & López de Prado, *The Deflated Sharpe Ratio* (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) · [Deflated Sharpe ratio (Wikipedia)](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio) · [Minimum backtest length & DSR (Jansen)](https://stefan-jansen.github.io/machine-learning-for-trading/08_ml4t_workflow/01_multiple_testing/) · [Overfitting & data-snooping (Surmount)](https://surmount.ai/blogs/backtests-overfitting-data-snooping-avoid)
- LLMs in quant research — [*Can LLM Strategies Outperform the Market in the Long Run?* (arXiv)](https://arxiv.org/html/2505.07078v3)
- Drift / regime detection — [CUSUM for sequential change detection (arXiv)](https://arxiv.org/pdf/2206.06777) · [Volatility regime shifting (Dozen Diamonds)](https://www.dozendiamonds.com/volatility-regime-shifting/) · [Strategy drift monitoring (Algo Studio)](https://algo-studio.com/)
- Cost — [Claude API pricing (Anthropic)](https://platform.claude.com/docs/en/about-claude/pricing) · [Anthropic API pricing guide 2026 (Finout)](https://www.finout.io/blog/anthropic-api-pricing)
