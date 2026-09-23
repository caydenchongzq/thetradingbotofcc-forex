---
id: 2026-07-08-microstructural-trend-demise-corroboration-triage
name: MicrostructuralTrendDemiseCorroborationTriage
family: other
status: idea
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-24-asian-range-london-breakout, 2026-07-01-signed-semivariance-momentum, 2026-07-05-external-falsification-corroboration-triage, 2026-07-07-ml-feature-selection-and-leakage-methodology-triage]
sources:
  - https://arxiv.org/abs/2607.01550
  - https://arxiv.org/pdf/2605.04004
  - https://arxiv.org/pdf/2605.17724
  - https://researchpaperfilteropen.vercel.app/
  - https://www.quantifiedstrategies.com/algorithmic-trading-strategies/
trials_used: 0
verdict: "Daily pass 2026-07-08: 5 candidates, 0 differentiable+directional+OHLCV-testable. HEADLINE: Bouchaud/Kurth/Eisler/Rej (arXiv 2607.01550, 2 Jul 2026) give a MICROSTRUCTURAL MECHANISM for our entire breakout/trend closure — post-2008 short-term trend PnL collapsed specifically on SMALL-TICK, HFT-market-made instruments (EURUSD is exactly this class) because HFT liquidity-withdrawal in front of predictable directional flow broke the market-impact feedback loop that sustained the trend edge. This is the causal generator of the ~65% double-break 'touch tax' we keep hitting. Other 4: market-by-order Volume-Profile ORB (blocked-on-data, tick/order-flow); LSTM-vs-GBM MNQ (invariant #1 + null); functional-GARCH FX vol (directionless, Risk-Governor); retail ORB/momentum (breakout/trend closed). No trial; W28 stays 10/10; trials stay 171. 7th consecutive triage-only run."
---

# MicrostructuralTrendDemiseCorroborationTriage — daily research pass 2026-07-08

## Hypothesis & market rationale
Daily scan of the curated sources (`SOURCES.md`) + arXiv q-fin.TR/CP July-2026 + practitioner
catalogs for a **differentiable, directional, OHLCV-testable-on-EURUSD-M15** candidate that is
not already closed by a prior library verdict and does not violate a hard invariant. As with the
prior six runs, the binding question is not "is there a new idea?" (there always is) but "is there
one that is (a) directional, (b) testable on the single EURUSD-M15 parquet, and (c) not a rename of
a closed family?"

## Sources
- **Kurth, Eisler, Rej, Bouchaud — "Is Trend Still Your Friend?: A Microstructural Account of the
  Demise of Short-Term Trend-Following"** — arXiv:2607.01550 (q-fin.TR, submitted 2 Jul 2026).
  ~100 liquid futures 1995–2025 + a CTA proxy. Central finding: post-2008 short-term trend PnL
  collapsed **on small-tick contracts across all signal horizons**, intact on large-tick ones; the
  discriminating cross-sectional variable is **volatility-normalised tick size**, not asset class or
  liquidity. Mechanism: trend profits are sustained by a self-fulfilling market-impact feedback loop
  (signal → directional trade → impact reinforces the move); the post-crisis shift to HFT-dominated
  market making, whose **liquidity-withdrawal behaviour in front of predictable directional flow**
  is far worse on sparse (small-tick) limit order books, broke that loop on small-tick instruments.
- **Mesfin (2026) — "Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic
  Falsification Study"** — arXiv:2605.04004. Already recorded 2026-07-05; re-surfaced. Independent
  pre-specified-gate/OOS/net-of-cost falsification of 14 OHLCV signal families → zero clear edge.
- **"Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ"** —
  arXiv:2605.17724. ML next-session direction; invariant #1 (non-pure spine) + reported ~coin-flip.
- **Market-by-order Volume-Profile Value-Area / opening-order-flow-delta ORB study** (2026,
  researchpaperfilteropen.vercel.app): 71.1% follow-through to 0.5× range, directional asymmetry at
  deep targets. Needs market-by-order/tick + Volume-Profile — not in the M15 OHLCV parquet.
- QuantifiedStrategies / ForexTester / LiteFinance 2026 retail catalogs: ORB, volatility breakout,
  volume-confirmed momentum, timeframe-stacked trend — all closed families.

## Relation to prior library work
Every candidate this run dedupes into an existing verdict:

- **Bouchaud et al. 2607.01550 → NOT a candidate; it is a MECHANISM for our closures.** It is a
  falsification-corroborating result, not a tradable signal. Its importance: it supplies the *causal
  generator* we had only characterised empirically. Our findings —
  [[2026-06-15-resting-stop-and-market-entry]] (the incumbent's edge is a level-fill artifact; both
  live-faithful fills lose), the 4× live-faithful breakout closure
  ([[2026-06-24-asian-range-london-breakout]] and the double-break "touch tax"), and the full
  trend/momentum closure across raw-drift/vol-conditioning/cross-session/variance-decomposition
  ([[2026-07-01-signed-semivariance-momentum]]) — are all **short-horizon directional-persistence on
  a small-tick, HFT-market-made instrument (EURUSD)**. That is precisely the cell in which Bouchaud
  et al. find the edge has structurally collapsed, and their HFT-liquidity-withdrawal-in-front-of-
  predictable-flow channel *is* our ~65% double-break rate described from the demand side. This
  upgrades the trend/breakout closure from "internal empirical finding + one external falsification
  ([[2026-07-05-external-falsification-corroboration-triage]])" to "internal + external-empirical +
  a peer-level microstructural **mechanism** that specifically predicts EURUSD should be dead." It
  also implies the block is **structural, not data-length-bound** for the directional families: a
  longer export would not revive short-horizon EURUSD trend/breakout, because the impact loop that
  once sustained it no longer closes on a small-tick HFT book. (Caveat: it does NOT speak to the
  filter/selectivity families or to non-directional/event-driven mechanisms, which remain the only
  open frontiers — all currently blocked-on-data.)
