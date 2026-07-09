---
id: 2026-07-09-causal-ml-and-vol-of-vol-directional-triage
name: CausalMLAndVolOfVolDirectionalTriage
family: other
status: idea
related: [2026-07-08-microstructural-trend-demise-corroboration-triage, 2026-07-05-external-falsification-corroboration-triage, 2026-07-02-directional-ml-and-vol-forecasting-triage, 2026-06-11-breakout-retest, 2026-06-22-volume-confirmed-orb]
sources:
  - https://arxiv.org/html/2507.09347v1
  - https://arxiv.org/abs/2606.00060
  - https://arxiv.org/pdf/2403.02591
  - https://www.quantifiedstrategies.com/opening-range-breakout-strategy/
  - https://www.stocktitan.net/articles/volatility-clustering-explained
trials_used: 0
verdict: "Daily pass 2026-07-09: 5 candidates surveyed, 0 differentiable+directional+OHLCV-M15-testable. (1) Volatility+causal-inference directional framework (arXiv 2507.09347) = Granger/causal-inference ML on a cross-asset equity universe → violates pure-spine invariant #1 AND blocked-on-data. (2) ML hourly-return net-of-cost walk-forward (arXiv 2606.00060 + the 70k-hourly XGBoost/LSTM/iTransformer study) = invariant #1; its own finding (gross profitable, net eroded by costs on EUR/USD 1min-1h) is a FRESH external corroboration of our cost-erosion closure. (3) HARQ realized-quarticity vol-of-vol (arXiv 2403.02591) = directionless volatility forecasting → Risk-Governor domain, dedupes to the closed functional-GARCH family. (4) ORB retest + volatility filter (QuantifiedStrategies) = breakout family closed + retest already tested-rejected [[2026-06-11-breakout-retest]] + subtractive-filter wall [[2026-06-22-volume-confirmed-orb]]. (5) First-hour range → day-range expansion / volatility clustering = directionless magnitude predictor (Risk-Governor), incumbent already ATR-gates. No trial; W28 stays 10/10; trials stay 171. 8th consecutive triage-only run — binding constraint remains the EURUSD-M15-only data surface, not idea supply."
---

# CausalMLAndVolOfVolDirectionalTriage — daily research pass 2026-07-09

## Hypothesis & market rationale
Daily scan of the curated sources (`SOURCES.md`) + arXiv q-fin.TR/CP (2026 listings) +
practitioner catalogs for a **differentiable, directional, OHLCV-testable-on-EURUSD-M15**
candidate that is not already closed by a prior library verdict and does not violate a hard
invariant (pure spine #1; live-fillable fill #3). As with the prior seven runs, the binding
question is not "is there a new idea?" (there always is) but "is there one that is (a)
directional, (b) testable on the single `state/parquet/eurusd_m15.parquet`, and (c) not a
rename of an already-closed family?"

## Sources
- **"A Framework for Predictive Directional Trading Based on Volatility and Causal
  Inference"** — arXiv:2507.09347v1 (q-fin, Jul 2025). Builds a directional-trading signal
  on a **cross-asset equity universe** using Granger-causality / causal-inference algorithms
  over inter-asset volatility relationships. (55 mentions of "causal", 8 of "stocks", 6 of
  "Granger" in the fetched text; single "intraday" mention.)
- **"Machine Learning-Based Bitcoin Trading Under Transaction Costs: Evidence From
  Walk-Forward Forecasting"** — arXiv:2606.00060, plus the companion ~70,000-hourly-obs
  (2018–2026) study evaluating XGBoost / LSTM / iTransformer in a 27-fold walk-forward
  protocol *net of transaction costs*. Central empirical finding restated below.
- **"Matrix-based Prediction Approach for Intraday Instantaneous Volatility Vector"** —
  arXiv:2403.02591, representative of the HARQ / realized-quarticity ("vol-of-vol")
  forecasting family; forecasts the *level* of volatility, not direction.
- **QuantifiedStrategies — Opening Range Breakout Strategy (backtest)** —
  https://www.quantifiedstrategies.com/opening-range-breakout-strategy/ , plus the
  practitioner consensus (LiteFinance, ChartingLens, Trade That Swing) that ORB needs a
  retest and/or an ATR/ADR volatility filter to suppress false breaks.
- **Volatility Clustering (StockTitan explainer)** —
  https://www.stocktitan.net/articles/volatility-clustering-explained : daily range
  expansion begets range expansion; the first-hour range as a predictor of the day's range.

The backtester — not any source — is the arbiter. None reached the backtester this run
(reasons below).

## Relation to prior library work
Every surveyed mechanism maps onto an existing library verdict or a hard invariant:

1. **Volatility + causal-inference directional framework (arXiv 2507.09347).** Two
   independent disqualifiers: (a) the signal is a learned Granger/causal-inference model on
   the live decision path → violates **invariant #1** (deterministic, pure spine; no learned
   inline model), the same wall that closed every ML-directional candidate on 07-02/04/05/06;
   (b) it is *inter-asset* (a cross-sectional equity universe) → **blocked-on-data** on the
   EURUSD-M15-only parquet, dedupes to [[2026-06-07-cross-instrument-confirmation]]. Discard.

