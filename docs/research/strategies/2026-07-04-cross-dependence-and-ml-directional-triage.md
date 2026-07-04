---
id: 2026-07-04-cross-dependence-and-ml-directional-triage
name: CrossDependenceAndMLDirectionalTriage
family: other
status: research/triage (no trial)
related: [2026-06-07-cross-instrument-confirmation, 2026-07-02-directional-ml-and-vol-forecasting-triage, 2026-07-03-candlestick-and-volatility-timing-triage, 2026-07-01-signed-semivariance-momentum]
sources:
  - https://arxiv.org/html/2311.18477v3
  - https://www.researchgate.net/publication/395011327_Directional_forecasting_for_eight_forex_pairs_against_the_US_dollar_using_machine_learning_techniques
  - https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10490999/
  - https://www.sciencedirect.com/science/article/pii/S0261560625001330
  - https://www.buildalpha.com/opening-range-breakout/
  - https://www.stocktitan.net/articles/volatility-clustering-explained
trials_used: 0
verdict: "Daily pass 2026-07-04: every mechanism surfaced is (a) directionless volatility forecasting → Risk-Governor domain, (b) an ML directional model → violates the pure-spine invariant #1, (c) a cross-pair/cross-market cross-dependence filter → blocked-on-data (dedupes to CrossInstrumentConfirmation), or (d) momentum/reversal → trend & MR families already closed. No differentiable OHLCV-testable candidate. No trial; W27 stays 10/10; trials stay 171. 3rd consecutive triage-only run — reinforces the cadence-cut recommendation."
---

# CrossDependenceAndMLDirectionalTriage — daily research pass, 2026-07-04

## Hypothesis & market rationale
Daily spec-08 pass. With the OHLCV single-instrument idea space marked fully closed on
2026-06-30 (breakout across all level defs, mean-reversion 7/7, trend/momentum across
raw-drift/vol-conditioning/cross-session/variance-decomposition, seasonality & calendar,
exit-model 0/5, filter family floor-bound), the object of a daily pass is now to test the
*closure* adversarially: search current literature and community catalogs for a mechanism
that is BOTH (i) genuinely differentiable from a recorded failure mode and (ii) implementable
& testable on the only data we have (EURUSD M15 OHLCV parquet). Anything that fails either
test is triaged without spending a trial.

## Sources
- **Functional-GARCH intraday FX volatility-curve forecasting** — arXiv 2311.18477v3 (updated
  Sep 2025): intraday return curves are serially uncorrelated but show long-range conditional
  heteroskedasticity; USD/EUR & USD/GBP intraday-return curves are *cross-dependent*.
- **Directional forecasting for eight FX pairs vs USD via ML** — ResearchGate 395011327 (2025):
  RF/XGBoost directional classifiers on FX pairs.
- **Extending the Omega model with momentum and reversal strategies to intraday trading** —
  PMC10490999: intraday momentum + reversal rebalancing, net-of-cost.
- **Intraday volatility connectedness on the FX market: the role of uncertainty** —
  ScienceDirect S0261560625001330 (2025): volatility spillover/connectedness driven by
  cross-market uncertainty.
- Opening-range-breakout catalogs (BuildAlpha, QuantifiedStrategies, LiteFinance) and
  volatility-clustering practitioner writeups — surveyed for any non-closed mechanism.

## Relation to prior library work — candidate-by-candidate triage
1. **Functional-GARCH / realized-range volatility forecasting (arXiv 2311.18477v3).**
   The estimand is the intraday *volatility curve*, not a return sign. It forecasts
   magnitude, not direction — the Risk-Governor's domain (which already sizes on ATR/ER),
   not an entry signal. Same exclusion as [[2026-07-02-directional-ml-and-vol-forecasting-triage]]
   and [[2026-07-03-candlestick-and-volatility-timing-triage]]. The paper's own finding that
   the isolated intraday return series is *serially uncorrelated* independently corroborates
   the closed trend/momentum family ([[2026-07-01-signed-semivariance-momentum]]). **DISCARD —
   directionless.**
