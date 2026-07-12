---
id: 2026-07-12-optimization-methodology-and-ml-directional-triage
name: OptimizationMethodologyAndMLDirectionalTriage
family: other
status: idea
related: [2026-07-09-causal-ml-and-vol-of-vol-directional-triage, 2026-07-07-ml-feature-selection-and-leakage-methodology-triage, 2026-07-05-external-falsification-corroboration-triage, 2026-06-11-breakout-retest, 2026-06-22-volume-confirmed-orb, 2026-06-15-resting-stop-and-market-entry]
sources:
  - https://arxiv.org/abs/2602.10785
  - https://arxiv.org/pdf/2603.13638
  - https://arxiv.org/pdf/2605.23007
  - https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4135239_code2537556.pdf?abstractid=4080253
  - https://www.quantifiedstrategies.com/eurusd-trading-strategy/
  - https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/
trials_used: 0
verdict: "Daily pass 2026-07-12: 5 candidates surveyed, 0 differentiable+directional+OHLCV-M15-testable. (1) Double-OOS walk-forward window-length parameter optimization (arXiv 2602.10785, BTC EMA) = directionless METHODOLOGY, spec-06 optimizer/DSR domain — corroborates our WF+lockbox+trial-ledger gate stack, supplies no signal. (2) Performance-driven causal signal engineering under non-stationarity (arXiv 2603.13638) = learned causal ML on the decision path → pure-spine invariant #1 violation. (3) MadEvolve LLM-evolutionary trading-system optimization (arXiv 2605.23007) = AutoML/LLM meta-search, not a directional OHLCV mechanism + LLM-inline. (4) Intraday momentum/reversal in crypto (SSRN 4080253) = wrong asset; both families closed on EURUSD (trend + MR 7/7). (5) ORB + volatility-regime filter + retest + volume (practitioner consensus) = breakout closed across all level defs + retest tested-rejected [[2026-06-11-breakout-retest]] + vol-regime gate & volume filter closed [[2026-06-22-volume-confirmed-orb]]. No trial; W28 stays 10/10; trials stay 171. 9th consecutive triage-only run — 2026 literature is now dominated by optimization/overfitting METHODOLOGY that validates our gate stack rather than proposing signals; binding constraint remains the EURUSD-M15-only data surface."
---

# OptimizationMethodologyAndMLDirectionalTriage — daily research pass 2026-07-12

