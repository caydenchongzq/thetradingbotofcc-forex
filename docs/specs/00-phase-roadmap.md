# 00 — Phase Roadmap

> The implementation plan for the FTMO EURUSD bot, sequenced into three phases by **where it runs** and **how the AI loop is powered**. This is the entry point for `docs/specs/`. Each component spec (01–07) is written to be implementation-ready *independent* of phase; this file says **what to build in what order, what "done" means at each gate, and what changes between phases**.
>
> Source decisions: README §9 (locked), the R1–R8 findings, and the two rollout decisions of 2026-06-02 (local-first host; Max-subscription AI runtime first). See `docs/research/README.md` → "Post-research decisions".

---

## 0. The two axes we are phasing

Everything in the project splits into a **deterministic spine** and an **AI improvement loop**. The phasing moves each along its own axis without ever changing the contract between them.

```
                       Phase A                Phase B                Phase C
                  (local + Max)          (VPS + Max/hybrid)      (VPS + full API)
  ────────────────────────────────────────────────────────────────────────────────
  Live engine     local Windows PC  ───►  London Windows VPS  ───►  (unchanged)
  host                                     (before funded a/c)
  ────────────────────────────────────────────────────────────────────────────────
  AI runtime      Cowork scheduled  ───►  Cowork (or begin     ───► Claude Agent SDK
                  tasks on Max            hybrid)                    + Batch API,
                  subscription                                       separate Linux box
  ────────────────────────────────────────────────────────────────────────────────
  Account         demo → free-trial ───►  challenge → funded   ───►  funded (scaled)
  stage           → challenge
  ────────────────────────────────────────────────────────────────────────────────
```

The invariant across all phases: **the live trade decision is deterministic Python; the LLM only reads journals and proposes versioned config diffs; the R6 backtester is the arbiter; promotion is a gated config-version bump.** Nothing in the phasing relaxes that.

---

## 1. Build order (component dependency graph)

Build the spine bottom-up so every layer can be tested against the one below before the next is added. The strategy — the biggest unknown — is built *last* in the spine, on top of an already-trusted risk/execution/journal stack, so it can be swapped freely.

```
   (1) Journal & State        ◄── everything writes here; build first, it's the contract
        04-journal-state.md
            │
   (2) Risk Governor          ◄── "risk before reward"; pure, fully unit-testable offline
        02-risk-governor.md
            │
   (3) Execution / MT5        ◄── needs risk-approved orders to place; reconciliation + magic
        03-execution-mt5.md
            │
   (4) Backtest harness       ◄── needs journal schema + risk + a strategy interface to drive
        05-backtest-harness.md
            │
   (5) Strategy Engine        ◄── built last in the spine, validated in (4) before going live
        01-strategy-engine.md
            │
   (6) Improvement loop       ◄── reads the journal (1) + backtests (4); proposes config diffs
        06-improvement-loop.md
            │
   (7) Ops / deployment       ◄── supervises (2)(3)(5) as a service; phased host
        07-ops-deployment.md
```

Rationale for the order: the **journal schema is the contract** every other component reads or writes, so it is frozen first (04). The **Risk Governor (02)** is pure arithmetic with no I/O, so it is built and exhaustively unit-tested before anything can place an order — "risk before reward" (README §11). **Execution (03)** is the first component that touches the broker; it only ever places orders the Risk Governor already approved. The **backtest harness (05)** needs the journal schema, the risk model, and a strategy *interface* (not yet a strategy) so it can replay candidates. The **strategy engine (01)** is implemented last in the spine and immediately validated through the harness. The **improvement loop (06)** and **ops (07)** wrap the working spine.

---

## 2. Phase A — Local + Cowork/Max (the build-and-prove phase)

**Goal:** a fully working deterministic spine, validated in backtest, forward-tested on the FTMO free trial, and ready to attempt the challenge — all running on the local Windows PC, with the AI loop running as Cowork scheduled tasks at ≈ zero marginal cost.

### 2.1 What runs where
- **Live engine:** local Windows PC. Auto-logon console session, MT5 terminal kept open, Python engine supervised by NSSM/WinSW, watchdog + healthchecks heartbeat (07).
- **AI loop:** Cowork scheduled tasks on the **same machine**, on the existing Max plan (06 §"Runtime: Cowork"). Scheduled **outside** the London/NY-overlap session so a backtest sweep can never starve the live engine (R7 host-phasing note).
- **Account:** demo MT5 first, then the FTMO **free trial**, then a small/cheap **challenge** once metrics clear the gates.

### 2.2 Milestones & exit criteria (each gates the next)

