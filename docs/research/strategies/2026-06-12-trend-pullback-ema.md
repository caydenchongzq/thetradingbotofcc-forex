---
id: 2026-06-12-trend-pullback-ema
name: TrendPullbackEMA
family: trend
status: tested-rejected
related: [2026-06-02-session-breakout-er, 2026-06-11-breakout-retest, 2026-06-07-tp-2r-sweep, 2026-06-07-intraday-ts-momentum, 2026-06-09-late-session-drift]
sources: ["https://www.tradingsim.com/blog/20-moving-average-pullback", "https://forexalgo-trader.com/resources/282-the-50-ema-pullback-strategy-a-clean-repeatable-approach-to-trend-trading", "https://fxnx.com/en/blog/master-20-ema-pullback-strategy", "https://www.quantifiedstrategies.com/moving-average-trading-strategy/"]
trials_used: 1
verdict: "Pullback-to-EMA continuation entry is a LOW-win-rate (27.4%) entry that a 2R target cannot rescue: -0.141R, PF 0.77, only 84 trades (<200 floor), 0/1 scored folds profitable, lockbox -0.064R PF 0.91 FAIL. The exact inverse of the incumbent's 73%-win 1R breakout; 'buy the dip in the trend' does not survive on EURUSD M15 overlap with costs."
---

# TrendPullbackEMA — enter a shallow pullback to a rising fast EMA in an ER-confirmed trend

## Hypothesis & market rationale
The incumbent enters on the bar that *closes* beyond the session opening range. A large body of
practitioner literature claims a complementary, arguably higher-quality continuation entry: in an
established trend, wait for a **shallow pullback to a fast EMA** and enter when price **resumes**
in the trend direction (closes back through the EMA and past the prior bar's extreme). Economic
story: an impulse leg attracts profit-takers and late counter-trend fades; when that supply/demand
is absorbed at the EMA and price reasserts, the trend's initiating flow is still in control and the
faders are offside. Falsifiable claim: pullback-resume entries during the London/NY overlap have a
positive, cost-surviving expectancy on EURUSD M15. **The arbiter — not the source — decides.**

## Sources
- 20-MA pullback continuation rules (slope filter + reversal-candle confirmation, intraday 1m/5m/15m):
  https://www.tradingsim.com/blog/20-moving-average-pullback
- 9/20/50-EMA pullback day-trading rules (trend filter, enter on resume close, stop beyond the EMA,
  target 1:2+): https://forexalgo-trader.com/resources/282-the-50-ema-pullback-strategy-a-clean-repeatable-approach-to-trend-trading
  and https://fxnx.com/en/blog/master-20-ema-pullback-strategy
- Moving-average strategy backtest survey (short-window EMA as an intraday momentum filter):
  https://www.quantifiedstrategies.com/moving-average-trading-strategy/

Community/retail sources are **hypothesis only** — the mechanism was re-implemented pure in our
engine; **no code was copied into `src/`** (spec 08 §5.6, §6).

## Relation to prior library work
- **Not a breakout subset** (the key differentiator from the rejected [[2026-06-11-breakout-retest]]):
  that idea was *subtractive on the incumbent's own breakouts* and suffered double-jeopardy
  (anti-selection + a halved trade count). This is a **new, independent signal source** — a
  structural retracement that fires on its own EMA geometry, not a filter carving the incumbent's
  trades. The differentiation is real; the failure mode, however, **converged** anyway (see Lessons).
- **Distinct from the rejected trend probes:** the edge claim is a *structural retracement in a
  confirmed trend*, not a serial-correlation effect ([[2026-06-07-intraday-ts-momentum]], early→late
  return corr 0.026) and not a clock/seasonal drift ([[2026-06-09-late-session-drift]]).
- **The ≥2R rejection on the incumbent ([[2026-06-07-tp-2r-sweep]]) was argued a priori not to bind**
  (different entry, tighter structural stop, discounted location). The backtest **refuted that
  argument**: the 2R target failed here too — for the orthogonal reason that the *win rate*, not just
  the geometry, collapses on a pullback entry (Lessons).

## Strategy spec
- **Session:** London/NY overlap, reuses `session.window_start/window_end` (13:00–16:00 London).
- **Regime gate (inherited, unchanged):** ER ≥ `er_threshold` (0.30) AND ATR in the NORMAL band —
  trend quality + fixed-R sizing safety.
- **Trend direction:** fast EMA (`ema_window`=20) rising/falling — `EMA[-1]` vs `EMA[-1-slope_lookback]`
  (`slope_lookback`=5) — and `last.close` on the trend side of the EMA.
- **Entry (one-shot per side per day):** a recent bar (within `pullback_lookback`=6) touched the EMA
  from the trend side (the retrace); the current bar **resumes** — closes back through the EMA AND
  beyond the prior bar's extreme. Market entry at that close.
- **Params → `ALLOWED_LEVERS` if ever promoted:** `pullback.ema_window`, `slope_lookback`,
  `pullback_lookback`, `atr_mult_sl`, `target_r`.

**Exit geometry (spec 08 §5.8 — chosen per mechanism, pre-registered, NOT inherited):**
- **stop = max(structural, 1.0×ATR).** Structural = just beyond the pullback extreme the entry leans
  on; the 1.0×ATR floor guards against thin-bar noise. *Tighter* than the incumbent's 1.2×ATR because
  a pullback enters at a favourable (near-support) location — justified a priori, not defaulted.
- **target = 2.0R (R:R = 1:2).** The discounted entry leaves room for the trend to resume toward and
  beyond the prior swing extreme; the literature's stated 1:2–1:3 target.
- **break-even after +1R via the incumbent `manage()`** — no new manage semantics, so **NO
  live-mirror flag** is required (contrast the time-box close of [[2026-06-09-late-session-drift]]).

## Implementation notes
- **Additive only.** New pure indicator `ema_series()` in `src/engine/indicators.py`; new module
  `src/engine/strategy_trend_pullback.py` (`TrendPullbackEMA`, subclasses `SessionBreakoutER` for the
  shared pure `_regime`/`_blackout`/`manage`; `evaluate` fully replaced); one `register("TrendPullbackEMA", …)`
  line in `src/engine/registry.py`. The incumbent class is **not modified**.
- **Tests:** `tests/engine/test_trend_pullback.py` (12 cases: long/short geometry, R:R = 1:2, stop ≠
  1.2×ATR, fail-safe rejections, regime-gate degenerate block, registry wiring, EMA-indicator
  alignment + fail-safe). **Full `python -m pytest -q` green** (290 passed).
- **No writes to `state/`, no live-path edits, ConfigStore untouched.** Pure function of
  (bars, now, context_bias, calendar); every degraded path ⇒ `NoSignal`.
- **Live-mirror needed?** No — `manage()` is the incumbent's already-live-mirrored break-even move.

## Backtest results
Command: `py scripts/run_backtest.py --strategy TrendPullbackEMA --walkforward --trials 163`
(`--trials 163` = cumulative 162 from [[2026-06-11-breakout-retest]] + this candidate).
A/B incumbent: `py scripts/run_backtest.py --walkforward --trials 163` (HEAD v4, same data/costs).

| metric | gate | candidate (TrendPullbackEMA) | incumbent HEAD (SessionBreakoutER) |
|---|---|---|---|
| trades (in-sample) | ≥ 200 | **84** ✗ | 224 ✓ |
| expectancy | ≥ 0.10R | **−0.141R** ✗ | +0.294R ✓ |
| win rate | — | 27.4% | 73.2% |
| profit factor | ≥ 1.3 | **0.77** ✗ | 1.99 ✓ |
| Sharpe (ann.) | ≥ 1.0 | **−0.63** ✗ | (pass) ✓ |
| Sortino | ≥ 1.5 | **−0.95** ✗ | (pass) ✓ |
| deflated Sharpe (trials=163) | ≥ 0.95 | **0.000** ✗ | (pass) ✓ |
| FTMO breaches | 0 | 0 ✓ | 0 ✓ |
| stitched OOS | no collapse | −0.164R | +0.283R |
| folds profitable | ≥ 60% | **0/1 scored** ✗ | PASS |
| lockbox (held out) | core gates pass | **−0.064R, PF 0.91 FAIL** ✗ | +0.324R, PF 2.15 PASS |
| **walk-forward verdict** | PASS | **FAIL** ✗ | PASS |

Walk-forward folds (candidate): +0.083 / −0.255 / −0.493 / +0.437 / −0.560 / −0.215 / −0.168 R —
negative in 5 of 7 windows, no fold structure that survives scoring.

## Verdict
**REJECT — tested-rejected.** The candidate fails every R6 gate except the FTMO hard gate, fails the
walk-forward, and fails the sealed lockbox. It is decisively dominated by the incumbent on the same
data and costs. **No proposal filed** (promotion requires ALL gates to pass — spec 08 §6).

## Lessons
1. **The pullback-resume entry is a structurally LOW-win-rate entry (27.4%) — the exact inverse of
   the incumbent's 73%-win 1R breakout.** Buying strength *after* a dip (close past the prior high
   following a retrace) systematically enters near a local high where, on EURUSD M15 overlap, price
   mean-reverts more often than it continues. The retail "buy the pullback" wisdom does **not** clear
   costs on this instrument/timeframe.
