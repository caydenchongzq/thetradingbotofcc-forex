---
id: 2026-07-02-directional-ml-and-vol-forecasting-triage
name: DirectionalMLAndVolForecastingTriage
family: other
status: idea
related: [2026-06-23-vol-conditioned-intraday-momentum, 2026-07-01-signed-semivariance-momentum, 2026-06-30-ohlcv-exhausted-final-closure]
sources: ["https://github.com/paperswithbacktest/awesome-systematic-trading", "https://link.springer.com/article/10.1007/s44163-025-00424-4", "https://arxiv.org/html/2311.18477v3", "https://arxiv.org/html/2503.00851v2", "https://arxiv.org/pdf/physics/0610023", "https://www.researchgate.net/publication/279276207_Eurusd_Intraday_Price_Reversal"]
trials_used: 0
verdict: "Daily research pass 2026-07-02: no differentiable, OHLCV-M15-testable, live-fillable candidate exists. Every mechanism surfaced maps to a closed family (breakout / MR 7/7 / trend-momentum incl. vol-conditioning & signed-jump) or violates hard invariants (ML = non-pure spine; vol-forecasting = directionless, Risk-Governor domain). No trial spent; budget preserved. OHLCV idea space remains fully closed — real lever is a data export."
---

# DirectionalMLAndVolForecastingTriage — 2026-07-02 research/triage pass

## Hypothesis & market rationale
This is a **triage report**, not a strategy candidate. Per spec 08 §2 the daily run must
surface 3–5 idea candidates and either test the differentiable ones or record why none are.
Today's search (SOURCES.md catalogs + arXiv q-fin + practitioner/quant literature) returned
only mechanisms that (a) map to an already-closed library family, (b) violate a hard invariant,
or (c) are directionless and therefore not entry signals. This report documents the pass so a
future run does not re-surface these as fresh, and records the two genuinely-new-but-untestable
findings for the queue.