| # | Milestone | Exit criteria (must all hold) |
|---|---|---|
| A0 | Repo scaffold + config + journal | `src/` skeleton, pinned lockfile, env-driven config loader, journal writes/reads round-trip (JSONL→SQLite→Parquet), schema-versioned. Unit tests green. |
| A1 | Risk Governor | All sizing/kill-switch/limit/forbidden-practice unit tests pass, **including property tests that no approved order can breach the daily or overall floor** under worst-case slippage. 100% branch coverage on the veto paths. |
| A2 | Execution adapter | Against a **demo** account: place/modify/close with SL/TP by magic number; cold-boot **reconciliation** correctly classifies pre-existing positions; idempotent intent log prevents double-send in a kill-and-restart test. |
| A3 | Backtest harness | Event-driven loop reproduces a hand-checked trade tape on a fixture; spread/commission/slippage modelled; **FTMO rule simulation** flags a deliberately-breaching strategy; walk-forward + deflated-Sharpe plumbing works. |
| A4 | Strategy engine validated | EURUSD 15m session-gated breakout + ER/ATR regime gate implemented; backtest on Dukascopy tick history clears **all R6 gates** (expectancy ≥ +0.10R net, PF ≥ 1.3, Sharpe ≥ 1.0, walk-forward non-collapse, DSR significant, **zero simulated FTMO breaches**). |
| A5 | Forward-test on free trial | Engine runs unattended on the FTMO **free trial** for an agreed window; live fills, slippage, and rule-budget tracking match backtest assumptions within tolerance; no engine crashes unrecovered by the watchdog. |
| A6 | Improvement loop live (Cowork) | Performance Reviewer + Strategy Researcher + Backtest Analyst run as Cowork scheduled tasks; a proposal flows end-to-end (journal → diff → backtest gates → human-approved version bump) and the trial ledger increments. |
| **A→B gate** | **Ready to risk money on uptime** | Challenge-readiness: the strategy has cleared A4, forward-tested clean in A5, and we are about to attempt (or have passed) a paid challenge and need 24/5 reliability for the **funded** account. |

### 2.3 Phase-A simplifications we deliberately accept (and undo later)
- AI loop shares the live box (mitigated by off-session scheduling).
- AI runtime is hand-scheduled Cowork, not programmatic Batch API.
- Single-machine durability (off-box backup still required).
None of these touch the deterministic spine or the agent contract, so undoing them in B/C is configuration + host work, not redesign.

---

## 3. Phase B — London Windows VPS (the uptime phase)

**Trigger:** before the first **funded** account goes live (provision in advance; run in parallel on demo to confirm parity, then cut over).

**What changes:**
- Live engine migrates to a **London-region Windows VPS** (R7: 4 vCPU / 8 GB target, NVMe, 99.9%+, LD4 proximity for fill quality). Same artifact, same pinned stack, new `.env`.
- **Restore live/improvement-box separation**: the AI loop moves off the trading box. It may stay on Cowork (run from the desktop / a separate machine) or begin the hybrid toward Phase C.
- Full ops surface goes live: NSSM service, watchdog with IPC re-init + backoff, Telegram alerts, healthchecks dead-man's-switch, on-box **and** off-box journal backups, locked-down RDP, secrets via env/DPAPI.
- **No US geolocation login**, even via VPN (FTMO hard rule).

**Exit criteria (B→C gate):** engine runs unattended 24/5 on the VPS across a full funded-account cycle with green heartbeat, reconciliation verified across at least one real crash/restart and one deploy, backups restorable. We move to C only when the AI cadence/volume actually justifies leaving Cowork.

---

## 4. Phase C — Full API / Batch (the scale phase)

**Trigger (any of):** Researcher cadence outgrows hand-scheduled Cowork runs; we want the loop running while the desktop app is closed / on a headless box; or fair-use friction appears. None expected early.

**What changes (harness swap only):**
- Agent runtime swaps from Cowork scheduled tasks to the **Claude Agent SDK + Anthropic Batch API** with model tiering (Haiku for Reviewer/narration, Sonnet/Opus for the Researcher), behind the same `AgentRuntime` seam (06 §"Runtime seam").
- AI loop runs on a **separate Linux box** (cheap VM or container), reading the journal and writing proposals over the artifact channel — no new contract.
- `plan`/`dontAsk` permission modes enforce "read + propose only" structurally; monthly token budget + alert as a belt-and-braces cap (R5 §6).

**Unchanged:** the deterministic spine, the journal contract, the proposal-diff schema, the trial ledger, the gate sequence, and human-approved promotion. Because Phase A already writes the identical artifacts, this is a drop-in substitution.

---

## 5. Cross-phase invariants (never violated by phasing)

1. **AI off the hot path.** No LLM call is ever inline on a live trade, in any phase.
2. **The backtester is the arbiter.** No proposal reaches live config without passing the deterministic R6 gates; the LLM cannot edit the gates.
3. **Zero simulated FTMO breaches** is a hard, binary promotion gate.
4. **Human approves every promotion** through at least Phase A and the funded cut-over.
5. **MT5 is the source of truth on restart**; reconcile before acting; on ambiguity, hold/flatten.
6. **Same artifact, env-driven config** across hosts — no code forks between local and VPS.
7. **Continuous audit trail**: the journal, trial ledger, and versioned config are append-only and survive every migration.

---

## 6. Immediate next actions (Phase A, in order)

1. Scaffold the repo (`src/engine`, `src/risk`, `src/execution`, `src/journal`, `src/backtest`, `src/agents`, `config/`, `tests/`), pin the toolchain, add the env-driven config loader. → spec 04, 07.
2. Implement & exhaustively test the **Journal/State** layer (the contract). → spec 04.
3. Implement & exhaustively test the **Risk Governor** offline. → spec 02.
4. Implement the **Execution adapter** against a demo account; prove reconciliation. → spec 03.
5. Stand up the **backtest harness** against a fixture. → spec 05.
6. Implement the **strategy engine**; validate through the harness against the R6 gates. → spec 01.
7. Wire the **improvement loop** as Cowork scheduled tasks. → spec 06.
8. Forward-test on the **free trial**; harden ops; prepare the VPS migration runbook. → spec 07.
