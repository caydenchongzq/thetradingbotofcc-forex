---
id: 2026-07-05-external-falsification-corroboration-triage
name: ExternalFalsificationCorroborationTriage
family: other
status: research/triage (no trial)
related: [2026-07-04-cross-dependence-and-ml-directional-triage, 2026-07-03-candlestick-and-volatility-timing-triage, 2026-07-02-directional-ml-and-vol-forecasting-triage, 2026-07-01-signed-semivariance-momentum, 2026-06-07-cross-instrument-confirmation]
sources:
  - https://arxiv.org/abs/2605.04004
  - https://arxiv.org/pdf/2605.04004
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6709401
  - https://algorithmictoken.substack.com/p/strategy-lab-3-the-signals-that-dont
  - https://arxiv.org/pdf/2604.07870
  - https://arxiv.org/pdf/1604.07969
  - https://www.sciencedirect.com/science/article/pii/S0169207025001281
  - https://link.springer.com/article/10.1007/s44163-025-00424-4
  - https://arxiv.org/html/2512.12924v1
  - https://www.quantifiedstrategies.com/gap-fill-trading-strategies/
trials_used: 0
verdict: "Daily pass 2026-07-05: 0 of 5 surfaced mechanisms are both differentiable from a recorded failure mode AND testable on EURUSD-M15 OHLCV. Realized-skewness/higher-moment directional = dedupes to the closed variance-decomposition leg of the trend/momentum family (signed-semivariance, 07-01) or is cross-sectional (blocked-on-data); cross-currency LOB predictability = blocked-on-data (dedupes to CrossInstrumentConfirmation); ML 8-pair directional = pure-spine invariant #1 violation; microstructure walk-forward = needs tick data. HEADLINE: an INDEPENDENT external falsification study (Mesfin 2026, arXiv 2605.04004) tested 14 OHLCV intraday signal families on MNQ 5-min (2021-2025) under strict OOS/t≥2/net-of-cost criteria and found ZERO clear — same methodology, same verdict as this library, on a different instrument. Strong external corroboration of the closure. No trial; W27 stays 10/10; trials stay 171. 4th consecutive triage-only run — reinforces the cadence-cut recommendation."
---

# ExternalFalsificationCorroborationTriage — daily research pass, 2026-07-05

## Hypothesis & market rationale
Daily spec-08 pass. The single-instrument OHLCV idea space was marked **fully closed** on
2026-06-30 (breakout across all level definitions, mean-reversion 7/7, trend/momentum across
raw-drift / vol-conditioning / cross-session / variance-decomposition, seasonality & calendar,
exit-model 0/5, filter family floor-bound). Since then the object of each pass is to test that
closure *adversarially*: find a mechanism that is BOTH (i) genuinely differentiable from a
recorded failure mode and (ii) implementable & testable on the only data we hold (EURUSD M15
OHLCV parquet). Anything failing either test is triaged without spending a trial (spec 08 §4.3
— re-testing a closed family+failure-mode without stated differentiation burns DSR budget for
nothing).

## Sources
- **Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification
  Study** — Mathias Mesfin, arXiv **2605.04004** / SSRN 6709401 (2026). 947 trading days of
  5-minute MNQ data (2021-2025); **fourteen** signal families tested — opening-range breakouts,
  gap strategies, volume signals, cross-session momentum, liquidity grabs, volatility-conditioned
  classifiers, and news-driven strategies — under strict institutional criteria (OOS walk-forward,
  |t| ≥ 2.0, ≥ 30 trades, positive net return after a fixed 2-point round-trip cost, multi-year
  stability). **Primary conclusion: no signal satisfies all criteria simultaneously; gross edge to
  next-bar-open execution is ~0.07–1.50 points/trade, insufficient to overcome cost.**
  Practitioner writeup: algorithmictoken Substack "Strategy Lab #3 — The Signals That Don't Work."
- **Skewness Dispersion and Stock Market Returns** — arXiv 2604.07870 (2026): cross-sectional
  inter-percentile range of daily realized skewness as a return predictor.
- **On the Surprising Explanatory Power of Higher Realized Moments in Practice** — arXiv 1604.07969:
  realized skewness/kurtosis forecasting; finds realized kurtosis forecasts *variance*, not return
  sign.
