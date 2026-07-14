---
id: 2026-07-14-range-expansion-and-candlestick-cost-erosion-triage
name: RangeExpansionAndCandlestickCostErosionTriage
family: other
status: research/triage (no trial)
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-18-nr7-volatility-breakout, 2026-07-05-external-falsification-corroboration-triage, 2026-07-08-microstructural-trend-demise-corroboration-triage, 2026-07-09-causal-ml-and-vol-of-vol-directional-triage, 2026-06-22-volume-confirmed-orb]
sources: ["https://arxiv.org/pdf/2605.04004", "https://www.mdpi.com/2227-7390/8/5/802", "https://quantifiedstrategies.substack.com/p/candlestick-patterns-that-actually", "https://arxiv.org/pdf/2603.27501", "https://arxiv.org/html/2507.09347v1", "https://public.econ.duke.edu/~boller/Papers/HFML.pdf"]
trials_used: 0
verdict: "Daily pass 2026-07-14: 5 candidates, 0 differentiable+directional+OHLCV-M15-testable. (1) Intraday range-EXPANSION continuation (MNQ falsification arXiv 2605.04004 + a 2026 first-hour range-expansion study) fires the SAME market-fill-offset mechanism that closed our breakout family: t=-10.96 at 1.5x-range, continuation direction actively WRONG because the move is exhausted by the next-bar-open entry — a 4th external corroboration of the touch-tax/exhaustion closure [[2026-07-08-microstructural-trend-demise-corroboration-triage]], NOT a new edge; (2) adaptive candlestick patterns EURUSD (MDPI Mathematics 8(5):802 + QuantifiedStrategies ranking) — the cited EURUSD study reports NO net-positive return after costs, and a pattern is just a reversal/continuation trigger = breakout or MR, both closed across all level defs; corroborates cost-erosion; (3) skew-enhanced SABR vol model (arXiv 2603.27501) = options implied-vol surface → blocked-on-data + directionless (Risk-Governor/functional-GARCH closed); (4) volatility+causal-inference directional framework (arXiv 2507.09347) = GMM+Granger/PCMCI ML on the decision path (invariant #1) + 45-day OOS + cross-asset, already deduped 07-09; (5) intraday-return factor-zoo predictability (Bollerslev HFML, Duke) = high-frequency ML factor zoo on an equity index → invariant #1 + blocked-on-data. No trial; W29 stays 10/10; trials stay 171. 11th consecutive triage-only run — binding constraint remains the EURUSD-M15-only data surface, not idea supply; reinforces cadence-cut recommendation."
---

# RangeExpansionAndCandlestickCostErosionTriage — daily research pass 2026-07-14

