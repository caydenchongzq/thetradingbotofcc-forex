---
id: 2026-06-16-vwap-stretch-reversion
name: VWAPStretchReversion
family: mean-reversion
status: tested-rejected
related: [2026-06-08-asian-sweep-fade, 2026-06-10-asian-sweep-fade-rr, 2026-06-15-resting-stop-and-market-entry, 2026-06-15-london-open-breakout-er]
sources:
  - "https://www.quantifiedstrategies.com/vwap-trading-strategy/"
  - "https://crosstrade.io/learn/trading-strategies/vwap-reversion"
  - "https://alvarezquanttrading.com/blog/efficiency-ratio-and-mean-reversion/"
  - "https://trendspider.com/learning-center/kaufman-efficiency-ratio/"
  - "https://forextester.com/blog/mean-reversion-trading/"
trials_used: 1
verdict: "Fade-to-the-session-VWAP is STRUCTURALLY negative on EURUSD M15, not just noise: −0.283R / PF 0.58 / 40.8% win in-sample, 0/6 WF folds profitable, stitched −0.280R (≈ in-sample, NO collapse → a stable adverse edge), lockbox −0.414R/PF 0.50 FAIL. Clears the 200-trade floor (338) — a NEW intraday anchor, not a subset — but the edge sign is wrong. Third distinct mean-reversion fade to fail (overnight-range 1R, 2R, now session-mean) → mean reversion on EURUSD M15 is closed across anchors; intraday extension CONTINUES more than it reverts even under a low-ER gate."
---

# VWAPStretchReversion — fade a stretch from the session VWAP back to the mean

## Hypothesis & market rationale
Session VWAP (volume-weighted average price since the session open) is the intraday "fair
value" that institutional execution is benchmarked against. The economic claim: VWAP-benchmarked
flow leans *against* large excursions from VWAP, so in a non-trending session a price stretched
far from VWAP tends to revert toward it. The edge, if real, is **liquidity provision into a
transient imbalance** — the other side is momentum/breakout traders chasing the excursion.

Falsifiable claim: in a ranging (low-ER) session, entering a **market** fade when price closes
≥ 1.5×ATR from the session VWAP, targeting a partial reversion (1.5R) with a 1.0×ATR stop, has
positive expectancy net of costs and clears the R6 gates + walk-forward + lockbox. If instead
the excursion is the *start* of a directional leg (continuation), the fade has negative
expectancy and the gates reject it.

## Sources
- QuantifiedStrategies — *VWAP Trading Strategy (Backtest)*: mean-reversion around VWAP "often
  shows a positive edge over long periods … but fails badly on strong trend days, making a
  regime filter mandatory" (https://www.quantifiedstrategies.com/vwap-trading-strategy/).