- **Assessing cross-currency predictability in forex markets: insights from limit order book data**
  — ScienceDirect S0169207025001281 (2025): cross-currency directional predictability from LOB
  microstructure.
- **Directional forecasting for eight forex pairs vs the US dollar using ML** — Springer Nature
  s44163-025-00424-4 (2025): RF/XGBoost directional classifiers.
- **Interpretable Hypothesis-Driven Trading: a walk-forward validation framework for market
  microstructure signals** — arXiv 2512.12924v1 (2025): methodology on microstructure signals.
- Gap-fill / opening-range practitioner catalogs (QuantifiedStrategies) — surveyed for any
  non-closed mechanism; the equity gap-fill fade is documented to fail at every entry time.

## Relation to prior library work — candidate-by-candidate triage
1. **Mesfin 2026 systematic OHLCV falsification study (arXiv 2605.04004).** Not a strategy — a
   *result*. It is an independent research program that ran the same falsification protocol this
   library uses (pre-specified gates, walk-forward, net-of-cost, negative-result documentation)
   over 14 OHLCV intraday signal families and reached the same verdict: **no OHLCV intraday signal
   clears cost.** Its family list maps almost one-to-one onto ours — opening-range breakout
   ([[2026-06-15-resting-stop-and-market-entry]]), gaps ([[2026-06-24-weekend-gap-fill]] /
   [[2026-06-26-prior-day-overreaction-reversal]]), volume ([[2026-06-22-volume-confirmed-orb]]),
   cross-session momentum ([[2026-06-29-asian-session-drift-signal]]), liquidity grabs / sweeps
   ([[2026-06-30-twenty-day-turtle-soup]], [[2026-06-19-session-range-false-break-fade]]),
   volatility-conditioned ([[2026-06-23-vol-conditioned-intraday-momentum]]), news-driven
   ([[2026-06-28-macro-news-release-momentum]], blocked-on-data). **Strong external corroboration
   of the closure thesis on a *different* instrument (MNQ) and *different* timeframe (5-min).**
   The mechanism is a general property of liquid, well-arbitraged intraday markets, not an
   EURUSD-M15 quirk. Nothing to test. **CORROBORATION — no candidate.**
2. **Realized-skewness / higher-realized-moment directional (arXiv 2604.07870, 1604.07969).** The
   only novel directional angle. Two sub-cases, both closed: (a) *Time-series* realized skewness of
   intraday returns as a predictor of the next window's return is a higher-moment sibling of the
   signed-semivariance imbalance already probed and rejected ([[2026-07-01-signed-semivariance-momentum]],
   |corr| ≤ 0.03, best gross +0.49p ≪ 2.6p cost) — same distributional-asymmetry information, same
   closed variance-decomposition leg of the trend/momentum family; and 1604.07969's own finding is
   that realized *kurtosis* forecasts variance (directionless → Risk-Governor domain). (b)
   *Skewness dispersion* (arXiv 2604.07870) is explicitly **cross-sectional** — the inter-percentile
   range across a universe of assets — so it needs a multi-asset universe not in the parquet.
   **DISCARD — time-series case dedupes to the closed variance-decomposition family; cross-sectional
   case is blocked-on-data.**
3. **Cross-currency predictability from limit-order-book data (ScienceDirect S0169207025001281).**
   Needs (i) a second currency and (ii) LOB/microstructure depth — the parquet holds only EURUSD M15
   OHLCV with tick-volume. Exact mechanism already queued as
   [[2026-06-07-cross-instrument-confirmation]] (**blocked-on-data**). **DEDUPE → blocked-on-data;**
   revives only with a multi-instrument + depth export (§8 backlog #4).
4. **ML directional forecasting, 8 FX pairs (Springer s44163-025-00424-4).** A tree/ensemble
   classifier as the entry decision directly violates **hard invariant #1** (the spine must be a
   *pure, deterministic* function of (bars, now, context_bias, calendar); AI is offline-propose-only,
   never inline on a live trade). Same exclusion recorded 07-02 and 07-04. **DISCARD —
   invariant-violating.**
5. **Interpretable hypothesis-driven microstructure walk-forward (arXiv 2512.12924v1).** A
   *validation methodology* over market-microstructure signals (order-book imbalance, tick-level
   flow). The framework is sound (and echoes our own harness) but its signals need tick/LOB data we
   do not have; as an entry mechanism it is directionless-until-fed-microstructure. **DISCARD —
   blocked-on-data / methodology, not a testable OHLCV signal.**