## Hypothesis & market rationale
Daily spec-08 pass. Today is Tue 2026-07-14 (ISO 2026-W29). The prior 10 runs were all
triage-only: the OHLCV-M15 directional idea space is closed internally (breakout 4× under
live fills, trend/momentum, mean-reversion 7/7, seasonality, exit-model 0/5, filter-family
by transitivity) and corroborated externally three times over (MNQ 5-min falsification,
~100-futures microstructural trend-demise, an ML hourly-return net-negative OOS study). The
task is still to run an honest online scan, triage 3–5 fresh candidates against the library,
and only spend a trial on a candidate that is **differentiable + directional + OHLCV-M15-
testable + live-fillable**. Budget for W29 is FRESH (10/10; 0 spent — the trial ledger's last
entry is 2026-06-25, trial #171).

## Sources
- Mesfin (2026), *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A
  Systematic Falsification Study* — arXiv 2605.04004. Range-expansion continuation leg:
  t = **-10.96** at the 1.5x-mean-range threshold (2.0x, 2.5x similar), continuation
  **actively wrong**; authors attribute it to the signal being exhausted by the time a
  bar-close fires and entry executes at the next bar open.
- A 2026 intraday first-hour range-expansion study (surfaced via web search, same finding):
  bars whose range exceeds 1.5/2.0/2.5x the rolling mean range do **not** continue in the
  expansion direction net of friction.
- Cakici/Zaremba-style adaptive candlestick work: *Predictive Power of Adaptive Candlestick
  Patterns in Forex Market. EURUSD Case* — MDPI *Mathematics* 8(5):802
  (https://www.mdpi.com/2227-7390/8/5/802) — **no net-positive average return after
  transaction costs in any case**.
- QuantifiedStrategies, *Candlestick Patterns That Actually Work: Ranked by Backtested
  Performance* — daily-OHLCV pattern ranking, practitioner tier.
- *From Volatility to Variance: A Skew-Enhanced SABR Model* — arXiv 2603.27501 (options
  implied-vol skew, Chinese options market).
- *A Framework for Predictive Directional Trading Based on Volatility and Causal Inference*
  — arXiv 2507.09347 (GMM + Granger + PCMCI, 45-day backtest, cross-asset).
- Bollerslev et al., *Intraday Market Return Predictability Culled from the Factor Zoo*
  (Duke HFML working paper) — high-frequency ML across a large factor zoo, equity index.

## Relation to prior library work
Every candidate dedupes to an already-closed family, an invariant violation, or a
blocked-on-data gate. Details in the triage table.

## Triage — 5 candidates

**1. Intraday range-expansion continuation.** *Idea:* enter in the direction of a bar whose
range exceeds k×(rolling mean range), expecting continuation. *Ruling:* **closed —
corroboration, not a candidate.** This is a breakout by another name (the "level" is a
volatility threshold instead of an OR high/low), and the MNQ falsification measured it
directly: t = -10.96, continuation direction **actively wrong** at k=1.5, because a bar-close
signal + next-bar-open **market** entry arrives after the move. That is *precisely* the
market-fill offset / touch-tax mechanism that closed our directional breakout family under
live-faithful fills ([[2026-06-15-resting-stop-and-market-entry]], [[2026-06-18-nr7-volatility-breakout]])
and that Kurth-Eisler-Rej-Bouchaud gave a microstructural generator for
([[2026-07-08-microstructural-trend-demise-corroboration-triage]]). This is now the **4th
independent external corroboration** of the exhaustion/cost-erosion closure. No trial — a
re-test would burn budget to re-derive a result we hold internally with a mechanism.

**2. Adaptive candlestick patterns (EURUSD).** *Idea:* trade classic/adaptive candlestick
reversal or continuation patterns as entry triggers. *Ruling:* **discard — dedupes to closed
breakout/MR + cited EURUSD evidence is net-negative.** A candlestick pattern is only a
trigger for a reversal (mean-reversion, 7/7 closed) or continuation (breakout, closed across
every level definition) — it introduces no new economic mechanism, just a different way to
mark the same level. The strongest cited EURUSD-specific study (MDPI *Mathematics* 8(5):802)
reports **no net-positive average return after costs in any case**, matching our own
cost-erosion wall ([[2026-06-22-volume-confirmed-orb]], the MNQ falsification). Testable on
M15 in principle, but it would spend a trial to re-confirm the closed families at a
lower-power pattern base. No trial.

**3. Skew-enhanced SABR volatility model** (arXiv 2603.27501). *Ruling:* **blocked-on-data +
directionless.** Requires an options implied-volatility surface (skew), which the EURUSD-M15
OHLCV parquet does not contain, and it forecasts variance/skew, not price direction — the
Risk Governor's domain, dedupes to the closed functional-GARCH / intraday-vol-forecasting
family ([[2026-07-09-causal-ml-and-vol-of-vol-directional-triage]]).

**4. Volatility + causal-inference directional framework** (arXiv 2507.09347). *Ruling:*
**invariant #1 + blocked-on-data.** GMM regime states plus Granger-causality and PCMCI
causal-graph learning on a cross-asset universe put a fitted ML/causal model on the decision
path (violates the pure deterministic spine, invariant #1), need instruments beyond EURUSD,
and the paper's own 45-day OOS is far too short to clear our walk-forward. Already surfaced
and disqualified 2026-07-09; re-surfacing does not change the ruling.

**5. Intraday-return predictability from the factor zoo** (Bollerslev HFML, Duke). *Ruling:*
**invariant #1 + blocked-on-data.** High-frequency machine learning across a large factor
zoo, on an equity index, to predict intraday market return — a fitted-model decision path
(invariant #1) requiring a factor panel that does not exist in the M15 parquet. Its
methodological note (intraday return predictability is thin and regime-dependent) mildly
corroborates the closure but supplies no live-fillable single-instrument signal.

## Strategy spec
N/A — no candidate selected for implementation. Nothing was built; `src/`, tests, `state/`,
the live path, and the ConfigStore are untouched.

## Implementation notes
No code changed. No indicator, strategy, registry line, or test added. No writes to
`state/`; live path (`run.py`, `decide.py`, execution, risk) untouched; `ConfigStore.promote`
not called. This report + the INDEX row are the only additions.

## Backtest results
None. No candidate was differentiable + directional + OHLCV-M15-testable + live-fillable, so
no `run_backtest.py` invocation and no trial-ledger entry. Cumulative trials remain **171**;
W29 budget remains **10/10**.

## Verdict
**0 of 5 candidates testable today. No trial spent.** 11th consecutive triage-only run.
Candidate 1 (range-expansion continuation) is upgraded to a 4th external corroboration of the
directional-breakout closure — same market-fill-offset mechanism, measured directly at
t = -10.96. Candidate 2 (candlesticks) is a level-relabelling of the closed breakout/MR
families with net-negative cited EURUSD evidence. Candidates 3–5 are blocked-on-data and/or
invariant-#1 (ML-on-decision-path) violations.

## Lessons
- **Range-expansion = breakout in volatility coordinates, and it fails for the identical
  reason.** A bar-close volatility-threshold trigger followed by a next-bar-open market fill
  is the exact seam CLAUDE.md invariant #3 warns about: the signal needs the close to
  confirm, but the edge needs you to act *before* the close. The MNQ t = -10.96 (wrong
  direction) is the cleanest external measurement yet of that seam. Any future "expansion" or
  "thrust" continuation idea inherits this closure by construction — do not spend a trial on
  one without a live-fillable pre-trigger fill *and* a positive gross base.
- **Candlestick patterns add no mechanism.** They only mark a reversal or continuation level,
  so they collapse into the closed MR (7/7) and breakout families; the strongest EURUSD study
  is net-negative after costs. File future "pattern" ideas straight to discard unless they
  carry a genuinely new economic conditioner.
- **The 2026 literature keeps handing us corroboration, not signals.** Four external
  falsifications now agree with our internal closure (MNQ 5-min, ~100 futures microstructure,
  ML hourly net-negative OOS, and now range-expansion t = -10.96). The binding constraint is
  unchanged and structural: a single-instrument EURUSD-M15 OHLCV surface. A longer EURUSD-M15
  export will NOT revive directional edges; the only live levers are the still-open
  *blocked-on-data* frontiers.

## Next steps
- No new queue entries — all 5 candidates dedupe to existing closed/blocked items; the idea
  queue is unchanged.
- **Cadence cut (standing recommendation, awaits Cayden).** 11 consecutive zero-trial runs
  argue for dialing the daily schedule to ~2–3x/week; the M5 review (2026-06-21) already
  recommended this. Awaiting Cayden's approval — not applied autonomously.
- **The only edge-bearing lever is a data export** to unlock the blocked-on-data frontier,
  ranked by expected differentiation from the closed OHLCV families:
  1. Macro news-release timestamps → `MacroNewsReleaseMomentum` (event-driven, market-fill,
     genuinely distinct from clock-time breakout/seasonality).
  2. A second instrument + rates → `CurrencyCarryXSMomentum`, `CrossInstrumentConfirmation`,
     `MonthEndConditionalRebalancing`, `CrossCurrencyLowVolumeReversal`.
  3. A true session-close/overnight-gap FX feed → `OvernightIntradayReversal`,
     `EndOfDayReversal` (both require a positive a-priori reversal-sign probe given MR is 7/7).
  A longer EURUSD-M15 directional history is explicitly **de-prioritised** — the directional
  closure is now mechanism-backed, not sample-bound.