2. **ML hourly-return net-of-cost walk-forward (arXiv 2606.00060 + the 70k-hourly study).**
   Same invariant #1 violation (XGBoost/LSTM/iTransformer on the decision path). But its
   *finding* is a fresh external corroboration of our own closure: gross returns on the
   training set are "solidly profitable," while OOS test performance is "considerably worse"
   and profitability is "eroded in the presence of transaction costs" on **EUR/USD and
   GBP/USD at 1-minute-to-1-hour frequencies** — the exact cost-erosion mechanism behind the
   4× live-faithful breakout closure and [[2026-07-05-external-falsification-corroboration-triage]].
   A *third* independent instrument/method (after MNQ 5-min and ~100 futures) reaching the
   "gross edge does not survive cost + OOS" verdict on intraday FX. Discard as a candidate;
   logged as corroboration.

3. **HARQ realized-quarticity vol-of-vol (arXiv 2403.02591).** Forecasts the *magnitude* of
   intraday volatility (a U-shaped-corrected vol level), not a return sign → **directionless**,
   Risk-Governor domain, dedupes to the functional-GARCH family already closed as
   directionless on 07-02/04/06/07. The incumbent already gates on ATR-floor/ceiling +
   ATR-percentile + ER, so a smoother vol-of-vol state carries no incremental *directional*
   information to identify (same argument that closed [[2026-06-22-garch-vol-regime-gate]]).
   Discard.

4. **ORB retest + volatility filter (QuantifiedStrategies + practitioner consensus).** The
   retest-entry variant is already **tested-rejected**: [[2026-06-11-breakout-retest]]
   (BreakoutRetestER) found the break→retest→resume filter is *anti-selective* — it discards
   the immediate-continuation winners (win 73%→43%, PF 1.99→0.70) and halves the trade count
   below the floor. The ATR/ADR "skip narrow mornings" volatility filter is a subtractive
   filter on the market-fill base, which has only ~24 trades of floor headroom and no
   selection edge ([[2026-06-22-volume-confirmed-orb]], [[2026-06-28-trend-aligned-orb-market-fill-probe]]).
   Breakout family is closed across all level definitions. Discard.

5. **First-hour range → day-range expansion / volatility clustering (StockTitan).** A
   magnitude predictor: a big first hour predicts a big day. This is **directionless** (it
   sizes/times risk, it does not pick a side) → Risk-Governor / position-sizing domain, not a
   directional entry. It also re-expresses the incumbent's existing ATR/ER regime gate.
   Discard.

## Strategy spec
Not reached — no candidate survived triage to an implementable, differentiated,
directional, OHLCV-M15 spec. (Exit-geometry section intentionally omitted: nothing to
parameterise.)

