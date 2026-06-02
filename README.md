# thetradingbotofcc-forex

> A technical Forex trading bot with a deterministic execution core, wrapped by an AI team that develops, tests, and continuously improves the strategy — built to pass and stay funded on an FTMO prop-firm account.

**Status:** 🧪 Exploration / architecture stage — no code committed yet. This README defines _what we're building and why_, and which decisions are locked vs still open (see §9). Research tracks that feed the open decisions live in [`docs/research/`](docs/research/).

---

## 1. Vision

Trade forex like a disciplined desk, not a single rigid indicator script. A **deterministic technical engine** makes and executes the actual trades; a **team of AI agents** sits around it to research, backtest, refine, and continuously improve the strategy based on real results.

The thesis behind starting over: the previous failures were not bad luck. A fixed indicator stack with no regime awareness and no hard risk governor will eventually hit a drawdown limit. The fix is (a) a **technical strategy that knows when it's in a bad regime** and steps aside, (b) a **risk layer with veto power** that the strategy cannot override, and (c) an **AI improvement loop** that keeps sharpening the strategy from live and backtested results. The exact strategy is not yet chosen — that's a research output, not an assumption.

## 2. Design principles

These are the load-bearing decisions that shape everything else.

### AI off the hot path

The live trade decision — signal evaluation, position sizing, stop-loss, order placement, the risk governor — is **deterministic Python code**. It runs in microseconds, is fully backtestable and reproducible, and keeps working even if every AI service is down. **AI is never an inline dependency on a live trade.** This avoids the latency, downtime, non-determinism, and token-cost problems of putting an LLM in the critical path, and it's what makes FTMO-style validation possible (you can't backtest an LLM's live judgement; you can backtest rules).

### Technical-first

The core edge is **technical** (price, structure, indicators, regime) — deterministic and testable. Fundamental/macro analysis is treated as an **optional overlay**, not core scope (see the three tiers below).

### Three tiers of scope, by certainty

1. **Core (committed):** deterministic technical engine + hard risk governor. The trader.
2. **Improvement loop (committed):** AI agents develop, backtest, refine, and update the strategy from results. The desk around the trader. _This is the definite go-to path._
3. **Fundamental AI overlay (designed-but-deferred):** an optional AI layer that reads news / macro / real-time market context on higher timeframes and provides a *bias*. Unproven, so it is **not built into core scope** — only a clean seam is reserved for it.

### Design the seam, defer the feature

The technical engine exposes **one optional "context bias" input** (e.g. _normal / cautious / stand-down_). On day one it's hardcoded to `normal`. The fundamental AI overlay can later write to that input — but the engine never depends on it. This keeps the architecture open without overbuilding an unproven idea.

### Shadow-mode first

If/when we test the fundamental overlay, it starts in **logging-only mode**: it records what it _would_ have advised, changing nothing. We then measure whether following it would have helped or hurt. Only with evidence does it graduate logging → soft bias (size/blackout windows) → and even then never a hard live gate. The improvement loop (tier 2) is what evaluates it.

### Fail safe, not open

If any component errors or data is stale, the system flattens or holds — it never guesses.

## 3. Objectives

**Primary objective:** Pass an FTMO 2-Step Challenge and keep the resulting funded account compliant indefinitely.

1. **Pass evaluation** — hit the profit target without breaching any daily-loss, max-loss, or other rule (see §4).
2. **Survive, then earn** — on the funded account, prioritise _not breaching_ over maximising return. Target a smooth equity curve over a spiky one.
3. **Risk discipline as a hard constraint** — the bot must never knowingly place a trade that, if stopped out, could breach the daily-loss or max-loss limit. Enforced in deterministic code.
4. **Fully automated, no human in the live loop** — the deterministic engine trades unattended; AI agents handle research, refinement, and oversight asynchronously. Every decision is logged and explainable after the fact.
5. **Falsifiability** — every component is backtested and forward-tested on demo before it touches an evaluation account. We measure expectancy (avg R per trade), win rate, max drawdown, and rule-breach frequency.