Dedup result: **0 of 5** are both differentiable from a recorded failure mode and OHLCV-testable.
Two (cross-currency LOB, skewness-dispersion) are legitimate future directions already covered by
the blocked-on-data queue; one is invariant-violating; one is directionless-until-microstructure;
and the headline item is a *corroboration*, not a candidate.

## Strategy spec
N/A — no candidate selected for implementation. No indicator, strategy module, registry entry,
or test was added. `src/` untouched.

## Implementation notes
No code written. Additive-only guarantee trivially held: docs-only change (this report +
INDEX.md line). No writes to `state/`, no touch of the live path (`run.py`, `decide.py`,
execution, risk), no `ConfigStore.promote`. The pre-existing dirty working tree (AGENTS.md,
CLAUDE.md, `src/backtest/gates.py`, proposal JSONs, wrapper.log, `.pine`, PROMOTION_BRIEF_*.md)
is **not from this run** and was left untouched — the commit is path-scoped to this report and
INDEX.md only (fail-safe: leave the repo green, do not sweep unrelated changes into an autonomous
commit).

## Backtest results
None. No trial spent. Trial ledger unchanged (cumulative **171**); W27 budget unchanged (**10/10**).

## Verdict
**Triage-only, no trial.** 0 testable candidates. The daily pass surfaced only (a) closed-family
mechanisms (breakout, mean-reversion, trend/momentum incl. higher-moment decomposition), (b)
invariant-violating ML directional models, or (c) blocked-on-data cross-instrument / LOB /
microstructure signals. No proposal filed. Budget and ledger preserved.

## Lessons
- **The closure now has independent external corroboration.** Mesfin 2026 (arXiv 2605.04004) is
  the first *outside* study to run our exact falsification protocol — pre-specified gates, OOS
  walk-forward, |t| ≥ 2, net-of-cost — over the *same 14 OHLCV signal families* on a different
  liquid instrument (MNQ), and reach the same conclusion: **no OHLCV intraday signal clears cost.**
  This upgrades our "idea space exhausted on 2024-2026 EURUSD M15" from an internal empirical
  finding to a corroborated structural property of liquid intraday markets. The binding constraint
  is confirmed to be the *data surface* (single-instrument OHLCV, net of a ~2.6p cost stack), not a
  gap in our search or a peculiarity of EURUSD.
- **Higher realized moments keep resolving to two already-closed buckets.** Every "new" moment-based
  directional idea (semivariance 07-01, now realized skewness/kurtosis) either (i) carries no
  directional information beyond raw drift on 24h FX — because FX lacks the overnight-close
  information-concentration that powers the equity results — landing in the closed
  variance-decomposition leg, or (ii) is cross-sectional and needs a universe we don't have. The
  triage rule to demand a *time-series, single-instrument, net-of-cost* differentiation before a
  trial keeps catching these cheaply.
- **4th consecutive triage-only run.** The idea-supply side is not the bottleneck; the data side is.
  Reinforces the standing M5 recommendation to cut research cadence (daily → ~2–3×/week) until a
  data lever lands. The highest-value unblockers remain, in priority order: a **longer EURUSD-M15
  history export** (revives the sample-size-bound TrendAlignedORB re-test and the subtractive-filter
  family), a **second instrument + macro/rate feed** (unblocks CrossInstrumentConfirmation, currency
  carry/XS-momentum, cross-currency LOB predictability), an **M5 export** (M5TriggerORB), a **news
  calendar** (MacroNewsReleaseMomentum), and an **equity-return feed** (conditional month-end
  rebalancing).

## Next steps
- No new queue entries (nothing surfaced that is not already recorded). The skewness-dispersion and
  cross-currency-LOB items map onto existing blocked-on-data entries
  ([[2026-06-07-cross-instrument-confirmation]], [[2026-06-24-currency-carry-xs-momentum]]).
- Awaiting Cayden: (1) approval of the standing **cadence-cut** (daily → 2–3×/week); (2) a **data
  export** decision to unblock the queue — a longer EURUSD-M15 history is the single highest-yield
  lever and directly revives a concrete queued re-test (TrendAlignedORB).