## Implementation notes
No code written. No indicator added, no `Strategy` module, no `register()` line, no test
touched. `state/` untouched; live path (`run.py`, `decide.py`, execution, risk) untouched;
`ConfigStore.promote` not called. Working tree carries pre-existing uncommitted changes from
other sessions (AGENTS.md, CLAUDE.md, gates.py, proposal JSONs, service logs, `.pine`) that
are **not mine**; this run commits ONLY the new report + `INDEX.md`, path-scoped, leaving the
rest as-found (fail-safe: do not sweep another session's mess into my commit).

## Backtest results
None. `trials_used: 0`. Cumulative trial count unchanged at **171**. W28 trial budget
unchanged at **10/10 remaining**.

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|
| — | — | no candidate reached the harness | — |

## Verdict
**Triage-only run — no candidate backtested.** All 5 surveyed mechanisms are disqualified
before spending a trial: 2 violate the pure-spine invariant #1 (ML/causal-inference on the
decision path), 1 is directionless (vol-of-vol forecasting → Risk-Governor), 1 is a
tested-rejected breakout variant + subtractive-filter wall, 1 is a directionless magnitude
predictor. No proposal filed (nothing passed; nothing was even tested). This is the **8th
consecutive triage-only run**.

## Lessons
- **The cost-erosion finding now has a third independent external replication.** After MNQ
  5-min (Mesfin 2026, [[2026-07-05-external-falsification-corroboration-triage]]) and ~100
  futures (Bouchaud et al., [[2026-07-08-microstructural-trend-demise-corroboration-triage]]),
  the ML-hourly-FX literature (arXiv 2606.00060 and the 70k-hourly XGBoost/LSTM/iTransformer
  study) reports the same on EUR/USD & GBP/USD 1min–1h: **gross-profitable in-sample, net
  negative OOS after cost.** Our "OHLCV directional idea space is exhausted on EURUSD M15" is
  now corroborated across three instruments, three method-classes, and (with 07-08) a
  microstructural mechanism. The conclusion is structural, not sampling noise.
- **ML papers keep surfacing as candidates and keep failing the same two gates.** Causal-
  inference and deep-learning directional frameworks are the dominant 2025–2026 q-fin output,
  but every one either (a) puts a learned model inline on the trade (invariant #1) or (b)
  needs a cross-asset/tick surface we don't have (blocked-on-data) — usually both. Future
  triage can fast-path any "ML directional" or "causal-inference signal" hit to disqualified
  without a deep read: the invariant, not the paper's performance claim, is binding.
- **"Vol-of-vol / realized-quarticity" is the new face of the directionless-vol family.**
  HARQ-style forecasts predict volatility *level*, so they land in the Risk-Governor domain,
  not the directional-entry domain — same bucket as functional-GARCH. Worth a one-line note
  only if a run ever re-scopes to *risk sizing* rather than *entry direction*.
- **Process note (unchanged, now 8×):** the binding constraint is the single EURUSD-M15
  parquet, not the idea pipeline. The still-open frontiers all need a data export
  (news-calendar event momentum, options-strike gamma pin, multi-currency carry / cross-
  sectional, equity-conditioned month-end). A longer EURUSD-M15 *directional* history will
  NOT help — 07-08's microstructural mechanism argues that block is structural.

## Next steps
- **Cadence cut (8th reinforcement).** Daily research on a fully-triaged single-instrument
  surface yields triage-only runs; recommend dialing the scheduled task from daily to
  ~2–3×/week (spec 08 §1 "cadence is a dial") until a new data surface lands. Awaits Cayden.
- **Prioritise the data-export lever, directional families first-in-line once it lands:** a
  news/macro-release timestamp calendar (unblocks
  [[2026-06-28-macro-news-release-momentum]]), a second instrument + rates (unblocks
  [[2026-06-24-currency-carry-xs-momentum]], cross-instrument confirmation), an equity daily
  feed (unblocks [[2026-06-30-month-end-calendar-effect]] conditional), options OI/strike
  (unblocks [[2026-06-28-ny-options-cut-gamma-pin]]).
- No queue additions this run — every surveyed idea maps to an existing closed/blocked entry.
