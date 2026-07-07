---
id: 2026-07-07-ml-feature-selection-and-leakage-methodology-triage
name: MLFeatureSelectionAndLeakageMethodologyTriage
family: other
status: research/triage (no trial)
related: [2026-07-06-volatility-regime-and-ml-directional-triage, 2026-07-05-external-falsification-corroboration-triage, 2026-07-04-cross-dependence-and-ml-directional-triage, 2026-07-02-directional-ml-and-vol-forecasting-triage, 2026-06-15-resting-stop-and-market-entry]
sources:
  - https://www.mdpi.com/3042-5042/3/1/6
  - https://arxiv.org/abs/2604.15531
  - https://arxiv.org/abs/2605.23959
  - https://arxiv.org/html/2311.18477v3
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4496917
  - https://www.quantifiedstrategies.com/algorithmic-trading-strategies/
trials_used: 0
verdict: "Daily pass 2026-07-07: 0 of 5 surfaced mechanisms are BOTH differentiable from a recorded failure mode AND directional+testable on EURUSD-M15 OHLCV. Bias-corrected feature selection BFSA (MDPI Metrics 2026, Lansky) = ML feature-selection + model estimation on the live path (pure-spine invariant #1 violation), DAILY horizon (not M15), 14-pair cross-sectional universe (blocked-on-data) — and its own headline is that short-horizon FX predictability is EXAGGERATED by feature selection (corroborates spurious-predictability); Spurious Predictability in Financial ML (arXiv 2604.15531, Nikolopoulos) = falsification-audit methodology, directionless — external corroboration + independently validates our DSR/lockbox/walk-forward gate stack against synthetic nulls; When Alpha Disappears / one-switch decision-time-leakage benchmark (arXiv 2605.23959, Zhang et al.) = methodology, directionless — and its finding that same-day-open execution with post-open bar info inflates backtests is a textbook external restatement of our level-fill / live!=backtest artifact ([[2026-06-15-resting-stop-and-market-entry]], invariant #3); functional-GARCH intraday FX vol-curve forecasting (arXiv 2311.18477) = directionless (Risk-Governor domain, deduped 07-02/04/06); Intraday Stock Predictability Everywhere (SSRN 4496917, Liu-Stentoft) = equities cross-sectional, blocked-on-data (not single-instrument FX). Retail search returned only MA-crossover (trend closed) + chart patterns / London-range break (breakout closed, ~65% double-break chop). No trial; W28 stays 10/10; trials stay 171. 6th consecutive triage-only run — binding constraint remains the EURUSD-M15-only data surface, not idea supply; reinforces the M5 cadence-cut recommendation."
---

# MLFeatureSelectionAndLeakageMethodologyTriage — daily research pass, 2026-07-07

## Hypothesis & market rationale
Daily spec-08 pass. The single-instrument OHLCV idea space was declared **fully closed** on
2026-06-30, externally corroborated on 2026-07-05 (Mesfin 2026, arXiv 2605.04004: 14 OHLCV
intraday signal families on MNQ 5-min, zero clearing strict OOS / |t|≥2 / net-of-cost), and has
now returned triage-only for five straight runs (07-02→07-06). Each pass is adversarial: surface
a mechanism that is BOTH (i) genuinely differentiable from a recorded failure mode and (ii)
directional and implementable on the only data held — EURUSD M15 OHLCV
(`state/parquet/eurusd_m15.parquet`, tick-volume only, continuous across week boundaries). A
directionless (volatility/sizing) signal belongs to the Risk Governor, not the deterministic
entry spine; one needing volume/tick/second-instrument data is `blocked-on-data`; one needing a
non-pure learned model on the live path violates invariant #1.

## Sources
- Lansky, J. (2026), *Bias-Corrected Feature Selection for Short-Horizon FX Trading: Evidence
  from Liquid Currency Pairs*, **Metrics** 3(1):6, MDPI (DOI 10.3390/metrics3010006) — BFSA /
  BFSA-Fixed bias-corrected feature selection in a rolling walk-forward model; 14 liquid FX pairs,
  **daily** horizon (H=1); reports pair Sharpe 1–2, portfolio Sharpe >2 at H=1, collapsing to
  negative at H=2/3.
- Nikolopoulos, S. D. (2026), *Spurious Predictability in Financial Machine Learning*,
  arXiv:2604.15531 — a falsification audit that tests complete predictive workflows against
  synthetic reference classes (zero-predictability nulls, microstructure placebos) and quantifies
  selection-induced performance inflation via an effective-multiplicity magnitude gap.