## Sources
- [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading) — the FX/intraday subset resolves to ORB (breakout), time-series momentum (trend), and intraday reversal (mean-reversion) — all closed families in this library.
- [Directional forecasting for eight forex pairs against the US dollar using ML techniques (Springer, Discover AI 2025)](https://link.springer.com/article/10.1007/s44163-025-00424-4) — Random-Forest/XGBoost directional classifiers on OHLCV-derived features.
- [Intraday FX Volatility-Curve Forecasting with Functional GARCH (arXiv 2311.18477v3)](https://arxiv.org/html/2311.18477v3) — intraday conditional-volatility curve forecasting.
- [Forecasting realized volatility, path-dependent perspective (arXiv 2503.00851v2)](https://arxiv.org/html/2503.00851v2) — path-dependent volatility (PDV) forecasting.
- [Unexpected volatility and intraday serial correlation (arXiv physics/0610023)](https://arxiv.org/pdf/physics/0610023) — return serial correlation conditioned on a volatility surprise.
- [EURUSD Intraday Price Reversal (ResearchGate 279276207)](https://www.researchgate.net/publication/279276207_Eurusd_Intraday_Price_Reversal) — intraday reversal anchor.

## Relation to prior library work
Each finding is dispositioned against the recorded closures (spec 08 §4.3 requires a stated
differentiator for any variant of a rejected idea; where none exists the idea is discarded):

1. **ORB / breakout catalog entries** → **closed.** Directional breakout is edgeless under
   live-faithful fills across every level definition tried (session-OR, London-open, NR7,
   Asian-box, PDH/PDL, pivot) — the ~65% double-break rate is the structural cause. No new
   level definition changes the mechanism. Discard.
2. **Time-series / intraday momentum** → **closed.** Trend/momentum is closed across
   raw-drift, vol-conditioning ([[2026-06-23-vol-conditioned-intraday-momentum]], gradient
   INVERTED vs equities, corr −0.12), cross-session ([[2026-06-29-asian-session-drift-signal]],
   corr 0.046), and variance-decomposition ([[2026-07-01-signed-semivariance-momentum]],
   |corr|≤0.03). Discard.
3. **Intraday price reversal** (ResearchGate; arXiv physics/0610023 vol-surprise-conditioned
   continuation) → **closed by transitivity.** Mean-reversion fade is 7/7 closed across all
   anchor types; a vol-surprise conditioner on continuation is a variant of vol-conditioned
   momentum, which INVERTED (corr −0.12) — the recorded failure mode (EURUSD does not revert
   or continue predictably on any anchor/scale in 2024–2026) applies directly. No stated
   differentiator survives. Discard.
4. **ML directional forecasting** (Springer 2025) → **rejected by invariant #1.** A trained
   RF/XGBoost classifier carries learned weights = hidden state and a training pipeline; the
   deterministic spine requires `evaluate/manage` to be a *pure, hand-specified* function of
   `(bars, now, context_bias, calendar)`. Out of architectural scope for this catalog. Queue
   as a note, not a candidate.
5. **Volatility-curve / path-dependent volatility forecasting** (arXiv 2311.18477, 2503.00851)
   → **directionless.** These forecast conditional volatility (magnitude), not direction. The
   Risk Governor already owns sizing and the incumbent already gates on ATR-floor/ceiling +
   ATR-percentile + ER, so an intraday vol-curve forecast has no identified incremental entry
   signal. Same disposition as [[2026-07-01-order-flow-entropy-magnitude]] (magnitude, not
   direction). Not an entry candidate.

## Strategy spec
N/A — no candidate selected for implementation. No exit geometry to pre-register (spec 08 §5.8),
because no directional, live-fillable, OHLCV-testable mechanism survived triage.

## Implementation notes
No code written. `indicators.py`, `registry.py`, and the incumbent strategy are untouched.
No writes to `state/`. No live-path edits. `python -m pytest -q` unchanged (green). No proposal
JSON written (nothing passed gates — nothing was tested).

## Backtest results
None. No trial was spent (§4.3: re-testing a family+failure-mode already recorded, without a
stated differentiator, is forbidden — it burns cumulative DSR budget for nothing). Cumulative
trial count stays **171**; W27 budget stays **0/10 spent (10 remaining)**.

## A/B vs incumbent HEAD
N/A (no candidate).

## Verdict
**No trial.** The 2024–2026 EURUSD M15 OHLCV idea space remains fully exhausted (consistent with
[[2026-06-30-ohlcv-exhausted-final-closure]] and the seven daily runs since). Today's search
produced zero directional, live-fillable, OHLCV-testable mechanisms not already closed. The two
genuinely-new findings are untestable on current data/architecture: ML directional forecasting
(invariant-conflicting) and intraday vol-curve/PDV forecasting (directionless).

## Lessons
- The web-search surface has converged: FX-intraday catalogs now return only ORB, TS-momentum,
  and intraday-reversal — the three families this library has already closed across every
  anchor and conditioner. Fresh OHLCV *mechanisms* are no longer appearing; new papers are
  either ML architectures (spine-incompatible) or volatility-forecasting (directionless).
- A "volatility surprise" or "unexpected-volatility" conditioner on continuation is **not** a
  new family — it is vol-conditioned momentum, already inverted-and-closed (06-23). Future runs
  should map any "conditioned continuation/reversion" idea onto the existing vol-conditioning
  and signed-jump closures before considering a probe.
- Directionless volatility work (functional GARCH, PDV, order-flow entropy) belongs to the Risk
  Governor / sizing domain, not the entry engine. Record such papers but do not queue them as
  entry candidates.
- The binding constraint is **not** trial budget (10/10 free this week) — it is the absence of a
  differentiable hypothesis. Manufacturing a trial to "use budget" would violate §4.3 and raise
  the DSR bar against every future real candidate.

## Next steps
- Hold trials. Do not test any breakout / mean-reversion / trend variant on current data without
  a genuinely new conditioner backed by a positive a-priori parquet probe.
- The real lever remains a **data export** (blocked-on-data queue, unchanged): longer history
  (re-test TrendAlignedORB — the strongest floor-bound candidate), a second instrument
  (cross-instrument confirmation, currency carry/XS-momentum, cross-currency low-volume reversal),
  M5 bars (M5-trigger ORB), a macro-release calendar (MacroNewsReleaseMomentum), an equity-return
  feed (MonthEndConditionalRebalancing), and options OI (NYOptionsCutGammaPin). These await
  Cayden's export decision.
