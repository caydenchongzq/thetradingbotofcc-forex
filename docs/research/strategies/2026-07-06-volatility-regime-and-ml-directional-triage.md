---
id: 2026-07-06-volatility-regime-and-ml-directional-triage
name: VolatilityRegimeAndMLDirectionalTriage
family: other
status: research/triage (no trial)
related: [2026-07-05-external-falsification-corroboration-triage, 2026-07-04-cross-dependence-and-ml-directional-triage, 2026-07-03-candlestick-and-volatility-timing-triage, 2026-07-02-directional-ml-and-vol-forecasting-triage, 2026-06-07-cross-instrument-confirmation]
sources:
  - https://arxiv.org/abs/2605.04004
  - https://arxiv.org/pdf/2605.11423
  - https://arxiv.org/html/2512.12924v1
  - https://arxiv.org/pdf/2605.17724
  - https://arxiv.org/html/2311.18477v3
  - https://www.sciencedirect.com/science/article/pii/S0169207025001189
  - https://volatilitybox.com/research/volatility-regimes-explained/
  - https://tradersmastermind.com/trading-strategy-opening-range-breakout/
trials_used: 0
verdict: "Daily pass 2026-07-06: 0 of 5 surfaced mechanisms are BOTH differentiable from a recorded failure mode AND directional+testable on EURUSD-M15 OHLCV. Functional-GARCH / intraday-spot-vol forecasting (arXiv 2311.18477, ScienceDirect S0169207025001189) = directionless (Risk-Governor domain, no entry sign); volatility-volume-gap regime classifier (arXiv 2605.11423) = directionless regime label + needs real volume & gaps the FX feed lacks (weekend-gap probe: feed continuous, tick-volume only); interpretable microstructure signals (arXiv 2512.12924) = regime-dependent, needs elevated info-arrival/microstructure = tick data (blocked) AND its regime-dependence finding corroborates our closure; LSTM-vs-GBM next-session direction (arXiv 2605.17724) = ML directional violates pure-spine invariant #1 AND is null (50.00% = coin-flip, external corroboration); Bollinger-squeeze / ORB = breakout family, closed across all level definitions. No trial; W28 stays 10/10; trials stay 171. 5th consecutive triage-only run — binding constraint remains the EURUSD-M15-only data surface, not idea supply; reinforces the M5 cadence-cut recommendation."
---

# VolatilityRegimeAndMLDirectionalTriage — daily research pass, 2026-07-06

## Hypothesis & market rationale
Daily spec-08 pass. The single-instrument OHLCV idea space was declared **fully closed** on
2026-06-30 and that closure was externally corroborated on 2026-07-05 (Mesfin 2026, arXiv
2605.04004: 14 OHLCV intraday signal families on MNQ 5-min, zero clearing strict OOS/t≥2/
net-of-cost criteria). The object of each subsequent pass is adversarial: surface a mechanism
that is BOTH (i) genuinely differentiable from a recorded failure mode and (ii) directional
and implementable on the only data held — EURUSD M15 OHLCV (`state/parquet/eurusd_m15.parquet`,
tick-volume only, continuous across week boundaries). A mechanism that is directionless
(a volatility/sizing signal) belongs to the Risk Governor, not the deterministic entry spine,
and cannot form a strategy entry; one that needs volume/tick/second-instrument data is
`blocked-on-data`; one that needs a non-pure model on the live path violates invariant #1.

## Sources
- Mesfin (2026), *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A
  Systematic Falsification Study*, arXiv:2605.04004 — 14 signal families, zero clear net of cost.
- *A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ Intraday
  Data*, arXiv:2605.11423 — regime **classifier** (label, not direction), uses volume + gaps.
- *Interpretable Hypothesis-Driven Trading: A Rigorous Walk-Forward Validation Framework for
  Market Microstructure Signals*, arXiv:2512.12924 — microstructure signals require elevated
  information arrival / trading activity; strong **regime dependence** (work only in high-vol).
- *Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ*,
  arXiv:2605.17724 — daily OHLCV features for next-session direction; OOS accuracy 50.00%
  (= coin-flip baseline).
- *Intraday FX Volatility-Curve Forecasting with Functional GARCH Approaches*,
  arXiv:2311.18477v3; *Modeling and forecasting intraday spot volatility*, ScienceDirect
  S0169207025001189 — volatility-curve forecasting (directionless).
- Volatility Box, *Volatility Regimes Explained*; Traders Mastermind, *Opening Range Breakout
  Strategy (2026)* — practitioner framing (breakout / Bollinger-squeeze), closed family.

The backtester — not the source — is the arbiter. This pass produced no falsifiable,
differentiable, directional EURUSD-M15 candidate, so no trial was spent.

## Relation to prior library work
Each surfaced mechanism dedupes onto a recorded verdict:

1. **Functional-GARCH / intraday spot-vol forecasting** (arXiv 2311.18477, ScienceDirect
   S0169207025001189) — **directionless.** Already ruled directionless/Risk-Governor-domain on
   2026-07-02 and 2026-07-04. A volatility forecast gives no entry sign; the Risk Governor
   already owns ATR-floor/ceiling + ATR-percentile sizing (`config/default.yaml` regime block).
   No incremental *directional* information. Not a strategy entry.
