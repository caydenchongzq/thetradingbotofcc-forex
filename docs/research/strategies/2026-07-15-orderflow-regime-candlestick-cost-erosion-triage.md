---
id: 2026-07-15-orderflow-regime-candlestick-cost-erosion-triage
name: OrderFlowRegimeCandlestickCostErosionTriage
family: other
status: research/triage (no trial)
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-16-vwap-stretch-reversion, 2026-06-28-trend-aligned-orb-market-fill-probe, 2026-07-01-order-flow-entropy-magnitude, 2026-07-13-overnight-reversal-and-transformer-fx-triage, 2026-07-14-range-expansion-and-candlestick-cost-erosion-triage]
sources: ["https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf", "https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/c953a0e6-e93e-4bf7-b839-45a90cedced4.pdf", "https://arxiv.org/abs/2605.04004", "https://volity.io/forex/candlestick-patterns/", "https://www.sciencedirect.com/science/article/pii/S095741742501351X", "https://github.com/paperswithbacktest/awesome-systematic-trading"]
trials_used: 0
verdict: "Daily pass 2026-07-15: 5 candidates, 0 differentiable+directional+OHLCV-M15-testable. (1) Order-flow imbalance reversal (SNB WP 2011-04 intraday FX returns & order flow; 2026 practitioner order-flow revival) = needs tick/trade-signed order flow the M15 OHLCV feed lacks → blocked-on-data, dedupes [[2026-07-01-order-flow-entropy-magnitude]] + [[2026-06-07-cross-instrument-confirmation]]; tick VOLUME already probed adverse [[2026-06-22-volume-confirmed-orb]]; (2) three-layer regime filter (50-EMA slope ≥15 bars + HH/HL structure + ADX(14)>25) on an ORB = a stacked subtractive filter on the −0.080R market-fill base → filter-family wall (ADX gate + TrendAlignedORB both already closed [[2026-06-28-trend-aligned-orb-market-fill-probe]]); cannot filter an edge the live-fillable base lacks; (3) confluence candlestick (engulfing at H4 S/R) EURUSD = single-bar reversal trigger at a prior-day level → MR 7/7 closed + breakout-across-all-levels closed, and the ML-signals FX study (ScienceDirect S095741742501351X) reports OOS profitability eroded by cost — a 5th external cost-erosion corroboration; (4) Overnight-Intraday Reversal (Della Corte-Kosowski) = re-surfaced, still blocked-on-data (continuous M15 feed has no close/open discontinuity [[2026-07-13-overnight-reversal-and-transformer-fx-triage]]); (5) VWAP session mean-reversion = already tested-rejected [[2026-06-16-vwap-stretch-reversion]]. No trial; W29 stays 10/10; trials stay 171. 12th consecutive triage-only run — binding constraint remains the EURUSD-M15-only data surface, not idea supply; reinforces cadence-cut recommendation."
---

# OrderFlowRegimeCandlestickCostErosionTriage — daily research pass 2026-07-15

## Hypothesis & market rationale
Daily spec-08 pass. Today is Wed 2026-07-15 (ISO 2026-W29). The prior eleven runs were all
triage-only: the OHLCV-M15 directional idea space is closed internally (breakout 4× under
live-faithful fills, trend/momentum across raw-drift/vol-conditioning/cross-session/variance-
decomposition, mean-reversion 7/7 across every anchor, seasonality/calendar, exit-model 0/5,
filter-family by transitivity) and corroborated externally four times over (MNQ 5-min
falsification, ~100-futures microstructural trend-demise, an ML hourly-return net-negative-OOS
study, and a first-hour range-expansion continuation that is directionally WRONG at the
market-fill entry). The task remains an honest online scan, a §4.3 triage of 3–5 fresh
candidates against the library, and — only if a candidate is differentiable, directional, and
testable on `state/parquet/eurusd_m15.parquet` — a dev-isolated backtest within the W29 trial
budget. Everything else is queued or discarded with a stated reason.

