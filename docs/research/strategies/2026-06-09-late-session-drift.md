---
id: 2026-06-09-late-session-drift
name: LateSessionDrift
family: trend
status: tested-rejected
related: [2026-06-02-session-breakout-er, 2026-06-08-asian-sweep-fade, 2026-06-08-london-fix-reversal, 2026-06-07-intraday-ts-momentum]
sources: ["https://github.com/paperswithbacktest/awesome-systematic-trading", "https://www.quantifiedstrategies.com/nr7-trading-strategy-toby-crabel/", "https://forextester.com/blog/momentum-trading-strategies/", "https://tradethatswing.com/analyzing-eur-usd-volatility-for-day-trading-purposes/"]
trials_used: 1
verdict: "Real but un-harvestable: +2.3 pip/night raw drift, but the thin liquidity that creates it brings a 1.24-pip entry spread + 0.82-pip slippage; net -0.146R in-sample, 1/7 WF folds, lockbox -0.232R PF 0.40. Costs and stop-noise consume a sub-ATR signal."
---

# LateSessionDrift — harvesting the late-session (21:00–00:00 London) EURUSD up-drift

## Hypothesis & market rationale
EURUSD shows a persistent **positive price drift in the thin-liquidity late-London /
NY-afternoon window (~21:00–00:00 London ≈ 20:00–23:00 UTC)**. Economic rationale: after the
16:00 London WM/R fix and through the 17:00 NY options/settlement cut, order books thin out;
residual benchmark-rebalancing and carry-roll demand for EUR can push price in one direction
with little opposing flow. Falsifiable, pre-registered prediction: going **long each night at
21:00 London and exiting ~3h later** earns a positive, cost-and-stop-surviving R-expectancy
that holds out-of-sample and on the sealed lockbox. The null (and the recorded outcome): the
drift is too small relative to ATR-scaled risk and is eaten by the wide late-session spread.

## Sources
- paperswithbacktest / awesome-systematic-trading — intraday-seasonality and
  market-intraday-momentum strategy family (hypothesis source only; no code copied).
- QuantifiedStrategies, *NR7 / Toby Crabel* and ForexTester *momentum* write-ups — volatility
  /session-timing mechanisms surveyed during triage (re-implemented pure if used; not used
  verbatim).
- TradeThatSwing EUR/USD volatility note — late-session liquidity/spread context.
- The signal itself was found **in-sample** via an hour-of-day mean-return t-stat scan over
  `state/parquet/eurusd_m15.parquet` (London hours 21/22/23 carried mean +0.26…+0.34 pip/bar,
  t≈4.0–4.7). This is an explicit multiple-comparison process; the cumulative-trial DSR
  penalty (trials=160) and the sealed lockbox are the safeguards, and both rejected it.

## Relation to prior library work
- **New family vs the incumbent** [[2026-06-02-session-breakout-er]] (overlap opening-range
  breakout): different session, different trigger (time-of-day, not a range break), different
  exit (time-box, not SL/TP-only). HEAD was untouched (dev-isolated); the A/B below confirms
  HEAD still passes every gate.
- **Differs from** [[2026-06-08-asian-sweep-fade]] (rejected fade): that was mean-reversion
  against a sweep; this is a directional drift-capture. Failure modes are unrelated.
- **Supersedes two queued ideas killed at the free probe stage this run** (no trial spent on
  them — triage, not backtests):
  - [[2026-06-08-london-fix-reversal]]: the post-fix reversion is ~0.2 pip to 18:00 London
    (below cost), win-rate 51.8% at k=0.5×ATR; the only positive subset (month-end, 19 days)
    is far below the 200-trade gate floor. **Probe-rejected** — do not test without a
    materially different mechanism.
  - [[2026-06-07-intraday-ts-momentum]]: early-session→late-session return correlation is
    0.026 (mean +0.25 pip, < cost); **probe-rejected**.
  - An *Asian-range breakout continuation* (opposite of the rejected fade) also probed
    negative (−0.33 pip/trade) and was discarded.

## Strategy spec
- **Universe / data:** EURUSD M15 only (`state/parquet/eurusd_m15.parquet`, 2024-01..2026-05).
- **Entry:** one **LONG market** order per day, on the M15 bar that OPENS at `entry_time`
  (21:00 London). `evaluate` is called by the engine only when flat, so this is inherently
  one-shot/day.