2. **A 2R target cannot rescue a sub-33% win rate.** 2R needs >33.3% wins just to break even before
   costs; at 27.4% the expectancy is structurally negative regardless of stop placement. This
   **reconfirms [[2026-06-07-tp-2r-sweep]] from a new entry mechanism**: EURUSD M15 overlap rewards
   *high-win-rate ~1R* structures, not *low-win-rate high-R* ones. The a-priori argument that a
   different entry would unbind the ≥2R failure was wrong — the binding constraint is the win rate the
   entry produces, not the exit geometry alone.
3. **A genuinely-new (non-subset) signal source still starved on the 200-trade floor (84 trades).**
   Unlike [[2026-06-11-breakout-retest]] this was NOT a carve-out of the incumbent's trades, yet the
   conjunction (ER-trend gate ∧ ATR-normal ∧ a deep-enough EMA touch ∧ a resume past the prior extreme
   ∧ one-shot/side/day) is so selective it yields ~35 trades/year. **Selectivity is the recurring
   killer of this research line** — breakout subset or not. Future trend candidates must estimate
   frequency *a priori* (≥200 trades over 2024-01..2026-05 ⇒ ≥~85/yr) before they are worth a trial.
4. **Process note that worked:** the EMA lags a trend by ~(window−1)/2 bars of slope, so a "shallow"
   pullback to a fast EMA is, on a clean trend, actually a *deep* retrace in price terms — the entry is
   rarer and worse-located than the literature's charts suggest. Worth remembering before proposing
   any further EMA-distance mechanism.

## Next steps
- **Trend family is now 0/3** on this dataset (serial-corr, time-of-day drift, structural pullback).
  Do not test another *selective* trend entry without an a-priori frequency estimate ≥ ~85 trades/yr.
- The still-open additive idea [[2026-06-11-breakout-retest|SecondEntryORB]] (re-break second entry to
  *raise* trade count) remains the more promising direction precisely because it attacks the recurring
  trade-floor failure instead of adding another selective entry. Queue stands.
- A *high-win-rate* pullback variant (1R target, tighter resume filter) is conceivable but would still
  face the 84-trade floor problem; not worth a trial until frequency is solved.