## Sources
- SNB Working Paper 2011-04, *Intraday patterns in FX returns and order flow* — order flow
  drives FX returns via a liquidity-provision (not asymmetric-information) mechanism.
  https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf
- Della Corte & Kosowski, *Overnight-Intraday Reversal Everywhere* (FX-inclusive).
  https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/c953a0e6-e93e-4bf7-b839-45a90cedced4.pdf
- Mesfin (2026), *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures* (arXiv
  2605.04004) — external falsification of 14 OHLCV signal families, zero clear the cost.
  https://arxiv.org/abs/2605.04004
- Volity, *Candlestick Patterns: Mastering Price Action … 2026* — confluence engulfing at H4
  S/R, practitioner claim. https://volity.io/forex/candlestick-patterns/
- *Predictive modeling of foreign exchange trading signals using machine learning techniques*
  (ScienceDirect S095741742501351X) — gross-profitable in-sample, cost-eroded OOS on EUR/USD.
  https://www.sciencedirect.com/science/article/pii/S095741742501351X
- paperswithbacktest/awesome-systematic-trading (curated catalog, revisited).
  https://github.com/paperswithbacktest/awesome-systematic-trading

## Relation to prior library work
Each candidate maps to an existing closed family, a blocked-on-data entry, or an
invariant violation. None supplies a new, live-fillable, OHLCV-M15-testable directional
mechanism.

1. **Order-flow imbalance reversal (SNB WP 2011-04 + 2026 order-flow revival).** The SNB
   result is real (order flow → returns via liquidity provision), but "order flow" means
   trade-signed volume / quote imbalance at tick or trade resolution. Our feed is M15 OHLCV
   with *tick count* volume only — no signing, no depth. This dedupes to
   [[2026-07-01-order-flow-entropy-magnitude]] (blocked-on-data, needs tick/order-level) and
   the cross-instrument/LOB blocked entry [[2026-06-07-cross-instrument-confirmation]]. The
   only OHLCV proxy we have — tick volume — was already probed as a break confirmer with
   flat-to-adverse selection ([[2026-06-22-volume-confirmed-orb]]). **blocked-on-data.**

2. **Three-layer regime filter on an ORB (50-EMA slope ≥15 bars + HH/HL + ADX(14)>25).** This
   is the exact retail "regime filter" pattern that recurs each pass. Mechanically it is a
   stacked *subtractive* filter on the incumbent breakout entry, whose live-fillable
   market-fill base is −0.080R with only ~24 trades of floor headroom. The EMA-slope/HH-HL
   leg is the directional trend veto already probed at maximum strength
   ([[2026-06-28-trend-aligned-orb-market-fill-probe]]: −0.027R / 149 trades, all gates fail);
   the ADX(14) leg is closed by mechanism argument (`ADXTrendStrengthGatedORB`, 2026-06-30).
   Stacking two closed vetoes cannot exceed the weaker one and shrinks trade count further —
   the general filter ruling holds: **you cannot filter an edge the live-fillable base lacks.**
   Dedupes to the closed filter family; **no trial.**

3. **Confluence candlestick (bullish/bearish engulfing at H4 support/resistance), EUR/USD.**
   An engulfing bar at a prior-structure level is a single-bar reversal/continuation trigger
   anchored to a price level. Both readings are closed: mean-reversion fade is 7/7 across all
   anchors, and breakout is closed across every level definition (intraday OR, London OR, NR7,
   Asian box, PDH/PDL, pivots). Single-bar candlestick microstructure specifically was closed
   via [[2026-06-29-high-er-thrust-fade]] and the 07-03 / 07-14 candlestick triages, with
   external academic nulls (Marshall-Young-Rose 2006; Orquín et al. EUR/USD 1-min). The
   ML-signals FX study (ScienceDirect S095741742501351X) adds a **5th external cost-erosion
   corroboration**: gross-profitable in-sample EUR/USD signals go net-negative OOS after cost.
   Dedupes to closed families; **no trial.**