2. **Cross-pair intraday return-curve cross-dependence (USD/EUR ↔ USD/GBP).** The one novel
   directional angle: use a correlated pair's realized intraday move as a confirming filter on
   the EURUSD entry. But it is the exact mechanism already queued as
   [[2026-06-07-cross-instrument-confirmation]] (**blocked-on-data**): the parquet holds only
   EURUSD M15 — no GBPUSD/second-instrument series exists to compute the cross-dependence.
   **DEDUPE → blocked-on-data;** revives with a multi-instrument export (§8 backlog #4).
3. **ML directional forecasting for 8 FX pairs (RF/XGBoost, ResearchGate 395011327).**
   Directly violates **hard invariant #1** (the strategy spine must be a *pure, deterministic*
   function of (bars, now, context_bias, calendar) — no learned black-box inline on a live
   trade; AI is offline-propose-only). A tree ensemble as the entry decision is non-pure by
   construction. Same exclusion recorded [[2026-07-02-directional-ml-and-vol-forecasting-triage]].
   **DISCARD — invariant-violating.**
4. **Omega-model intraday momentum + reversal (PMC10490999).** Two legs, both closed:
   momentum = the trend family (raw-drift, vol-conditioned, cross-session, semivariance — all
   closed); reversal = the mean-reversion fade family (7/7 closed across anchors). The Omega
   objective is a portfolio-construction/position-sizing wrapper over the same two directional
   signals — it does not supply a new signal. No differentiation from the recorded failure
   modes. **DISCARD — closed families.**
5. **Intraday volatility connectedness / uncertainty (ScienceDirect S0261560625001330).**
   Connectedness is a directionless spillover measure and needs cross-market uncertainty
   proxies (e.g. VIX, cross-pair vols) not present in the parquet. **DISCARD — directionless +
   blocked-on-data;** overlaps the Risk-Governor domain.

Dedup result: 0 of 5 are both differentiable and OHLCV-testable. One (cross-pair confirmation)
is a legitimate future direction but already queued as blocked-on-data; the rest are directionless,
invariant-violating, or in closed families.

## Strategy spec
None built — nothing cleared triage. (Per spec 08 §4.3, a candidate that reduces to a recorded
failure mode without stated differentiation is discarded, not tested; a data-blocked candidate is
queued, not tested.)

## Implementation notes
No `src/` changes. No `state/` writes. No live-path touch. No trial ledger entry. pytest
suite untouched (green from prior run; no code edited this pass).

## Backtest results
None — no candidate reached a probe or backtest. Trial budget unspent.

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|
| (no candidate tested) | — | — | HEAD v4 (unchanged) |

## Verdict
**Research/triage only — no trial.** No differentiable, OHLCV-testable candidate exists in
today's search surface. Cumulative trials stay **171**; W27 budget stays **10/10** (0 spent).
This is the **3rd consecutive triage-only run** (07-02, 07-03, 07-04), each returning only
closed-family, directionless, invariant-violating, or data-blocked mechanisms.

## Lessons
- The closure is holding under adversarial search: three independent daily searches now return
  the same four buckets — (a) volatility forecasting (directionless, Risk-Governor), (b) ML
  directional (invariant #1), (c) cross-instrument/cross-market (blocked-on-data), (d)
  momentum/reversal (closed). The literature itself corroborates the trend closure: the
  serially-uncorrelated intraday return curve (arXiv 2311.18477v3) is the academic statement
  of what [[2026-07-01-signed-semivariance-momentum]] found empirically.
- The single genuinely-new directional idea each pass now surfaces (here: cross-pair
  confirmation) is invariably **data-blocked**, not idea-blocked. The binding constraint is no
  longer hypothesis supply — it is the EURUSD-M15-only dataset. Continued daily runs on the
  current data have a near-zero expected yield.
- Process note: keep discarding directionless volatility-forecasting hits fast. They recur every
  pass (functional GARCH, realized-range clustering, connectedness) because "intraday FX" search
  terms surface the well-funded vol-forecasting literature; none of it is an entry signal, so
  none of it is in scope for the deterministic entry spine.

## Next steps
- **Unblocking action for Cayden (the real lever):** a longer-history and/or second-instrument
  (e.g. GBPUSD) M15 export. It would simultaneously (i) revive the strongest shelved candidate
  TrendAlignedORB and the incumbent-filter queue (both 200-trade-floor-bound on current history,
  must be re-based on the **market-fill** incumbent base −0.024R, not the level-fill artifact),
  and (ii) unblock CrossInstrumentConfirmation / cross-pair confirmation, CurrencyCarryXSMomentum,
  MacroNewsReleaseMomentum, MonthEndConditionalRebalancing, and CrossCurrencyLowVolumeReversal.
- **Cadence:** 3rd consecutive zero-yield triage run reinforces the standing M5 recommendation to
  cut the schedule daily → 3×/week (Mon/Wed/Fri) until a data export lands. Awaiting Cayden's OK;
  not applied here.
- No new idea-queue entries this pass (all surfaced ideas dedupe to existing queue rows).