- **Regime gate:** the incumbent's **NORMAL ATR band only** (vol_state == normal, i.e.
  4 < ATR < 22 pips and percentile within [0.20, 0.90]); the ER **trend gate is intentionally
  dropped** — the drift is a flow phenomenon, not a trend-regime one (a-priori decision).
- **Exit (primary):** **time-box** — flat after `hold_bars` = 12 M15 bars (~3h, ≈00:00
  London), implemented as an explicit `strategy.manage()` `close_all` (the engine's documented
  time-stop hook), with a London-time backstop for data-gap robustness.
- **Params** (a-priori, deliberately **not** swept; would become `ALLOWED_LEVERS` only if it
  had passed): `drift.entry_time=21:00`, `drift.hold_bars=12`, `drift.atr_mult_sl=1.5`,
  `drift.target_r=1.0`.

**Exit geometry (spec 08 §5.8 — chosen per mechanism, not inherited):**
- **Stop = 1.5×ATR** (≈14 pip). Rationale: the edge is a slow multi-hour drift; the stop is a
  disaster-guard, not the primary exit, so it must be **wider** than the incumbent's 1.2×ATR
  to avoid noising out of a gradual move. (Pre-test diagnostic confirmed 1.2×ATR was worse.)
- **Target = 1.0R** (R:R = 1:1 floor). Rationale: the real exit is the time-box; a 1R TP only
  banks an outsized overshoot and is rarely hit because mean drift (~2.3 pip) ≪ stop (~14 pip).
  The single-1R machinery is reused **with** justification, not by default.

## Implementation notes
- Additive only: `src/engine/strategy_late_drift.py` (`LateSessionDrift`, subclasses
  `SessionBreakoutER` for shared pure `_regime`/`_blackout`/tz; `evaluate` + `manage` fully
  replaced; incumbent class unmodified). One `register("LateSessionDrift", …)` line in
  `src/engine/registry.py`.
- Tests: `tests/engine/test_late_drift.py` (11) + `tests/backtest/test_late_drift_harness.py`
  (2, incl. a check that the exit is `manage_close`, not SL/TP). **Full `pytest -q` green
  (253 passed).** No writes to `state/` (other than the sanctioned trial-ledger append); no
  live-path edits.
- **LIVE-MIRROR FLAG (spec 08 §5.4):** the time-boxed exit is a **new `manage()` semantic** vs
  the incumbent (which only moves SL to BE). The backtester models it exactly and the live
  bridge `decide_manage` maps `close_all`→`close`, but the live runner has not exercised a
  manage-close on a real position. A config naming this strategy would need a human-supervised
  live-mirror session before promotion. **Moot here — it failed; not promoted.**

## Backtest results
Command: `py scripts/run_backtest.py --strategy LateSessionDrift --walkforward --trials 160`
(`--trials 160` = cumulative: 80 from the latest library report [[2026-06-08-asian-sweep-fade]]
+ 79 combos from the 2026-06-08 weekly sweep + this candidate; the ledger file undercounts, so
the count is reconstructed from reports per the standing note).

**In-sample R6 gates (full sample):**

| Gate | Threshold | Value | Pass |
|---|---|---|---|
| expectancy_r | ≥ 0.10 | **−0.146** | ✗ |
| profit_factor | ≥ 1.30 | **0.58** | ✗ |
| sharpe | ≥ 1.0 | **−2.04** | ✗ |
| sortino | ≥ 1.5 | **−2.39** | ✗ |
| sample_size | ≥ 200 | 394 | ✓ |
| deflated_sharpe (trials=160) | ≥ 0.95 | **0.000** | ✗ |
| ftmo_no_breach | 0 | 0 | ✓ |

**Walk-forward (OOS):** 1/7 folds profitable (only 2024-Q1: +0.214R); stitched OOS −0.124R;
**severe fold** −0.271R; 6 weak folds. Verdict FAIL.