4. **Overnight-Intraday Reversal (Della Corte-Kosowski).** Re-surfaced by the order-flow
   search. Unchanged verdict from yesterday
   ([[2026-07-13-overnight-reversal-and-transformer-fx-triage]]): the strategy needs a clean
   daily close→open discontinuity to anchor the overnight leg, which the **continuous** M15
   feed structurally lacks (max week-boundary gap 0.7p, [[2026-06-24-weekend-gap-fill]]). Also
   risks the closed MR-fade family and requires a positive a-priori reversal-sign probe once a
   session-anchored feed exists. **blocked-on-data.**

5. **VWAP session mean-reversion.** The "single most important intraday mean-reversion anchor"
   in every practitioner list. Already tested-rejected as `VWAPStretchReversion`
   ([[2026-06-16-vwap-stretch-reversion]]); part of the MR 7/7 closure. **no trial.**

## Strategy spec
Not reached — no candidate cleared triage. Per spec 08 §4.3, a variant of a rejected idea may
not consume a trial without a stated differentiator that defeats the recorded failure mode;
none of the five supplies one, and the two genuinely-distinct mechanisms (order flow,
overnight reversal) are blocked-on-data.

## Implementation notes
No code, no registry entry, no test changes. No writes to `state/` or the live path. Repo
left green (`python -m pytest -q` unchanged from HEAD — no source touched). This report +
the INDEX line are the only additions.

## Backtest results
None. `trials_used: 0`. Trial ledger unchanged (cumulative 171). W29 budget 10/10 remaining.

## Verdict
**No candidate testable on current data.** 0 trials consumed. Two blocked-on-data mechanisms
worth keeping warm for the data-export lever (order-flow imbalance; overnight-intraday
reversal — already queued); three dedupe to closed families (regime-filter/ADX, confluence
candlestick, VWAP MR). No proposal filed.

## Lessons
- **12th consecutive triage-only run.** The daily scan continues to return only (a) closed
  OHLCV families relabelled, (b) blocked-on-data microstructure/cross-sectional mechanisms, or
  (c) pure-spine-invariant-violating ML. Idea *supply* is not the bottleneck; the
  EURUSD-M15-only, OHLCV-only, continuous-feed data surface is.
- **Order flow is the highest-value blocked mechanism, not a new open idea.** The SNB
  liquidity-provision result is exactly the microstructure channel Kurth-Eisler-Rej-Bouchaud
  invoked for the trend/breakout *demise* ([[2026-07-08-microstructural-trend-demise-corroboration-triage]]).
  It is not tradeable without signed order flow / depth — reinforcing that the productive next
  step is a data upgrade (tick/order-flow or a second instrument), not another OHLCV probe.
- **The cost-erosion corroboration count is now five** (MNQ 5-min; ~100 futures; ML hourly-OOS;
  range-expansion mis-direction; ML-signals FX net-negative-OOS). The external literature keeps
  independently reconstructing our internal closure — strong evidence the closure is a property
  of the market, not of our harness.
- Process note: the cadence-cut recommendation (M5 review, [[m5-review-2026-06-21]]) is now
  reinforced twelve runs deep. A daily cadence on a saturated data surface produces one triage
  report per day with no trials; a 2–3×/week cadence (or an event trigger tied to a new data
  export) would preserve the same coverage at lower cost.

## Next steps
- Hold at trials=171, W29 budget 10/10.
- Priority remains the **data-export lever**: (a) longer EURUSD-M15 history — but note the
  07-08 mechanism finding means a longer *directional* history will NOT revive breakout/trend
  (structural, not length-bound); the length lever helps the sample-size-bound
  filter/event/cross-sectional frontier only; (b) tick / signed order-flow feed (unblocks the
  order-flow imbalance and entropy-magnitude ideas); (c) a second instrument + macro/rate feed
  (unblocks carry/XS-momentum, cross-instrument confirmation, conditional month-end); (d) a
  news-release calendar (unblocks MacroNewsReleaseMomentum — the cleanest genuinely-different
  family still standing).
- No change to the live path or ConfigStore. Nothing awaits Cayden's approval from this run
  beyond the standing cadence-cut and data-export decisions.