- Zhang, F., Li, Z., Peng, S., Chen, Y. (2026), *When Alpha Disappears: A One-Switch Benchmark
  for Decision-Time Leakage in Financial Backtests*, arXiv:2605.23959 — toggles one evaluation
  convention at a time around a clean t+1-open reference; finds **same-day-open execution with
  post-open daily-bar information** and centered temporal features cause large, stable inflation.
- *Intraday FX Volatility-Curve Forecasting with Functional GARCH Approaches*, arXiv:2311.18477v3
  — volatility-curve forecasting (directionless).
- Liu, F., Stentoft, L., *Intraday Stock Predictability Everywhere*, SSRN 4496917 — cross-sectional
  intraday predictability across an equity universe.
- QuantifiedStrategies, *5 Algorithmic Trading Strategies 2026*; TradingView / mondfx 15-minute
  scalping scripts — practitioner framing (MA-crossover, chart patterns, London-range break).

The backtester — not the source — is the arbiter. This pass produced no falsifiable,
differentiable, directional EURUSD-M15 candidate, so no trial was spent.

## Relation to prior library work
Each surfaced mechanism dedupes onto a recorded verdict:

1. **Bias-corrected feature selection, BFSA** (MDPI Metrics 2026, Lansky) — **multiple
   disqualifiers.** (a) The mechanism is ML feature selection + repeated model re-estimation
   converted to a directional decision — a learned, non-pure model on the entry path, which
   violates the deterministic-spine **invariant #1** (same ruling as the ML directional
   candidates on 2026-07-02, 2026-07-04, and the LSTM/GBM null on 2026-07-06). (b) It works at a
   **daily** horizon (H=1) and explicitly collapses to negative Sharpe at H=2/3 — it is not an
   M15 intraday mechanism, and its own result is "information decays within one day," reinforcing
   that our 15-minute horizon has even less to extract. (c) Its evidence is a **14-pair
   cross-sectional/portfolio** construction (portfolio Sharpe >2 is the *aggregate* of 14 pairs);
   single-EURUSD is `blocked-on-data` for the cross-sectional universe. (d) Its headline framing —
   short-horizon FX predictability is *"exaggerated by feature selection, causing structural
   directional imbalance"* — is itself a spurious-predictability warning, aligning with source #2,
   not a validated edge to re-implement.
2. **Spurious Predictability in Financial ML** (arXiv 2604.15531, Nikolopoulos) —
   **directionless methodology + corroboration.** Not a strategy: it is a falsification audit.
   Its value here is confirmatory — it formalises exactly why the gate stack we run
   (DSR deflation, held-out lockbox, walk-forward against synthetic nulls) is necessary, and
   shows that "many apparent findings represent methodological artifacts." It gives no entry
   sign; it validates our arbiter, it does not supply a candidate.
