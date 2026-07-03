---
id: 2026-07-03-candlestick-and-volatility-timing-triage
name: CandlestickAndVolatilityTimingTriage
family: other
status: idea
related: [2026-07-02-directional-ml-and-vol-forecasting-triage, 2026-06-29-high-er-thrust-fade, 2026-06-30-ohlcv-exhausted-final-closure, 2026-06-17-intraday-seasonality-drift, 2026-06-22-volume-confirmed-orb]
sources: ["https://github.com/wangzhe3224/awesome-systematic-trading", "https://www.alphaexcapital.com/forex/forex-market-analysis/candlestick-patterns/high-probability-candlestick-patterns-for-forex", "https://www.oru.se/globalassets/oru-sv/institutioner/hh/workingpapers/workingpapers2025/wp-14-2025.pdf", "https://arxiv.org/html/2311.18477v3", "https://tradersmastermind.com/trading-strategy-opening-range-breakout/"]
trials_used: 0
verdict: "Daily research pass 2026-07-03: no differentiable, OHLCV-M15-testable, live-fillable candidate. Every mechanism surfaced maps to a closed family (candlestick/engulfing reversal = single-bar MR, closed; ORB/gap = breakout, closed; time-of-day = seasonality, closed) or is directionless (volume-driven time-of-day volatility, functional GARCH = Risk-Governor domain). Notably, external academic evidence (Marshall-Young-Rose 2006; Orquin et al. EURUSD 1-min) independently corroborates the library's single-bar/MR closure — candlestick patterns show no edge net of cost. No trial spent; W27 budget stays 10/10, trials stay 171. OHLCV idea space remains closed — real lever is a data export."
---

# CandlestickAndVolatilityTimingTriage — 2026-07-03 research/triage pass

## Hypothesis & market rationale
This is a **triage report**, not a strategy candidate. Per spec 08 §2 the daily run must
surface 3–5 idea candidates and either test the differentiable ones or record why none are.
Today's search (SOURCES.md catalogs + arXiv/SSRN q-fin + practitioner literature) returned
only mechanisms that (a) map to an already-closed library family, (b) are directionless
(volatility magnitude, not entry signals → Risk-Governor domain), or (c) violate a hard
invariant. This report documents the pass so a future run does not re-surface these as fresh,
and captures one genuinely useful new data point: independent academic corroboration of the
library's closed single-bar / mean-reversion verdict.

This is the second consecutive triage-only run ([[2026-07-02-directional-ml-and-vol-forecasting-triage]]),
consistent with the OHLCV-exhaustion finding ([[2026-06-30-ohlcv-exhausted-final-closure]]).