- **Market-by-order Volume-Profile ORB** → breakout family CLOSED + needs tick/order-flow data;
  dedupes to [[2026-06-22-volume-confirmed-orb]] (tick-volume ≠ real volume) and the blocked-on-data
  order-flow queue ([[2026-07-01-order-flow-entropy-magnitude]]).
- **LSTM-vs-GBM MNQ** → invariant #1 (pure-spine) violation + null; same disposition as the
  06-30/07-02/07-06 ML entries.
- **Functional-GARCH FX vol** (recurring) → directionless, Risk-Governor domain; deduped 07-02/04/06.
- **Retail ORB / volatility-breakout / volume-momentum / timeframe-stacked trend** → breakout & trend
  families closed under live-faithful fills.

Per spec 08 §4.3, a variant of a rejected family must state what is different and why the failure
mode does not apply. None of the five clears that bar: three are closed-family renames, one violates
a hard invariant, one is blocked-on-data. **No candidate selected; nothing new to queue** (all map to
existing queue entries).

## Strategy spec
N/A — no candidate advanced to a spec. No exit geometry defined (no strategy built).

## Implementation notes
**No code written.** No indicator, strategy, registry, or test changes. No writes to `state/`, no
touch of the live path (`run.py`, `decide.py`, execution, risk), no `ConfigStore.promote`. Repo left
green (no edits to `src/` or `tests/`; existing pytest state unchanged). Trial ledger not appended
(no backtest run).

## Backtest results
None. No trial consumed. `--trials` unchanged at **171**. W28 budget **10/10 remaining**.

## Verdict
**Triage-only, no trial.** 0 of 5 candidates differentiable + directional + OHLCV-testable. The
run's substantive output is the **mechanistic corroboration** of the standing breakout/trend closure
by Bouchaud et al. (2026): EURUSD's small-tick HFT-market-made microstructure is the named cause of
the short-horizon directional-edge collapse we have measured 15+ ways. No proposal filed (promotion is
human-only and there is nothing to promote).

## Lessons
1. **The directional closure now has a peer-reviewed-tier causal mechanism, not just correlational
   nulls.** Bouchaud et al. identify volatility-normalised tick size as the variable that killed
   short-term trend post-2008, via HFT liquidity-withdrawal in front of predictable flow. EURUSD is
   squarely in the dead (small-tick) cell. Our repeated "touch tax" / ~65% double-break finding is
   the same phenomenon observed from the fill side. **Implication for triage:** stop treating the
   directional-breakout/trend closure as possibly data-length-bound — for these families it is
   *structural*. A longer or second-instrument export is worth it for the **filter, event-driven,
   and cross-sectional** families (still genuinely blocked-on-data), NOT to revive short-horizon
   EURUSD trend/breakout, which the mechanism predicts stays dead regardless of sample.
2. **7th consecutive triage-only run.** The 2026 literature keeps arriving as either (a) our own
   invariants restated (07-07 leakage/spurious-predictability papers) or (b) mechanistic explanations
   of our own closures (this run). Idea *supply* is not the constraint; the **EURUSD-M15-only OHLCV
   data surface** is. Every genuinely-new frontier (market-by-order flow, multi-instrument carry/XS,
   macro-event calendar, M5 trigger, conditional-calendar equity feed) is blocked-on-data.
3. **Process holding.** No trial spent on any of the 5; each was disposed by a one-line dedupe or an
   invariant check before touching the parquet. Budget discipline intact (W28 10/10; trials 171).

## Next steps
- **No re-test queued** — all five map to existing verdicts/queue entries; nothing new to add.
- Reinforces (7th time) the **cadence-cut** recommendation from the M5 review
  ([[m5-review-2026-06-21]]): daily research on a closed, single-instrument surface yields
  triage-only runs; 2–3×/week would lose no signal.
- **Data-export lever unchanged and now sharper:** prioritise exports that open the *still-open*
  frontiers — (1) a **second instrument + rates/swap** feed for carry / cross-sectional currency
  momentum and cross-instrument confirmation; (2) a **macro-release calendar** for
  event-driven momentum ([[2026-06-28-macro-news-release-momentum]]); (3) **M5 bars** for the
  multi-timeframe ORB trigger. Do NOT prioritise a merely-longer EURUSD-M15 export for the
  directional families — Bouchaud et al. imply that edge is structurally gone on this instrument.