**Timeframes:** intraday is in scope, down to 1m–15m. Short timeframes are allowed (FTMO permits scalping); what's out is **true HFT / latency-arbitrage**. Practical starting floor is 5m/15m, with 1m/3m allowed only once a backtest proves the edge clears spread + commission. Final timeframe is a per-instrument research output.

**Explicit non-goals (for now):** true HFT / latency-arbitrage (feed-error or delay exploitation, ultra-high-speed tools), trading around major scheduled news (FTMO's gap rule), martingale or grid recovery, AI in the live execution path, and any other "forbidden trading practice" under FTMO's terms.

## 4. FTMO constraints (the hard rules we design around)

**Target format: the 2-Step Challenge.** Rules verified against FTMO's official Trading Objectives page (modified May 2026). **There is no time limit** to reach the profit target.

### 2-Step Challenge (selected)

| Rule | FTMO Challenge (Phase 1) | Verification (Phase 2) | Funded account |
| --- | --- | --- | --- |
| Profit target | 10% | 5% | none |
| Max **daily** loss | 5% of initial capital | 5% | 5% |
| Max **overall** loss | 10% (static) | 10% (static) | 10% (static) |
| Min trading days | 4 | 4 | none |
| Time limit | none | none | none |

Daily loss is measured on **equity** (balance + open P/L), recalculated at 00:00 CE(S)T. Max overall loss is static at 90% of initial capital. These two numbers are the design envelope every risk decision must respect.

_(For reference, FTMO also offers a 1-Step format with a tighter 3% daily loss, a trailing overall drawdown, and a "Best Day ≤ 50% of positive-day profit" rule. Not our target, but noted in case we revisit.)_

## 5. Lessons from the previous attempts

What we're deliberately changing this time:

- **Strategy was NNFX** (No Nonsense Forex): a fixed stack of indicators with no regime filter. When the market wasn't trending the way the stack assumed, it bled. **Change:** the technical strategy must self-assess conditions and stand aside in poor regimes — and which strategy we use is decided by research, not picked blind.
- **No hard risk governor** — position sizing and drawdown weren't enforced against the live FTMO limits. **Change:** a deterministic Risk Manager with veto power over every order, sizing each trade so a full stop-out stays comfortably inside the daily budget.
- **Single point of view** — one script made every decision. **Change:** separate strategy, risk, and execution so each can be tested, swapped, and audited independently — and let an AI improvement loop keep refining them.
- **Two $100k accounts failed.** **Change:** validate on the unlimited free trial and a smaller/cheaper challenge before risking another $100k attempt.

## 6. Architecture

Two loops. The **live loop is deterministic** and runs unattended. The **improvement loop is AI-driven** and runs asynchronously (off the hot path).

```
        ══════════════  LIVE LOOP (deterministic, real-time)  ══════════════
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Technical    │──►│ Risk Governor│──►│  Execution   │──►│  MT5 (Python)│
│ Strategy     │   │ (sizing,     │   │  (orders,    │   │  on VPS/local│
│ Engine       │   │  kill-switch,│   │   SL/TP,     │   │  FTMO account│
│ + regime     │   │  FTMO limits)│   │   manage)    │   └──────────────┘
└──────────────┘   └──────────────┘   └──────────────┘
       ▲                                      │
       │ context bias (optional, cached)      │ trades + state
       │ default = "normal"                   ▼
┌─ ─ ─ ─ ─ ─ ─ ─┐                    ┌──────────────────┐
│ Fundamental   │                    │ Trade journal /  │
│ AI overlay    │  ← DEFERRED        │ logs / results   │
│ (shadow mode) │    (designed seam) └──────────────────┘
└─ ─ ─ ─ ─ ─ ─ ─┘                             │
                                              ▼
        ═══════════  IMPROVEMENT LOOP (AI agents, asynchronous)  ═══════════
┌──────────────────────────────────────────────────────────────────────┐
│  Strategy Researcher · Backtest Analyst · Performance Reviewer         │
│  → analyse results, detect drift/overfitting, propose & test refinements│
│  → update strategy params; evaluate whether the fundamental overlay     │
│    earns its place (via shadow-mode evidence)                           │
└──────────────────────────────────────────────────────────────────────┘
```

### Live loop — deterministic (committed)

- **Technical Strategy Engine** — computes the signal and regime; decides entry/exit. The strategy itself is the biggest open question, decided by research (track R1). Built as a swappable component so candidates can be tested against the same risk + execution layer.
- **Risk Governor** — the gatekeeper. Sizes each trade from the SL distance so a full stop stays inside the remaining daily budget; enforces max concurrent risk, daily-loss and max-loss limits, and a daily kill-switch. Pure deterministic code.
- **Execution** — translates an approved trade into MT5 orders (entry, SL, scaled TPs), manages partial exits and break-even moves, confirms fills.
- **Context bias input** — an optional hook (default `normal`) the fundamental overlay can later feed; the engine never depends on it.

### Improvement loop — AI agents (committed)

- **Strategy Researcher** — investigates edges, proposes strategy/parameter changes.
- **Backtest Analyst** — runs and interprets backtests, guards against overfitting, gates promotions on metrics.
- **Performance Reviewer** — journals every trade with rationale, tracks expectancy/drawdown/rule-breach stats, flags drift from backtest expectations.
- (Optional) **Research Analyst for the fundamental overlay** — only if/when tier 3 is explored; sources macro/news/calendar context (e.g. FRED) and runs in shadow mode first.

### Fundamental AI overlay — deferred (designed seam only)

Optional higher-timeframe news/macro bias. Not core scope; reserved as a seam and proven via shadow mode before it gets any influence. See §2.

## 7. Guardrails & risk philosophy

Non-negotiables, enforced in deterministic code:

1. **Per-trade risk cap** — a small fixed fraction of equity (e.g. 0.25–0.5%), sized off the actual SL distance.
2. **Daily-loss kill-switch** — stop opening trades well before the FTMO 5% daily limit (e.g. halt at 60–70% of the budget).
3. **Max-loss buffer** — never let aggregate open risk approach the 10% overall limit; trade smaller as the account nears it.
4. **One source of truth for account state** — the Risk Governor reads live equity/balance from MT5 before sizing, never assumes.
5. **No averaging into losers, no grid, no martingale.**
6. **Server-request budget** — stay well under FTMO's **2,000 requests/day** cap (order opens/modifies/closes). Critical on low timeframes: don't trail/modify every bar; batch or throttle order management.
7. **News-window blackout** — do not open trades around major scheduled news or ≤2h before a 2h+ market close (FTMO gap rule). Enforced deterministically via an economic-calendar check.
8. **Fail safe, not open** — if any component errors or data is stale, the system flattens or holds.

## 8. Instruments — start narrow, build to extend

Start with **one instrument**, prove the full pipeline on it, then extend. The architecture is **instrument-agnostic**: each instrument gets its own strategy parameters/profile (we assume **no single setting fits all pairs**), so adding a market is a config + validation exercise, not a rewrite. Long-term goal: extend to the major FX pairs and eventually crypto.

First-instrument choice is a research output (track R2). Open candidates: **XAUUSD** (Cayden's preference, but high volatility — need to check whether it's too aggressive for FTMO's daily-loss envelope) vs major **USD / GBP / JPY** pairs (commonly cited as more tractable). Decision deferred to research on volatility, spread, session behaviour, and FTMO suitability.

## 9. Decisions: locked vs open

**Locked (this round):**

- **Format:** FTMO 2-Step Challenge.
- **Trading approach:** technical-first; fundamental analysis is an optional, deferred overlay.
- **AI role:** off the live hot path. Live decisions are deterministic Python; AI drives the strategy-improvement loop, with an optional shadow-mode fundamental overlay as a reserved seam.
- **Automation:** fully automated, no human in the live loop.
- **Execution platform:** MT5 driven by a **Python** script, runnable on a VPS or locally, minimising dependence on external data feeds. _(TradingView still researched as a possible signal/data source — see R3 — but MT5+Python is the baseline.)_
- **Language:** Python.
- **Scope:** start with one instrument; design for extension to all FX pairs + crypto, with per-instrument settings.
- **Rollout (host):** **run locally first, move to a VPS later.** The live engine runs on Cayden's **local Windows PC** through dev, demo, free-trial forward-test, and the challenge phase; it migrates to a **London-region Windows VPS** (R7) before any **funded** account, where 24/5 uptime is non-negotiable. MT5's Python package is Windows-only, so the local Windows PC is a true parity environment, not a compromise — the same artifact runs locally and on the VPS, configured by env.
- **Rollout (AI runtime):** **start on the existing Claude Max subscription, move to the API later.** The improvement-loop agents (R5) run as **Claude Desktop / Cowork scheduled tasks** while the loop is low-frequency, so the marginal cost is ≈ the already-paid Max plan instead of per-token API billing. The agent contract (read journal → emit a versioned proposal diff → deterministic backtester is the arbiter → human-approved promotion) is **runtime-agnostic**, so graduating to the **Claude Agent SDK + Batch API** later is a swap of the execution harness, not a redesign. The orchestration layer is built pluggable from day one. See the phased plan in [`docs/specs/00-phase-roadmap.md`](docs/specs/00-phase-roadmap.md).

**Still open (feeds from research):**

1. **Technical signal / strategy** (R1) — what edge, which candidate(s). _The big one._
2. **First instrument** (R2) — XAUUSD vs a major USD/GBP/JPY pair.
3. **Timeframe** (R1/R2) — intraday; 5m/15m starting floor, 1m/3m only if backtest justifies it per instrument.
4. **TradingView's role** (R3) — is a subscription worth it for any feature MT5+Python can't provide?
5. **Backtesting stack & data sources** (R6).
6. **AI agent framework & orchestration** (R5).
7. **Fundamental overlay** (R8) — whether it earns its place, evaluated later via shadow mode.

## 10. Repository structure

```
thetradingbotofcc-forex/
├── README.md                  ← this file (project goals / architecture / principles)
└── docs/
    ├── research/
    │   ├── README.md          ← research roadmap + findings index (R1–R8, all ✅)
    │   ├── R1-signal/ … R8-fundamental/   ← per-track findings.md
    │   └── scripts/
    │       └── self-aware-trend-system.pine   ← reference only (a candidate to evaluate)
    └── specs/                 ← implementation-ready specs (per component)
        ├── README.md          ← spec index + reading order
        ├── 00-phase-roadmap.md
        ├── 01-strategy-engine.md
        ├── 02-risk-governor.md
        ├── 03-execution-mt5.md
        ├── 04-journal-state.md
        ├── 05-backtest-harness.md
        ├── 06-improvement-loop.md
        └── 07-ops-deployment.md
```

_(Structure will grow as components land — e.g. `src/` for the engine and agents, `backtests/`, `journal/`.)_

## 11. Next steps

1. ✅ Project goals, architecture, and design principles defined (this README).
2. ✅ Research roadmap in [`docs/research/`](docs/research/) — all eight tracks (R1–R8) researched and resolved.
3. ✅ Open decisions in §9 resolved from research findings; deployment phasing (local→VPS) and AI runtime phasing (Max→API) added.
4. ▶ **Implementation specs** in [`docs/specs/`](docs/specs/) — deep, per-component, implementation-ready. Start with the [phase roadmap](docs/specs/00-phase-roadmap.md).
5. **Phase A (local + Cowork/Max):** build the journal + state DB, the Risk Governor, the MT5 execution adapter, and the strategy engine; stand up the backtest harness and validate the EURUSD strategy + risk rules on historical data (risk before reward). Forward-test on the FTMO free trial. Improvement-loop agents run as Cowork scheduled tasks.
6. **Phase B (VPS):** migrate the live engine to a London Windows VPS before the funded account; restore live/improvement-box separation.
7. **Phase C (full API):** swap the agent runtime to the Claude Agent SDK + Batch API once cadence/volume justify it.

---

_Rules in §4 reflect FTMO's official Trading Objectives as of May 2026 and can change — re-verify before any live attempt._