## Hypothesis & market rationale
Daily scan of the curated sources (`SOURCES.md`) + arXiv q-fin.TR/CP (2026 listings) +
practitioner catalogs (QuantifiedStrategies, Trade That Swing, LiteFinance) for a
**differentiable, directional, OHLCV-testable-on-EURUSD-M15** candidate that is (a) not
already closed by a prior library verdict, and (b) does not violate a hard invariant (pure
deterministic spine #1; live-fillable fill #3). As with the prior eight runs, the binding
question is not "is there a new idea?" — there is always fresh 2026 q-fin output — but "is
there one that is directional, testable on the single `state/parquet/eurusd_m15.parquet`, and
not a rename of an already-closed family or an invariant violation?"

## Sources
- **"A novel approach to trading strategy parameter optimization using double out-of-sample
  data and walk-forward techniques"** — arXiv:2602.10785 (q-fin, 2026). Parameterises the
  walk-forward *training/testing window lengths* (81 combinations, 1–28 days) for an EMA
  strategy on intraday BTC at six frequencies (1–60 min), ranked by a Robust Sharpe Ratio,
  with a strict double-out-of-sample split and single execution over the 21-month test period.
  Its thesis is about **evaluation methodology and overfitting from repeated OOS reuse**, not
  a new signal.
- **"Performance-Driven Causal Signal Engineering for Financial Markets under
  Non-Stationarity"** — arXiv:2603.13638 (2026). Learns/engineers directional signals via
  causal-inference feature construction under regime non-stationarity — a learned model on
  the decision path.
- **"MadEvolve: Evolutionary Optimization of Trading Systems with Large Language Models"** —
  arXiv:2605.23007 (2026). An LLM-driven evolutionary search that *generates and mutates
  trading systems* — an AutoML / meta-optimization layer, not a specific directional entry.
- **"Intraday Return Predictability in the Cryptocurrency Markets: Momentum, Reversal, or
  Both"** — Wen, Bouri, Xu, Zhao, SSRN 4080253. Documents intraday momentum **and** reversal
  in crypto (wrong asset class).
- **Practitioner ORB consensus** — QuantifiedStrategies (EURUSD strategy backtest), Trade
  That Swing (ORB "up 400% this year", strict rules), LiteFinance/ChartingLens: ORB with a
  volatility-regime filter, a full-candle-close-beyond-range rule, above-average volume, VWAP
  confirmation, "skip narrow choppy mornings", and an optional retest before entry.

The backtester — not any source — is the arbiter. None reached the backtester this run
(reasons below).

## Relation to prior library work
Every surveyed mechanism maps onto an existing library verdict or a hard invariant:

1. **Double-OOS walk-forward window-length optimization (arXiv 2602.10785).** This is a
   **directionless methodology** paper, not a strategy: it optimizes *how you split
   train/test windows* for an existing EMA rule and warns that repeated optimization on
   nominally-OOS data inflates expectations. It lands squarely in the **spec-06 optimizer /
   DSR-accounting domain**, not the directional-entry domain. Two takeaways, both
   corroborating rather than extending us: (a) our harness already enforces exactly this
   discipline — a sealed lockbox never tuned on, a walk-forward with a stitched-OOS collapse
   check, and a cumulative trial ledger feeding `--trials` into the DSR deflation; (b) the EMA
   trend rule it optimizes is itself in our **closed trend family** (0/3 + drift/serial-corr
   nulls). Supplies no testable EURUSD-M15 signal. Discard as a candidate; logged as gate-stack
   corroboration alongside the 07-07 methodology cluster
   ([[2026-07-07-ml-feature-selection-and-leakage-methodology-triage]]).

2. **Performance-driven causal signal engineering under non-stationarity (arXiv 2603.13638).**
   A learned causal-inference model producing directional signals on the decision path →
   violates **invariant #1** (deterministic, pure spine; no learned inline model), the same
   wall that disqualified every ML-directional / causal-inference candidate on
   07-02/04/05/06/09. Its "non-stationarity" framing does not change the invariant: even a
   correct causal model cannot sit inline on a live trade here. Discard.

3. **MadEvolve LLM-evolutionary trading-system optimization (arXiv 2605.23007).** An LLM that
   evolves whole trading systems is (a) a **meta-optimizer**, not a specific directional OHLCV
   mechanism — there is nothing to translate into a falsifiable EURUSD-M15 entry/exit spec —
   and (b) an **LLM inline in the strategy-generation loop**, against the same governance that
   keeps AI offline and human-gated (invariant #5: AI proposes, the backtester + a human
   dispose; it never authors a live-trading system unsupervised). Discard. (Note: our own
   research engine is the sanctioned, bounded version of "AI proposes strategies" — dev-
   isolated, one candidate at a time, arbiter-gated, never auto-promoted.)

4. **Intraday momentum/reversal in crypto (SSRN 4080253).** Wrong asset class (crypto), and
   both directions are already closed on EURUSD M15: intraday **momentum/continuation** is the
   closed trend family (raw-drift, vol-conditioned, cross-session, signed-semivariance all
   null — [[2026-07-01-signed-semivariance-momentum]]), and intraday **reversal** is the
   mean-reversion fade family, **7/7 closed across all anchors**
   ([[2026-06-30-twenty-day-turtle-soup]]). "Momentum, reversal, or both" on EURUSD M15 has
   been answered: neither, net of cost. Discard.

5. **ORB + volatility-regime filter + retest + volume (practitioner consensus).** Every
   component is already closed: the **breakout family is closed across all level definitions**
   under live-faithful fills (session-OR, London-open, NR7, Asian-box, PDH/PDL —
   [[2026-06-15-resting-stop-and-market-entry]]); the **retest-entry** variant is
   tested-rejected as *anti-selective* ([[2026-06-11-breakout-retest]], win 73%→43%, discards
   the immediate-continuation winners and halves trades below the floor); the **volume
   confirmation** has no selection edge on the market-fill base ([[2026-06-22-volume-confirmed-orb]]);
   the **volatility-regime / "skip narrow mornings" filter** is a subtractive veto on a base
   with only ~24 trades of floor headroom and is closed by mechanism argument
   ([[2026-06-28-trend-aligned-orb-market-fill-probe]], GARCHVolRegimeGate). VWAP confirmation
   is a sibling of the rejected VWAP-stretch reversion. The practitioner "up 400%" claim is a
   long-only equity-index (stock ORB) artifact of a trending period, explicitly flagged by the
   source itself as regime-dependent; it does not transfer to the 24h, small-tick,
   ~65%-double-break EURUSD-M15 surface. Discard.

## Strategy spec
Not reached — no candidate survived triage to an implementable, differentiated, directional,
OHLCV-M15 spec. (Exit-geometry section intentionally omitted: nothing to parameterise.)

## Implementation notes
No code written. No indicator added, no `Strategy` module, no `register()` line, no test
touched. `state/` untouched; live path (`run.py`, `decide.py`, execution, risk) untouched;
`ConfigStore.promote` not called. This run commits ONLY the new report + `INDEX.md`,
path-scoped, leaving any pre-existing uncommitted changes from other sessions as-found
(fail-safe: do not sweep another session's working tree into my commit).

## Backtest results
None. `trials_used: 0`. Cumulative trial count unchanged at **171**. W28 trial budget
unchanged at **10/10 remaining**.

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|
| — | — | no candidate reached the harness | — |

## Verdict
**Triage-only run — no candidate backtested.** All 5 surveyed mechanisms are disqualified
before spending a trial: 2 are directionless methodology/meta-optimization (window-length
optimization → DSR domain; LLM system-evolution → meta-search + invariant #5), 1 violates the
pure-spine invariant #1 (causal-ML directional signal), 1 is wrong-asset with both families
already closed on EURUSD, 1 is a fully-closed breakout+retest+filter stack. No proposal filed
(nothing passed; nothing was tested). This is the **9th consecutive triage-only run**.

## Lessons
- **The 2026 q-fin literature is pivoting from signals to overfitting/optimization
  methodology — and that methodology keeps validating our gate stack, not our search.** This
  run surfaced three optimization/AutoML papers (double-OOS window-length opt 2602.10785;
  causal signal engineering 2603.13638; MadEvolve LLM evolution 2605.23007) alongside the
  07-07 cluster (BFSA feature selection, Spurious Predictability, When-Alpha-Disappears). The
  common thread: modern papers increasingly show that apparent intraday edges are **artifacts
  of the search/evaluation procedure** (repeated OOS reuse, feature-selection bias, leakage) —
  the exact failure modes our sealed lockbox + walk-forward + cumulative-trial DSR deflation
  are built to catch. External literature is independently re-deriving our own methodology; it
  is not handing us new signals.
- **"Optimization methodology" is a distinct disqualification bucket, worth fast-pathing.**
  A paper that optimizes *how you tune/split/search* (window lengths, feature selection,
  evolutionary meta-search) is directionless by construction — it never picks a side — and
  belongs to the optimizer/DSR/Risk-Governor domains, never the directional-entry domain.
  Future triage can dispose of "parameter optimization / AutoML / walk-forward methodology"
  hits in one line, the same way "vol-of-vol / functional-GARCH" is fast-pathed as
  directionless-vol.
- **Crypto intraday momentum/reversal is a closed dead-end for us on two counts** — wrong
  asset AND both directional families already closed on EURUSD M15. Any "momentum, reversal,
  or both" framing has a pre-written verdict: neither survives cost on this surface.
- **Process note (unchanged, now 9×):** the binding constraint is the single EURUSD-M15
  parquet, not the idea pipeline. The still-open frontiers all need a data export; a longer
  EURUSD-M15 *directional* history will not help — 07-08's microstructural mechanism
  ([[2026-07-08-microstructural-trend-demise-corroboration-triage]]) argues the directional
  block is structural, not sampling-limited.

## Next steps
- **Cadence cut (9th reinforcement).** Nine consecutive triage-only runs on a fully-triaged
  single-instrument surface. Recommend dialing the `ftmo-research-engine` scheduled task from
  daily to ~2–3×/week (spec 08 §1 "cadence is a dial", M5 recommendation) until a new data
  surface lands. Awaits Cayden's explicit OK — not enacted here.
- **Prioritise the data-export lever, directional families first-in-line once it lands:** a
  news/macro-release timestamp calendar (unblocks [[2026-06-28-macro-news-release-momentum]]),
  a second instrument + rates (unblocks [[2026-06-24-currency-carry-xs-momentum]],
  cross-instrument confirmation), an equity daily feed (unblocks
  [[2026-06-30-month-end-calendar-effect]] conditional), options OI/strike (unblocks
  [[2026-06-28-ny-options-cut-gamma-pin]]).
- No queue additions this run — every surveyed idea maps to an existing closed/blocked entry
  or an invariant violation.