3. **When Alpha Disappears / decision-time-leakage one-switch benchmark** (arXiv 2605.23959,
   Zhang et al.) — **directionless methodology + textbook restatement of our own finding.** Also
   not a strategy. Its central empirical result — that **same-day-open execution using post-open
   daily-bar information** produces large, stable, and *selective* backtest inflation — is an
   external, independent restatement of the level-fill artifact we discovered internally
   ([[2026-06-15-resting-stop-and-market-entry]]): the incumbent's +0.391R was a fill the live
   path cannot place (act-before-the-close vs confirm-at-the-close), and both live-faithful fills
   lose the edge. That is precisely "decision-time leakage" (invariant #3, live == backtest).
   Strong corroboration of our fill-realism discipline; no entry candidate.
4. **Functional-GARCH intraday FX vol-curve forecasting** (arXiv 2311.18477) — **directionless.**
   Already ruled Risk-Governor-domain on 2026-07-02/04/06. A volatility forecast gives no entry
   sign; the Risk Governor already owns ATR-floor/ceiling + ATR-percentile sizing
   (`config/default.yaml` regime block). Not a strategy entry.
5. **Intraday Stock Predictability Everywhere** (SSRN 4496917, Liu-Stentoft) —
   **blocked-on-data + wrong asset class.** The predictability is *cross-sectional* across a large
   equity universe (predict each stock intraday from the panel), not a single-instrument
   time-series signal, and it is equities, not FX. Needs a multi-name universe we do not hold —
   same disposition as [[2026-06-07-cross-instrument-confirmation]] and the cross-sectional MR
   candidate ([[2026-07-01-cross-currency-lowvol-reversal]] blocked-on-data).

Retail search (QuantifiedStrategies 2026, TradingView/mondfx 15-min scripts) surfaced only
MA-crossover systems (trend family, closed across raw-drift/vol-conditioning/cross-session/
variance-decomposition) and chart-pattern / "London high-low broken 95.45%" framings — the latter
is simply the ~65% double-break chop already identified as the structural cause of the closed
breakout family ([[2026-06-15-resting-stop-and-market-entry]]).

## Strategy spec
None. No candidate cleared triage, so nothing was implemented. (Per spec 08 §5.8, exit geometry
is pre-registered only for a candidate that reaches the build stage — not reached this pass.)

## Implementation notes
No code written. No edits to `src/`, `state/`, or the live path. `docs/` only (this report +
INDEX row). pytest not re-run: no code changed this pass, and the working tree carries only the
pre-existing, unrelated dirty state flagged in the M5 review (spec 08 changelog 2026-06-21) —
left untouched; my commit is path-scoped to the two doc files.

## Backtest results
None — no trial spent (adversarial triage terminated all five candidates at stage 3). Trial
ledger unchanged (cumulative **171**); W28 budget unchanged (**10/10**).

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|
| — | — | no testable candidate | HEAD v4 (market entry, no live edge) |

## Verdict
**Research/triage only, no trial.** 0 of 5 surfaced mechanisms are simultaneously (i)
differentiable from a recorded failure mode and (ii) directional + testable on EURUSD-M15 OHLCV.
Two are methodology/falsification papers (directionless — one of them, notably, an external
restatement of our own level-fill / decision-time-leakage finding); one is directionless
volatility forecasting (Risk-Governor domain); one is an ML+daily+cross-sectional FX predictor
(invariant #1 + wrong horizon + blocked-on-data, whose own thesis warns of spurious
predictability); one is cross-sectional equity predictability (blocked-on-data, wrong asset).
No proposal filed.

## Lessons
- **Sixth consecutive triage-only run.** The daily pass now reliably surfaces only (a)
  directionless volatility/regime work (Risk-Governor, not an entry), (b) data-blocked
  microstructure/multi-instrument/cross-sectional mechanisms, (c) ML-on-the-live-path violations,
  or (d) re-labelings of closed families. The binding constraint is unambiguously the **data
  surface** (one instrument, one timeframe, tick-volume, continuous feed), not idea supply.
- **The 2026 methodology literature is now independently reconstructing our own invariants.**
  Two of today's five hits are falsification/leakage papers, and the leakage one (arXiv 2605.23959)
  identifies *same-day-open execution with post-open bar information* as the single largest source
  of backtest inflation — the exact mechanism of the level-fill artifact we caught internally
  ([[2026-06-15-resting-stop-and-market-entry]]) and enshrined as invariant #3 (live == backtest).
  When the external literature's cautionary findings map onto our *already-adopted* controls, the
  marginal value of another single-dataset trial is near zero; the controls are the moat.
- **"Predictable at H=1 day, dead at H=2" cuts against, not for, our timeframe.** The strongest
  FX result found this pass (MDPI BFSA) lives at a daily horizon and decays within one day; that
  is direct evidence there is even less exploitable structure at M15 — and it is only reachable
  via a cross-sectional 14-pair construction we cannot build on one instrument anyway.

## Next steps
- **No code, no trial, no schedule/config change this run** (unsupervised; Cayden not present).
- **Reinforce the M5 cadence-cut recommendation** (spec 08 changelog 2026-06-21, awaiting
  Cayden's OK): reduce `ftmo-research-engine` from daily → 3×/week (`30 8 * * *` →
  `30 8 * * 1,3,5`). Six straight triage-only runs make the case decisive: daily cadence on a
  closed single-dataset idea space yields corroboration of the closure, not candidates.
- **The only edge-reviving lever remains a data export** (spec 08 §8 backlog #4): longer EURUSD
  history and/or a second instrument + macro/volume feed. That unblocks the standing queue —
  TrendAlignedORB re-test on the market-fill base, conditional month-end rebalancing, macro-news-
  release momentum, options-flow, M5-trigger ORB, cross-instrument confirmation, and now the
  cross-sectional FX BFSA / low-volume-reversal candidates — none testable on current data.
- Idea queue unchanged; nothing added (every surfaced mechanism dedupes to an existing
  closed/blocked entry or a methodology paper).
