# Research Roadmap

> A backlog of research tracks that feed the open decisions in the [project README](../../README.md) (§9). **Status: all eight tracks (R1–R8) have been researched.** Each track's brief is preserved below for traceability, and its findings live in `docs/research/<track-id>/findings.md`. See the findings index immediately below for the headline recommendations.

## Findings index (completed 2026-06-02)

All findings are evidence-based and cited. Headline recommendations:

| Track | Output | Headline recommendation |
| --- | --- | --- |
| **R1** Signal/strategy | [R1-signal/findings.md](R1-signal/findings.md) | Build a **session-gated London/NY-overlap volatility breakout on 15m EURUSD**, hard-gated by an Efficiency-Ratio + ATR regime filter. **Mine** the reference Pine script's regime ideas (ER, ATR-regime) but **don't port** its laggy SuperTrend-flip entry or unvalidated self-learning. |
| **R2** Instrument | [R2-instrument/findings.md](R2-instrument/findings.md) | Start with **EURUSD** (cheapest/most forgiving). Live data: gold's daily range ≈ **3× the majors** in % terms (~1.8% vs ~0.5–0.6%) with a fat tail; gold is tradeable under the 5% envelope only if sized tiny — defer it to instrument #2/#3. |
| **R3** Platform | [R3-platform/findings.md](R3-platform/findings.md) | **GO** on MT5 + Python (Windows-only, terminal must stay open, needs a watchdog). FTMO permits EAs. **TradingView = no-go** for the hot path; a subscription is only a human chart-review tool. |
| **R4** Risk model | [R4-risk/findings.md](R4-risk/findings.md) | Daily floor = `balance_at_0000_CEST − 0.05×Initial` (verified against FTMO's official page), breach checked on equity. Position size `lots = f·equity / (SL_pips·pip_value·(1+buffer))`, f≈0.35%; kill-switch halts new entries at 60% of the daily budget. 13-item forbidden-practice checklist. |
| **R5** AI loop | [R5-agents/findings.md](R5-agents/findings.md) | Plain Python orchestration; LLM may only **read & propose** (the R6 backtester is the arbiter). Cadence: Performance Reviewer per-session, Strategy Researcher weekly/on-drift, Backtest Analyst event-driven. **Runtime is phased & pluggable: Phase A runs the agents as Claude Desktop / Cowork scheduled tasks on the existing Max plan (~$0 marginal); Phase C swaps to Claude Agent SDK + Batch API (~$5–30/mo) when volume justifies it.** Contract is runtime-agnostic. |
| **R6** Backtest | [R6-backtest/findings.md](R6-backtest/findings.md) | Custom event-driven loop (system of record) + **vectorbt** for sweeps; **Dukascopy tick** (bid/ask) for dev, MT5 feed for final validation. Hard gate: **zero simulated FTMO breaches**; walk-forward + deflated-Sharpe anti-overfitting. |
| **R7** Infra | [R7-infra/findings.md](R7-infra/findings.md) | **Phased host: run on the local Windows PC first** (dev → demo → free-trial → challenge), then migrate to a **London-region Windows VPS** before the funded account (FTMO's engine is in Equinix LD4; no genuine FTMO free VPS exists). NSSM service + watchdog; safe restart reconciles **MT5 as source of truth** to avoid double-trading. Live/improvement-box separation is relaxed in Phase A (shared local box, agent runs scheduled outside trading sessions) and restored at the VPS stage. |
| **R8** Fundamental | [R8-fundamental/findings.md](R8-fundamental/findings.md) | Build the **seam now, defer the feature**. Shadow-mode logs `context_bias` (normal/cautious/stand-down) changing nothing; pre-registered pass/fail bar to graduate to soft bias. Honest read: **probably not worth it** except as a narrow risk-off stand-down detector. |

**Post-research decisions (2026-06-02, owner: Cayden).** Two rollout choices were made after reviewing the findings, and refine R5/R7 without contradicting them:

1. **Host: local-first, VPS later.** Run the live engine on the local Windows PC through dev, demo, free-trial, and the challenge phase; migrate to a London Windows VPS (R7's recommendation) before the funded account. Rationale: a home-PC outage on demo/challenge only costs a retry, whereas on funded capital it is an uninsurable risk — so we pay for the VPS exactly when uptime starts to matter.
2. **AI runtime: Max subscription first, API later.** Run the R5 improvement-loop agents as Claude Desktop / Cowork scheduled tasks on the existing Claude Max plan (marginal cost ≈ the already-paid subscription) while the loop is low-frequency, then graduate to the Claude Agent SDK + Batch API (R5's recommendation) when cadence/volume justify it. The agent contract is runtime-agnostic, so this is a harness swap, not a redesign.

Both are sequenced in [`docs/specs/00-phase-roadmap.md`](../specs/00-phase-roadmap.md) (Phase A → B → C).

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done — _all tracks below are now ✅._

## Scope guardrails (read first)

These come from the project's design principles (README §2) and bound every track:

- **Technical-first.** The core edge is technical. Fundamental/macro is an _optional, deferred overlay_ (track R8), not core scope.
- **AI off the hot path.** The live trade decision is deterministic Python. Do not propose designs that put an LLM inline on a live trade. AI lives in the **improvement loop** (offline/async) and, at most, a shadow-mode advisory overlay.
- **Intraday timeframes are in scope (down to 1m–15m).** Short timeframes / scalping are _allowed_ by FTMO. What's forbidden is **true HFT / latency-arbitrage** (exploiting feed errors or delays, ultra-high-speed tools), exceeding **2,000 server requests/day** per account, and **trading around major scheduled news** (gap rule). Practical steer: 5m/15m is the starting floor; 1m/3m is allowed but must prove in backtest that the edge clears spread + commission before we trust it. Timeframe is a per-instrument research output, not a fixed rule.
- **Evidence-gated.** Anything unproven (especially the fundamental overlay) must be validated in shadow/backtest before it gets any influence.

## How this works

- Each **track (R#)** is a self-contained research assignment with key questions, a concrete deliverable, a priority, and dependencies.
- A research agent picks up a track, does the work, and writes its output to `docs/research/<track-id>/` (e.g. `docs/research/R1-signal/findings.md`).
- Findings should be **evidence-based and cited**, and should end with a clear recommendation that resolves the relevant open decision.
- Keep raw artifacts (scripts, data samples, screenshots) under the track folder.

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done

## Priority & sequencing

The two gating questions are **what to trade** (R2) and **what signal/edge** (R1) — most downstream work depends on them. Execution-platform reality (R3) and the risk model (R4) can proceed in parallel since they're largely independent of strategy choice.

| Order | Track | Why this order |
| --- | --- | --- |
| 1 | **R3** Execution platform reality-check | Cheap to do, de-risks everything; confirms MT5+Python can do what we need before we build on it. |
| 1 | **R4** FTMO rules & risk model | Independent of strategy; defines the envelope all strategies must fit. |
| 2 | **R2** Instrument selection | Narrows the universe; R1 backtests need a target instrument. |
| 2 | **R1** Signal / strategy edge | The core question; partly depends on R2 (per-instrument behaviour). |
| 3 | **R6** Backtesting stack & data | Needed to validate R1 candidates rigorously. |
| 3 | **R5** AI improvement-loop framework | Build-time concern; the committed AI layer. Finalise once signal + execution settled. |
| 4 | **R7** Infrastructure / VPS | Deployment concern; last to lock. |
| 5 | **R8** Fundamental overlay (deferred) | Optional tier-3 experiment; only after core + improvement loop exist. Evaluated via shadow mode. |

---

## R1 — Technical signal / strategy edge  ✅

**Question:** What gives us a real, testable **technical** edge on the chosen instrument, and which strategy (or small ensemble) should we build first? (Technical-first per README §2 — fundamental context is out of scope here; it's R8.)

Key questions:

- What edge are we actually exploiting — trend-following, mean-reversion, breakout, session/time-of-day, volatility regime, or a hybrid? Under what market conditions does each work and fail?
- How do we detect and adapt to **regime** (trending vs ranging vs high-vol), given that the lack of regime awareness was a prior failure?
- Evaluate concrete candidates, including the reference `scripts/self-aware-trend-system.pine` (adaptive SuperTrend + Trend Quality Index) **on its merits** — is its regime measure genuinely predictive, or cosmetic?
- **Which timeframe?** Intraday is in scope (1m–15m). At very low TF (1m/3m) spread + commission dominate — does the edge actually survive costs there, or is 5m/15m the right floor? Decide per instrument with backtest evidence.
- Does the order-management style fit FTMO's **2,000 requests/day** cap? (e.g. trailing every 1m bar across instruments can get expensive in request count.)
- What entry, stop, and exit logic survives realistic costs (spread, commission, slippage) on FTMO conditions?
- What is the realistic expectancy (avg R), win rate, and worst-case drawdown? Does it fit inside the 5% daily / 10% max envelope?

**Deliverable:** A shortlist of 1–3 candidate strategies with rationale, expected market conditions, rough expectancy estimates, and a recommendation for the first one to build. Output: `R1-signal/findings.md`.

**Depends on:** R2 (target instrument), benefits from R4 (risk envelope). **Priority: High.**

## R2 — Instrument selection  ✅

**Question:** Which single instrument do we start with, and why?

Key questions:

- **XAUUSD (gold):** Cayden's preference. Quantify its volatility (ATR, typical daily range) and spread vs the majors. Is its daily range too large to size safely under a 5% daily-loss limit, or is it manageable with smaller position sizing? Any FTMO-specific quirks (leverage, swap, weekend gaps)?
- **Majors (USD / GBP / JPY pairs):** the claim that "GBP/USD/JPY pairs are mostly profitable" — is that supported, or folklore? Compare EURUSD, GBPUSD, USDJPY, GBPJPY etc. on liquidity, spread, trendiness, and session behaviour.
- Which instrument best matches a beginner-safe risk profile **and** a tractable edge for R1?
- How much does behaviour differ across instruments — confirming the "no single setting fits all pairs" assumption and informing the per-instrument config design.

**Deliverable:** A ranked comparison table (volatility, spread, session, FTMO suitability, edge tractability) and a clear pick for instrument #1, plus notes on what changes when we add the next instrument. Output: `R2-instrument/findings.md`.

**Depends on:** none (can start immediately). **Priority: High.**

## R3 — Execution platform reality-check  ✅

**Question:** Can MT5 + Python do everything we need on an FTMO account, and what (if anything) is TradingView genuinely better at?

Key questions:

- **MT5 Python (`MetaTrader5` package):** confirm it can connect to an FTMO MT5 account, read live equity/balance/positions, place/modify/close orders with SL/TP, and run reliably headless on a VPS. Known limitations (Windows-only? terminal must stay open? rate limits?).
- **FTMO specifics:** which MT5 build/broker server, leverage, order types allowed, and any execution constraints under their terms.
- **TradingView:** what would a paid subscription actually buy us — better charting/alerts, Pine signals via webhook, data we can't get from MT5? Is webhook→bridge worth the added moving part vs computing signals natively in Python? When (if ever) is TV the right signal source?
- **cTrader (cBot):** brief comparison given prior experience — any advantage over MT5+Python worth reconsidering?

**Deliverable:** A go/no-go on MT5+Python as the execution baseline, a concrete recommendation on TradingView's role (and whether a subscription is justified), and a list of platform constraints the design must respect. Output: `R3-platform/findings.md`.

**Depends on:** none. **Priority: High (do first — cheap, de-risks the build).**

## R4 — FTMO rules & risk model  ✅

**Question:** Exactly how do the FTMO limits compute, and what position-sizing / kill-switch math keeps us safe with margin?

Key questions:

- Precise mechanics of the 5% daily loss (equity-based, 00:00 CE(S)T reset) and 10% static max loss — worked examples, including how open P/L counts.
- FTMO's **forbidden trading practices** — what must the bot never do? Confirmed items to encode as hard checks: no feed-error/latency exploitation; **≤ 2,000 server requests/day** (order open/modify/close); **no trades around major scheduled news or ≤2h before a 2h+ market close** (gap rule); consistent position sizing (no wildly larger/smaller trades); no hedging/opposing correlated positions to game the Best Day Rule.
- **Request-budget design** (important for low timeframes): how do we count and throttle order-management actions to stay under 2,000/day across all instruments? What's a safe trailing/modify cadence?
- **News-blackout design:** which calendar source feeds a deterministic "is major news imminent?" check, and what blackout window before/after?
- Position-sizing formula: given equity, SL distance, and remaining daily budget, how many lots? What safety margin (kill-switch threshold) keeps us clear of a breach including slippage and spread?
- Max concurrent open risk, max trades/day, behaviour around the 00:00 reset, and weekend/gap handling.

**Deliverable:** A precise risk-model spec (formulas + thresholds) the Risk Manager agent will implement, plus a checklist of forbidden practices. Output: `R4-risk/findings.md`.

**Depends on:** none. **Priority: High.**

## R5 — AI improvement-loop framework & orchestration  ✅

**Question:** How do we build the AI agents that develop, test, and continuously improve the strategy — strictly **off the live hot path** (README §2)?

Two distinct loops to keep separate:

- **Live loop (deterministic, NOT this track):** real-time signal → risk → execution in plain Python. No LLM inline. This track must not design AI into it.
- **Improvement loop (this track):** asynchronous AI agents — Strategy Researcher, Backtest Analyst, Performance Reviewer — that read results/journals, detect drift and overfitting, propose and test refinements, and update strategy params.

Key questions:

- Agent framework choice (plain Python + LLM calls, or a framework) for an **offline/scheduled** improvement loop with state — not a real-time trading loop.
- Where exactly is the deterministic-vs-LLM boundary? Confirm the live path stays LLM-free and the AI only reads logs / proposes changes that a human or a gated process applies.
- Cadence: when does the improvement loop run (after each session / daily / weekly)? How are proposed changes validated (R6) before going live?
- Journaling/logging design so every live decision is auditable and so the AI has clean inputs to learn from.
- Token-cost budgeting: roughly how often are LLM calls made, and what bounds the spend?

**Deliverable:** An architecture spec for the improvement-loop agent layer — components, cadence, framework choice, the deterministic-vs-LLM boundary, and how refinements get validated and promoted. Output: `R5-agents/findings.md`.

**Depends on:** R1, R3, R6. **Priority: Medium.**

## R6 — Backtesting stack & data  ✅

**Question:** How do we validate a strategy rigorously before risking an account?

Key questions:

- Backtesting tooling for Python (e.g. backtrader, vectorbt, custom) — which fits our needs and can model spread/commission/slippage realistically?
- Historical data sources for FX majors and XAUUSD at the needed timeframe — quality, cost, granularity (tick vs minute).
- Metrics and acceptance gates: expectancy, win rate, max drawdown, Sharpe/Sortino, rule-breach simulation. Walk-forward / out-of-sample methodology to avoid overfitting.
- How to simulate FTMO rules in the backtest (daily-loss, max-loss) so we know a strategy would have survived.

**Deliverable:** A recommended backtesting stack + data source(s), and a written validation methodology with explicit pass/fail gates. Output: `R6-backtest/findings.md`.

**Depends on:** R1 (what we're testing). **Priority: Medium.**

## R7 — Infrastructure / VPS & ops  ✅

**Question:** Where and how does this run reliably, unattended?

Key questions:

- VPS options for hosting MT5 + the Python stack (provider, OS, cost, latency to FTMO's server, uptime).
- Process supervision, auto-restart, and monitoring/alerting (so a crash or stale-data condition is caught fast).
- Secrets/credentials handling, backups of journal/state, and a safe restart procedure that doesn't double-trade.
- Local-dev vs VPS-prod parity.

**Deliverable:** A deployment recommendation (host, supervision, monitoring, secrets) and an ops runbook outline. Output: `R7-infra/findings.md`.

**Depends on:** R3, R5. **Priority: Low (until closer to live).**

## R8 — Fundamental AI overlay (deferred experiment)  ✅

**Question:** Does an AI-driven fundamental/macro overlay on higher timeframes actually improve results — enough to earn any influence over trades? (Tier-3, designed-but-deferred per README §2. Do **not** build this into core scope.)

This track is gated: only start it once the deterministic core, the improvement loop (R5), and the journal exist. The whole point is to answer "is it helpful?" with evidence rather than assumption.

Key questions:

- What context could the overlay provide on higher timeframes — economic calendar / high-impact news blackout windows, central-bank stance, risk-on/off bias? Data sources (e.g. FRED, calendar, news feeds) and how they're summarised.
- **Shadow-mode design:** how does the overlay log what it _would_ have advised (e.g. _normal / cautious / stand-down_) into the journal **without affecting any trade**?
- **Evaluation:** over a meaningful sample, would following its advice have improved expectancy / reduced drawdown / avoided rule breaches? What's the acceptance bar to graduate it from logging → soft bias (size / blackout) ?
- The **seam contract:** confirm it writes only to the engine's optional `context bias` input and can be disabled with zero effect on the live path.

**Deliverable:** A shadow-mode design + an evaluation methodology with an explicit pass/fail bar, and (later) a recommendation on whether the overlay earns any influence. Output: `R8-fundamental/findings.md`.

**Depends on:** core engine + R5 + R6. **Priority: Low / deferred.**

---

## Open questions parking lot

Things to capture as they come up but not yet assigned to a track:

- Scaling plan / payout mechanics once funded (affects long-term targets, not the build).
- Multi-instrument portfolio risk once we extend beyond instrument #1.
- Crypto extension specifics (24/7 markets, different volatility, different broker).