2. **Volatility-Volume-Gap regime classifier** (arXiv 2605.11423) — **directionless + blocked.**
   Outputs a regime *label*, not a trade direction; and its two inputs are unavailable in our
   feed: real volume (we hold tick-volume only, shown non-transferable by
   [[2026-06-22-volume-confirmed-orb]]) and gaps (the weekend-gap probe [[2026-06-24-weekend-gap-fill]]
   found the M15 feed continuous across week boundaries, max boundary gap 0.7p). Even as a
   filter it hits the closed filter-family wall ([[2026-06-28-trend-aligned-orb-market-fill-probe]]):
   you cannot filter an edge the live-fillable base lacks.
3. **Interpretable microstructure signals, regime-dependent** (arXiv 2512.12924) —
   **blocked-on-data + corroborates closure.** Requires "elevated information arrival and trading
   activity" (microstructure/tick features we do not have — dedupes to
   [[2026-07-01-order-flow-entropy-magnitude]] blocked-on-data). Its headline finding — signals
   work *only* in high-volatility regimes and underperform in stable markets — independently
   echoes our recurring result that any faint edge is sub-cost outside rare regimes.
4. **LSTM vs Gradient Boosting next-session direction** (arXiv 2605.17724) — **invariant #1
   violation + null.** A learned directional model on the live path breaks the pure-deterministic-
   spine invariant (same ruling as the ML directional candidates on 2026-07-02 and 2026-07-04).
   It is also null on its own terms (OOS accuracy 50.00% = coin flip), a further external
   corroboration of intraday OHLCV directional non-predictability.
5. **Bollinger-squeeze / Opening-Range Breakout** (Volatility Box; Traders Mastermind) —
   **breakout family, closed.** Volatility-contraction→expansion breakout is exactly the NR7
   mechanism ([[2026-06-18-nr7-volatility-breakout]]); the directional breakout family is closed
   across every level definition under live-faithful fills ([[2026-06-15-resting-stop-and-market-entry]]).

## Strategy spec
None. No candidate cleared triage, so nothing was implemented. (Per spec 08 §5.8, exit geometry
is pre-registered only for a candidate that reaches the build stage — not reached this pass.)

## Implementation notes
No code written. No edits to `src/`, `state/`, or the live path. `docs/` only (this report +
INDEX row). pytest not re-run: no code changed this pass and the working tree carries only the
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
Two are directionless (Risk-Governor domain), two need volume/tick/microstructure data we do not
hold (blocked-on-data) or violate the pure-spine invariant, and the practitioner framings dedupe
onto the closed breakout family. No proposal filed.

## Lessons
- **Fifth consecutive triage-only run.** The daily pass is now reliably surfacing only (a)
  directionless volatility/regime work (Risk-Governor, not an entry), (b) data-blocked
  microstructure/multi-instrument mechanisms, or (c) re-labelings of closed families. The
  binding constraint is unambiguously the **data surface** (one instrument, one timeframe,
  tick-volume, continuous feed), not idea supply.
- **The 2026 literature is converging on our verdict from multiple instruments.** MNQ 5-min
  (Mesfin, arXiv 2605.04004 — 14 families, zero clear), MNQ daily-feature next-session
  (arXiv 2605.17724 — 50.00% accuracy), and regime-dependent microstructure (arXiv 2512.12924
  — only-in-high-vol) all independently reproduce "OHLCV intraday directional predictability
  net of cost is structurally absent." Our internal closure is externally robust across
  instrument and timeframe — this raises, not lowers, confidence that further single-dataset
  trials would burn DSR budget for nothing.
- **Directionless ≠ useless, but ≠ a strategy.** Volatility-curve / FGARCH forecasting keeps
  recurring in search results; it is genuinely good work, but it informs *sizing*, which the
  Risk Governor already owns. Recording it as "directionless / Risk-Governor domain" each pass
  is the correct disposition; it never becomes an entry candidate on its own.

## Next steps
- **No code, no trial, no schedule/config change this run** (unsupervised; Cayden not present).
- **Reinforce the M5 cadence-cut recommendation** (spec 08 changelog 2026-06-21, awaiting
  Cayden's OK): reduce `ftmo-research-engine` from daily → 3×/week (`30 8 * * *` →
  `30 8 * * 1,3,5`). Five straight triage-only runs make the case stronger: daily cadence on a
  closed single-dataset idea space yields corroboration, not candidates.
- **The only edge-reviving lever remains a data export** (spec 08 §8 backlog #4): longer EURUSD
  history and/or a second instrument + macro/volume feed. That unblocks the standing queue —
  TrendAlignedORB re-test on the market-fill base, conditional month-end rebalancing
  ([[2026-06-30-month-end-calendar-effect]] → conditional version), macro-news-release momentum,
  options-flow, M5-trigger ORB, cross-instrument confirmation — none testable on current data.
- Idea queue unchanged; nothing added (every surfaced mechanism dedupes to an existing
  closed/blocked entry).