## Sources
- [wangzhe3224/awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading) — FX/intraday subset resolves to ORB (breakout), time-series momentum (trend), and intraday reversal (mean-reversion), plus carry/cross-sectional momentum (multi-instrument, blocked-on-data). All closed or data-blocked in this library.
- [High Probability Candlestick Patterns for Forex 2026 (AlphaEx Capital)](https://www.alphaexcapital.com/forex/forex-market-analysis/candlestick-patterns/high-probability-candlestick-patterns-for-forex) — engulfing / two- and three-bar reversal patterns; the source itself concedes "without location and volume context, even engulfing bars are noise."
- Academic candlestick nulls (surfaced via search): Marshall, Young & Rose (2006) — 28 common candlestick patterns show no edge on Dow 30 over a decade; Orquín-Serrano et al. (2020) — EUR/USD 1-min candlestick signals show no significant advantage net of transaction costs.
- [Volume-driven time-of-day effects in intraday volatility models (Örebro WP 14/2025)](https://www.oru.se/globalassets/oru-sv/institutioner/hh/workingpapers/workingpapers2025/wp-14-2025.pdf) — decomposes intraday volatility into persistent, time-of-day, and Sunday-open components; a magnitude model, not a direction signal.
- [Intraday FX Volatility-Curve Forecasting with Functional GARCH (arXiv 2311.18477v3)](https://arxiv.org/html/2311.18477v3) — intraday conditional-volatility curve forecasting for EUR/USD; directionless.
- [Opening Range Breakout Strategy: Rules & Settings 2026 (Traders Mastermind)](https://tradersmastermind.com/trading-strategy-opening-range-breakout/) — practitioner ORB with prior-day / overnight-level and gap filters.

## Relation to prior library work
Each finding is dispositioned against the recorded closures (spec 08 §4.3 requires a stated
differentiator for any variant of a rejected idea; where none exists the idea is discarded):

1. **Candlestick reversal patterns — engulfing, three-bar reversal** → **closed.** These are
   single-/two-bar mean-reversion signals. The mean-reversion fade family is **7/7 closed
   across all anchor types**, including the single-bar microstructure anchor
   ([[2026-06-29-high-er-thrust-fade]]: signal statistically real at t=3.0 but gross +0.14p,
   18× below the ~2.6p cost gate). An engulfing/three-bar reversal is the same class of
   single-bar-shape signal with no new mechanism. The recorded failure mode (economically nil
   net of cost) applies directly. **New corroboration worth recording:** the external academic
   evidence surfaced today (Marshall-Young-Rose 2006; Orquín et al. EUR/USD 1-min) reaches the
   *same* verdict independently — candlestick patterns carry no edge net of cost — which raises
   confidence in the library's closure rather than reopening it. Discard, no trial.
2. **ORB / gap-and-go / gap-fade with prior-day & overnight-level filters** → **closed.**
   Directional breakout is edgeless under live-faithful fills across every level definition
   tried (session-OR, London-open, NR7, Asian-box, PDH/PDL, pivot); the ~65% double-break rate
   is the structural cause. Prior-day/overnight-level *filters* are subtractive on the −0.080R
   market-fill base with only ~24 trades of floor headroom (the filter-family wall confirmed by
   [[2026-06-22-volume-confirmed-orb]] and TrendAlignedORB). Weekend gap-fade is separately
   blocked-on-data (the M15 feed is continuous across week boundaries — no gap exists to trade).
   No differentiator. Discard.
3. **Volume-driven time-of-day volatility (Örebro 2025); functional-GARCH volatility curve
   (arXiv 2311.18477)** → **out of scope (directionless).** These forecast the *magnitude* of
   intraday moves, not their sign. They cannot produce an entry signal for the deterministic
   spine; at most they inform sizing, which the Risk Governor already owns (and which cannot
   manufacture directional edge). The *directional* time-of-day axis is separately closed
   ([[2026-06-17-intraday-seasonality-drift]]: every leg |t|<0.8, sub-pip drift). Discard.
4. **Carry / cross-sectional currency momentum (awesome-systematic-trading FX factor list)** →
   **blocked-on-data** (unchanged): needs a multi-currency universe + rate/swap data, neither
   in the EURUSD-M15 parquet. Already queued (`2026-06-24-currency-carry-xs-momentum`).

## Strategy spec
N/A — no candidate reached implementation. No indicator, strategy module, registry entry, or
test was added. The incumbent strategy class was not touched.

## Implementation notes
No code changes. No writes to `state/`. No live-path edits (`run.py`, `decide.py`, execution,
risk untouched). No `ConfigStore` calls. Repo left green. This is a docs-only run.

## Backtest results
None. No candidate was differentiable enough to justify a trial. Trial ledger unchanged
(cumulative trials remain **171**); W27 budget remains **10/10** (0 spent).

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|
| — | — | no candidate tested | — |

## Verdict
**Research/triage only — no trial spent.** No OHLCV-M15-testable, live-fillable, differentiable
candidate exists today. Every surfaced mechanism maps to a closed family or is directionless.
Consistent with the OHLCV-exhaustion closure ([[2026-06-30-ohlcv-exhausted-final-closure]]) and
the 2026-07-02 triage pass. No proposal filed. Budget and DSR bar preserved.

## Lessons
- **External academic evidence now independently corroborates the single-bar / mean-reversion
  closure.** The library killed candlestick-class reversals from its own probes
  ([[2026-06-29-high-er-thrust-fade]]); the published literature (Marshall-Young-Rose 2006;
  Orquín et al. EUR/USD 1-min) reaches the same net-of-cost null. When outside research and the
  in-house probes agree on a closure, that family should be treated as firmly shut — future
  triage should discard candlestick-pattern candidates at first pass without a probe.
- **Directionless volatility research keeps surfacing and must be dispositioned fast.** Functional
  GARCH / volume-driven time-of-day volatility are recurring search hits (also 07-02). They are
  Risk-Governor-domain magnitude models, never entry signals; a one-line disposition is correct
  every time. Recording them here should stop them re-appearing as "fresh."
- **Triage quality, not trial cap, remains the binding constraint** (spec 08 M5 review). Two
  consecutive zero-trial runs preserve budget and hold the rising DSR bar for a higher-conviction
  candidate — which, on current data, requires a data export to exist.

## Next steps
- **Unblocking action for Cayden (unchanged, escalating):** the real lever is a **longer-history
  and/or second-instrument export** (§8 backlog #4). It would revive TrendAlignedORB (the
  strongest re-test-on-longer-data candidate) and unblock the queued data-gated ideas
  (MacroNewsReleaseMomentum, MonthEndConditionalRebalancing, CurrencyCarryXSMomentum,
  CrossCurrencyLowVolumeReversal, M5TriggerORB).
- **Cadence:** the M5 recommendation to cut daily → 3×/week (Mon/Wed/Fri) still stands and still
  awaits Cayden's OK. Two more triage-only runs (07-02, 07-03) reinforce it: the OHLCV idea space
  is exhausted and daily cadence now yields near-certain triage-only passes.
- No new queue entries today — every surfaced idea was already queued (carry) or closed.