| window | trades | exp(R) | PF |
|---|---|---|---|
| 2024-01..04 | 19 | +0.214 | 2.15 |
| 2024-04..07 | 26 | −0.271 | 0.28 |
| 2024-07..10 | 29 | −0.122 | 0.51 |
| 2024-10..2025-01 | 43 | −0.198 | 0.49 |
| 2025-01..04 | 55 | −0.163 | 0.49 |
| 2025-04..07 | 61 | −0.082 | 0.69 |
| 2025-07..11 | 81 | −0.122 | 0.64 |

**Lockbox (held out 2025-11-01..2026-05-29, never tuned on):** trades=80, exp **−0.232R**,
PF **0.40**, sharpe −3.83 → **FAIL**. Notably this is the window where the *raw* drift looked
strongest (probe: +3.6–4 pip/quarter) — yet it is the worst lockbox fold, which is the cleanest
possible refutation that the raw drift is tradeable.

**Cost decomposition (the lesson, n=394):** mean gross +0.239 pip → mean **net −0.461 pip**.
Mean **spread at entry = 1.236 pip** (vs ~0.25 pip in liquid hours), entry slippage 0.82 pip,
commission ≈ $19/trade. Exit-reason R-asymmetry: tp (93) +0.764R · time-box (226) −0.027R ·
**sl (74) −1.079R** — the stop-outs swamp the take-profits.

## A/B vs incumbent HEAD
Same data, same harness, trials=160.

| | in-sample exp | PF | Sharpe | DSR | verdict |
|---|---|---|---|---|---|
| **HEAD SessionBreakoutER v4** | **+0.294R** | 1.99 | 3.36 | 0.989 | PASS all gates |
| LateSessionDrift | −0.146R | 0.58 | −2.04 | 0.000 | FAIL all but 2 |

The candidate is dominated on every axis and does not (and cannot) regress HEAD — it is a
separate, unpromoted registry entry; HEAD was re-run untouched and still clears every gate.

## Verdict
**REJECT.** Fails in-sample (6/7 gates), walk-forward (1/7 folds, severe fold, lockbox FAIL).
The late-session up-drift is a *real* economic effect (+2.3 pip/night raw, 64.7% up-nights,
positive in 9/10 calendar quarters) but is **not harvestable** on EURUSD M15.

## Lessons
1. **A raw-pip edge is not an R-edge.** A genuine +2.3 pip/night signal is ~0.16R against the
   ~14-pip ATR-scaled stop a 3-hour hold needs to avoid noise-outs — and once intraday
   stop-outs (full −1R) are weighed against time-box winners (fractional +R), the per-trade
   R-expectancy is ~0 even **before** costs (cost-free diagnostic: +0.003R unstopped). Judge
   candidates in R through the arbiter, never on headline pips — reaffirms the EXIT_MODEL /
   [[2026-06-07-tp-2r-sweep]] precedent.
2. **The drift and its cost share a cause — thin liquidity.** The very illiquidity that lets
   the drift exist imposes a **1.24-pip entry spread (5× the daytime average) + 0.82-pip
   slippage**. You cannot collect a thin-book drift without paying the thin-book spread. Any
   "trade the quiet hours" idea must be costed at *that hour's* spread, not the dataset mean.
3. **Recency of a raw signal is a trap.** The most recent window had the largest raw drift but
   the worst lockbox R — strong evidence the apparent strengthening was trend/vol drift, not a
   growing edge.
4. **t-stat mining needs the DSR/lockbox backstop, and it worked.** An hour-of-day scan will
   always surface *some* significant-looking hour; the trials=160 DSR penalty and the sealed
   lockbox correctly killed it. Keep feeding the cumulative trial count.

## Next steps
- **Do not** rescue by sweeping stop width / hold length: the unstopped R-edge is ~0, so no
  exit-geometry tuning makes it pass, and sweeping would only burn DSR budget (spec §4.3).
- Mark [[2026-06-08-london-fix-reversal]] and [[2026-06-07-intraday-ts-momentum]] as
  **probe-rejected** in the idea queue so they are not re-tested.
- If late-session seasonality is revisited, it needs a *fundamentally* cheaper expression
  (e.g. wider timeframe to amortise the spread, or a second instrument to net flows) —
  recorded as `blocked-on-data`, not a re-test of this mechanism.