- crosstrade.io — *VWAP reversion strategy*: fade price ≥ 2σ from session VWAP, target a return
  to VWAP, daily anchor reset (https://crosstrade.io/learn/trading-strategies/vwap-reversion).
- Alvarez Quant Trading — *Efficiency Ratio and Mean Reversion*: ER as the regime switch between
  trend-following and mean-reversion logic
  (https://alvarezquanttrading.com/blog/efficiency-ratio-and-mean-reversion/).
- TrendSpider — *Kaufman Efficiency Ratio*: ER ∈ [0,1]; low = chop, high = clean trend; "to enter
  during consolidation, a low ER is preferred" (https://trendspider.com/learning-center/kaufman-efficiency-ratio/).
- ForexTester — *Mean Reversion Trading*: regime-dependence and cost sensitivity of FX reversion
  (https://forextester.com/blog/mean-reversion-trading/).

Hypothesis-only; no community code copied into `src/`. The implementation re-uses our own
audited engine machinery (`_regime`, `_blackout`, `manage`, the `ExitPlan` seam) and a new pure
`session_vwap` indicator. The backtester is the arbiter.

## Relation to prior library work
- **Differs from the CLOSED Asian sweep-fade family** ([[2026-06-08-asian-sweep-fade]] 1R +
  [[2026-06-10-asian-sweep-fade-rr]] 2R, both `tested-rejected`). Required §4.3 differentiation:
  the sweep-fade triggers on a **structural event** — a poke through a *fixed overnight-range
  high/low* that closes back inside — and its recorded failure mode is that fading a swept
  *level* stands in front of stop-run momentum (the sweep is often the start of expansion). This
  candidate has **no level and no failed-breakout requirement**; the trigger is a *continuous
  distance from the session VWAP* (a statistical mean), selecting a **different trade
  population** ("price is far from today's fair value in a chop session", not "price ran a key
  level"). So the sweep-fade failure mode was not assumed to carry over — the backtester decided.
  *It did carry over in spirit:* the family verdict now generalises across anchors (see Lessons).
- **Shares the inverted-ER ranging gate** with the fade family (ER < threshold) — that gate is
  NOT the novelty here (it is the fade family's a-priori choice); the **entry trigger** is.
- **Inherits the live-fillability discipline of [[2026-06-15-resting-stop-and-market-entry]]:**
  MARKET entry at the confirmed close (fill ≈ signal price), so the result is live-faithful from
  day one — no level-fill artifact is possible (the thing that faked the incumbent's +0.391R).
- **Escapes the 200-trade-floor trap** that bound the subtractive-filter family and killed
  [[2026-06-15-london-open-breakout-er]] on its own base (153): a session-mean stretch is an
  **additive, frequent** trigger → 338 trades, well clear of the floor. The floor was never the
  problem here; the **edge sign** is.

## Strategy spec
- **Anchor / session:** session VWAP accumulates from the **London open (08:00 London)**; trade
  window **08:00–16:00 London** — the liquid London + overlap hours only (deliberately avoiding
  the thin-hour spread that killed [[2026-06-09-late-session-drift]]).
- **VWAP:** `Σ(typical·volume)/Σ(volume)` over the in-window bars so far, `typical=(H+L+C)/3`,
  tick-volume from the parquet. New pure indicator `session_vwap` (fail-safe → `nan` on no usable
  volume → `NoSignal`).
- **Regime gate (INVERTED ER, a-priori):** pass iff not degenerate AND vol_state NORMAL AND
  `ER < er_threshold` (0.30) — mean reversion wants chop, not trend. Same NORMAL ATR band as the
  incumbent.
- **Entry:** when a closed bar's `|close − VWAP| ≥ stretch_atr_mult(1.5)×ATR`, **market** fade
  toward VWAP (short if above, long if below). **Edge-triggered**: only the bar that *first*
  closes beyond the band fires (revert-then-re-stretch re-arms it) — not every bar while
  stretched. `min_session_bars=8` (≥2h) before trading so the VWAP is meaningful.
- **Exit geometry (spec 08 §5.8 — pre-registered, NOT inherited):**
  - **stop** = `max(distance-to-this-bar's-extreme, 1.0×ATR)` — `atr_mult_sl=1.0`, a dedicated
    lever deliberately NOT the incumbent's 1.2: a reversion trade wants room just past the
    excursion's tip; it is only wrong if the stretch keeps extending into a genuine trend, which
    the 1.0×ATR-beyond-extreme stop catches cleanly.
  - **target** = **1.5R** fixed: entry is ≥1.5×ATR from VWAP and stop ≈1.0×ATR, so reverting
    toward the mean travels ≈1.5×ATR ≈ 1.5R. **R:R 1.5:1** (≥ 1:1 floor; the ≥2R rejections
    [[2026-06-07-tp-2r-sweep]] do not bind a 1.5R target *derived from the reversion distance*).
    Single full exit, no scaling, no break-even.
- **Levers if ever promoted:** `vwap.stretch_atr_mult`, `vwap.anchor/window_*`,
  `exits.atr_mult_sl`, `exits.target_r_multiples`.

## Implementation notes
- Additive only: new pure `session_vwap(highs, lows, closes, volumes)` in
  `src/engine/indicators.py`; new module `src/engine/strategy_vwap_reversion.py`
  (`class VWAPStretchReversion(SessionBreakoutER)` — `evaluate` replaced, shared machinery
  inherited, incumbent class untouched); one `register("VWAPStretchReversion", …)` line in
  `src/engine/registry.py`; dev config `config/dev/vwap_reversion.yaml`.
- Unit tests `tests/engine/test_vwap_reversion.py` (14): `session_vwap` value/weighting/degenerate;
  fires short on up-stretch & long on down-stretch with **market fill == close**; no-signal when
  not stretched; edge-trigger freshness; ranging-gate veto on a trend; outside-session; building
  VWAP; stand-down; insufficient history; exit geometry (stop = max(struct, 1.0×ATR), single 1.5R
  target, R:R==1.5); registry build (+ default `stretch_atr_mult==1.5`).
- Full `python -m pytest -q` green (369 tests). No writes to `state/config` HEAD; no live-path
  edits; no promotion. **No live-mirror needed** (no new manage semantics — single broker-side
  SL+TP, the validated seam).

## Backtest results
Command: `py scripts/run_backtest.py --config-file config/dev/vwap_reversion.yaml --walkforward
--trials 167` (cumulative trial count 167; 59,993 M15 bars, 2024-01 → 2026-05).

### In-sample (all gates) + A/B vs incumbent HEAD (identical harness & costs)
| metric | gate | VWAPStretchReversion | incumbent HEAD (live-faithful market) |
|---|---|---|---|
| trades | ≥ 200 | **338 — PASS** | 224 |
| expectancy | ≥ 0.10R | **−0.283R — FAIL** | −0.080R |
| win rate | — | 40.8% | 57.6% |
| profit factor | ≥ 1.30 | **0.58 — FAIL** | 0.56 |
| sharpe | ≥ 1.0 | **−2.04 — FAIL** | −2.00 |
| sortino | ≥ 1.5 | **−2.34 — FAIL** | −2.21 |
| DSR | ≥ 0.95 | **0.00 — FAIL** | 0.00 |
| maxDD | — | $11,123 | $9,370 |
| FTMO breaches | 0 | 0 — PASS | 0 |
| **verdict** | | **FAIL (5/7 gates)** | FAIL |

A/B: the VWAP fade is **worse than the (already-edgeless) incumbent on every axis that matters** —
expectancy −0.283R vs −0.080R, win 40.8% vs 57.6%, maxDD $11.1k vs $9.4k. More trades, more loss.

### Walk-forward (OOS)
| window | trades | exp(R) | PF | net$ |
|---|---|---|---|---|
| 2024 Q1 | 63 | −0.258 | 0.63 | −5588 |
| 2024 Q2 | 54 | −0.461 | 0.46 | −3935 |
| 2024 Q3 | 56 | −0.154 | 0.67 | −271 |
| 2024 Q4 | 64 | −0.187 | 0.59 | −139 |
| 2025 Q1 | 49 | −0.234 | 0.58 | −41 |
| 2025 Q2 | 33 | −0.445 | 0.47 | −16 |
| 2025 Q3–Q4 | 11 | −0.417 | 0.46 | −3 |

**0/6 scored folds profitable**, stitched OOS **−0.280R ≈ in-sample −0.283R (collapse=False)**,
severe fold (min −0.461R). Lockbox 2025-11→2026-05: **8 trades, −0.414R, PF 0.50 — FAIL**.
**WALK-FORWARD: FAIL.**

## Verdict
**tested-rejected.** Fails 5/7 in-sample gates, 0/6 WF folds, and the lockbox. No proposal filed.
Critically, in-sample ≈ stitched-OOS with **no collapse** — this is not an overfit that fell
apart out-of-sample; the negative expectancy is **stable across every quarter**, i.e. a genuine
*adverse* edge. Fading intraday extension on EURUSD M15 systematically loses, even from the
session mean and even under a low-ER ranging gate.

## Lessons
- **Mean reversion on EURUSD M15 is now closed across anchors.** Three distinct fade mechanisms
  have failed: overnight-range sweep at 1R ([[2026-06-08-asian-sweep-fade]]), the same at 2R
  ([[2026-06-10-asian-sweep-fade-rr]]), and now extension from the *session VWAP mean*. The
  anchor (structural level vs statistical mean) and the trigger (failed breakout vs σ/ATR stretch)
  did not matter — **the sign of the edge is the same**: on this instrument/timeframe, intraday
  extension **continues more than it reverts**. The low-ER "ranging" gate does not rescue it;
  selecting chop does not make the next move revert. Do not test further pure-fade variants
  without a *different* conditioning variable that is shown a priori to flip the continuation.
- **The win-rate arithmetic confirms it mechanically.** A 1.5R target needs >40% wins to break
  even *gross*; the fade delivered 40.8% gross → after ~1.6-pip round-trip cost the edge is
  negative (PF 0.58). This mirrors the [[2026-06-12-trend-pullback-ema]] finding that *win rate,
  not exit geometry, is the binding constraint* — only here the low win rate comes from fading
  (catching the continuation) rather than chasing.
- **Clearing the trade-floor is necessary, never sufficient — the dual of two recent rejections.**
  [[2026-06-14-trend-aligned-orb]] and [[2026-06-15-london-open-breakout-er]] died *below* the
  200-trade floor with arguably-fine edges; this one sailed past it (338) with a *broken* edge.
  Trade-count and edge-sign are orthogonal; an additive new anchor solves the former and says
  nothing about the latter.
- **Process win:** the new anchor was tested **live-faithfully from the first bar** (market fill ≈
  signal price) — there is no fill artifact to disentangle here, unlike the incumbent. The number
  is trustworthy precisely because the entry is one the live path can place.

## Next steps
1. **Reject**; close the pure mean-reversion fade direction (3/3 across anchors). Queue no further
   σ/ATR-stretch or sweep variants without a new continuation-flipping conditioner.
2. The open research space remains what [[2026-06-15-london-open-breakout-er]] identified: a
   *genuinely different mechanism* whose live fill ≈ its signal price and whose edge does not
   depend on the breakout-bar continuation. Both breakout and mean-reversion families are now
   broadly closed under live-faithful fills — favour **cross-sectional / conditioning signals**
   (e.g. a calendar/seasonality *gate* on an existing edge, or an event-conditioned filter) over
   another standalone directional intraday mechanism.
3. Newly queued ideas from this run's research (see INDEX idea queue): an **invoice-effect
   intraday-seasonality** directional bet (Breedon-Ranaldo 2012) — flagged *probe-first* given
   the [[2026-06-09-late-session-drift]] "small raw drift < cost" precedent; and a **high-ER**
   mean-reversion variant (fade only after a strong directional thrust, the Alvarez angle) —
   flagged *likely-redundant* given this 3/3 fade closure, to be probed not tested.
