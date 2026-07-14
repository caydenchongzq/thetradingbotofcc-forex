---
id: 2026-07-13-overnight-reversal-and-transformer-fx-triage
name: OvernightReversalAndTransformerFXTriage
family: other
status: research/triage (no trial)
related: [2026-06-23-end-of-day-reversal, 2026-06-24-weekend-gap-fill, 2026-06-30-twenty-day-turtle-soup, 2026-07-01-signed-semivariance-momentum, 2026-07-05-external-falsification-corroboration-triage, 2026-07-08-microstructural-trend-demise-corroboration-triage, 2026-07-12-optimization-methodology-and-ml-directional-triage]
sources: ["https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/c953a0e6-e93e-4bf7-b839-45a90cedced4.pdf", "https://arxiv.org/pdf/2512.12727", "https://arxiv.org/pdf/2508.14784", "https://arxiv.org/abs/2605.04004", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10490999/", "https://arxiv.org/pdf/2409.04471"]
trials_used: 0
verdict: "Daily pass 2026-07-13: 5 candidates, 0 differentiable+directional+OHLCV-M15-testable. Overnight-Intraday Reversal Everywhere (Della Corte-Kosowski) = MR-family fade needing a clean daily close/overnight non-trading gap the continuous M15 feed lacks — dedupes to end-of-day-reversal (blocked-on-data) + MR 7/7 closed; EXFormer transformer FX returns (arXiv 2512.12727) = ML on the decision path → pure-spine invariant #1; graph-learning FX statistical arbitrage (arXiv 2508.14784) = cross-sectional multi-currency → blocked-on-data + invariant #1; MNQ OHLCV falsification (arXiv 2605.04004) = already our external corroboration [[2026-07-05-external-falsification-corroboration-triage]]; Omega momentum/reversal (PLOS One 2023) = trend + MR families closed on EURUSD. No trial; W29 stays 10/10; trials stay 171. 10th consecutive triage-only run — binding constraint is the EURUSD-M15-only data surface, not idea supply."
---

# OvernightReversalAndTransformerFXTriage — daily research pass 2026-07-13

## Hypothesis & market rationale
Daily spec-08 pass. Budget is a FRESH W29 (Mon 2026-07-13 → ISO 2026-W29, weekday 1),
`trial_budget_per_week = 10`, 0 spent this week, cumulative trials = 171. So the question was
purely whether the online search surfaced a candidate that is (a) directional, (b) testable on
the EURUSD-M15 parquet alone, and (c) differentiated from a closed library family or a prior
rejection's failure mode (§4.3). It did not. This report records the triage so future runs
don't re-walk the same five candidates.

## Sources
- Della Corte & Kosowski, *Overnight-Intraday Reversal Everywhere* —
  https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/c953a0e6-e93e-4bf7-b839-45a90cedced4.pdf
- *EXFormer: A Multi-Scale Trend-Aware Transformer with Dynamic Variable Selection for FX
  Returns Prediction*, arXiv 2512.12727 — https://arxiv.org/pdf/2512.12727
- *Graph Learning for Foreign Exchange Rate Prediction and Statistical Arbitrage*,
  arXiv 2508.14784 — https://arxiv.org/pdf/2508.14784
- Mesfin, *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic
  Falsification Study*, arXiv 2605.04004 — https://arxiv.org/abs/2605.04004
- *Extending the Omega model with momentum and reversal strategies to intraday trading*,
  PLOS One 2023 — https://pmc.ncbi.nlm.nih.gov/articles/PMC10490999/
- *Predicting Foreign Exchange EUR/USD direction using machine learning*, arXiv 2409.04471 —
  https://arxiv.org/pdf/2409.04471

## Relation to prior library work — the five candidates, each disqualified

**1. Overnight-Intraday Reversal Everywhere (Della Corte & Kosowski) — MR family, blocked-on-data anchor.**
The paper documents that the intraday (open→close) return reverts the prior overnight
(close→open) return "everywhere," FX included. The mechanism needs two things this data surface
cannot supply: a clean daily *close/auction* to anchor the overnight leg, and a genuine
non-trading *overnight gap* to carry the inventory-unwind signal. Our M15 feed is **continuous
across the day and the week** — [[2026-06-24-weekend-gap-fill]] measured max boundary gap 0.7p
(mean 0.11p) over 125 weeks; 24h EURUSD has no daily close/open discontinuity to reverse.
Dedupes directly to [[2026-06-23-end-of-day-reversal]] (blocked-on-data for exactly this
missing-close-anchor reason). And even if a synthetic session-close anchor were imposed, the
**mean-reversion fade family is 7/7 closed across every anchor tried** (Asian-1R, Asian-2R,
VWAP-stretch, session-OR-false-break, ECB-fix, high-ER-thrust, 20-day-turtle-soup —
[[2026-06-30-twenty-day-turtle-soup]]): EURUSD M15 intraday extension continues > reverts under
every gate. Would need a real close-to-open FX feed **and** a positive a-priori reversal-sign
probe before it could differentiate. Blocked-on-data; no trial.

**2. EXFormer transformer FX returns prediction (arXiv 2512.12727) — pure-spine invariant #1 violation.**
A multi-scale trend-aware transformer with dynamic variable selection that predicts FX returns.
Putting a learned neural predictor on the entry decision violates CLAUDE.md **invariant #1**
(the spine must be a pure, deterministic function of `(bars, now, context_bias, calendar)` —
no learned model inline on a live trade, cf. invariant #5). Its "trend-aware" target is also in
the **trend/momentum family that is closed** on EURUSD M15 across raw-drift, vol-conditioning,
cross-session, and variance-decomposition ([[2026-07-01-signed-semivariance-momentum]]). Same
disqualification as every prior ML-directional candidate (07-04, 07-06, 07-07, 07-09, 07-12).

**3. Graph-learning FX prediction & statistical arbitrage (arXiv 2508.14784) — blocked-on-data + invariant #1.**
Learns a graph over a **multi-currency universe** for cross-sectional statistical arbitrage.
Inherently needs instruments beyond the single EURUSD-M15 parquet (dedupes to
[[2026-06-07-cross-instrument-confirmation]], blocked-on-data) and puts a learned model on the
decision path (invariant #1). Doubly disqualified.

**4. MNQ OHLCV falsification study (arXiv 2605.04004) — already our external corroboration.**
Same paper the library adopted on 2026-07-05 as the independent, different-instrument
confirmation that the OHLCV intraday idea space is structurally (not incidentally) exhausted
([[2026-07-05-external-falsification-corroboration-triage]]). Re-surfacing it is not a new idea;
it reaffirms the closure. No action.

**5. Omega-model momentum/reversal intraday (PLOS One 2023) — trend + MR families closed.**
An Omega-ratio-optimised overlay on momentum and reversal signals, demonstrated on S&P 500 /
NASDAQ-100 constituents. Both underlying signal families are closed on EURUSD M15 (trend
[[2026-07-01-signed-semivariance-momentum]]; MR 7/7 [[2026-06-30-twenty-day-turtle-soup]]); the
Omega layer is a position-sizing / objective-function wrapper (Risk-Governor / optimizer
domain), not a new directional signal. Already deduped in the 07-12 pass (its crypto cousin).
No differentiation from the closed families.

## Strategy spec
N/A — no candidate selected for build. Nothing cleared triage.

## Implementation notes
No code, no indicator, no registry entry, no tests, no writes to `state/` or the live path.
Repo left green (only this report + INDEX.md line added, path-scoped commit). Pre-existing
uncommitted working-tree changes (AGENTS.md, CLAUDE.md, gates.py, staged 07-08 report,
untracked promotion briefs, wrapper log) are Cayden's / other agents' and were NOT touched —
the commit is scoped to my two files only (the `git commit -- <paths>` gotcha noted in prior
runs still applies).

## Backtest results
None. No trial spent (trials remain 171; W29 budget remains 10/10).

## Verdict
**Triage-only, no trial.** 0 of 5 candidates are simultaneously directional, OHLCV-M15-testable,
and differentiated from a closed family or prior failure mode. No proposal filed.

## Lessons
- **10th consecutive triage-only run.** The binding constraint remains the single-instrument,
  single-timeframe (EURUSD-M15) data surface — not idea supply. Every genuinely new mechanism
  the 2026 literature offers is either (a) directionless/vol-forecasting (Risk-Governor domain),
  (b) ML on the decision path (invariant #1), (c) cross-sectional/multi-currency/tick/news
  (blocked-on-data), or (d) a re-label of a family already closed on this data.
- **The overnight-intraday reversal is the cleanest "so-close-but-blocked" candidate this month:**
  a well-cited, cross-asset, FX-inclusive reversal effect — but it needs a daily close/open
  discontinuity the continuous 24h M15 feed structurally lacks. It joins end-of-day-reversal and
  month-end-conditional as **high-value-once-a-richer-feed-exists** items. It is NOT a longer
  EURUSD-M15 history lever (per [[2026-07-08-microstructural-trend-demise-corroboration-triage]],
  a longer M15 directional history will not revive closed directional families); it needs a
  *different feed shape* (true session-close-anchored bars), not more of the same.
- Reinforces the standing recommendation: **cut the research cadence** (daily → ~weekly) until a
  data-export lever lands (2nd instrument / interest-rate / news-calendar / real overnight-gap
  feed). The daily cadence is now spending a session to re-confirm a closed frontier.

## Next steps
- No build. No proposal.
- Priority data-export levers, unchanged and reinforced: (1) 2nd instrument + rate/swap data →
  unblocks CurrencyCarryXSMomentum, CrossInstrumentConfirmation, graph/statistical-arbitrage;
  (2) macro news-calendar timestamps → MacroNewsReleaseMomentum; (3) equity daily returns →
  MonthEndConditionalRebalancing; (4) **NEW: a true daily-close/overnight-gap FX feed** →
  Overnight-Intraday Reversal + EndOfDayReversal.
- Await Cayden on the cadence-cut recommendation (now standing across 07-01..07-12 reviews).
