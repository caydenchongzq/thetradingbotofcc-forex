---
id: 2026-06-26-prior-day-overreaction-reversal
name: PriorDayOverreactionReversal
family: mean-reversion
status: probe-rejected (no trial)
related:
  - 2026-06-17-intraday-seasonality-drift
  - 2026-06-16-vwap-stretch-reversion
  - 2026-06-19-session-range-false-break-fade
sources:
  - "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3362142"
  - "https://www.emerald.com/jes/article/48/1/211/224523/Daily-abnormal-price-changes-and-trading"
trials_used: 0
verdict: "Probe-rejected: next-day reversal after abnormal daily return is noise in 2024-2026 data (gross −3 to +0.65p across all thresholds; ~50% WR; signal absent or reversed vs Caporale-Plastun 2008-2018 finding). No trial."
---

# PriorDayOverreactionReversal — Cross-day reversal after abnormal EURUSD daily return

## Hypothesis & market rationale

Caporale and Plastun (2019, SSRN 3362142; published JES 2020) document a two-part pattern in
EURUSD using daily + hourly data for 2008–2018:
1. On an "overreaction day" (daily return exceeds a dynamic threshold), prices continue **in
   the direction of the overreaction** throughout the day.
2. **The following day, prices reverse** — cumulative abnormal returns are statistically
   negative relative to the overreaction direction.

The proposed strategy: detect a daily overreaction via a rolling z-score or ATR-multiple
threshold; at the London open the NEXT day, enter a fade (short if prior day was strongly up,
long if prior day was strongly down). Stop ~1.5×ATR, target 1.5R (reversal can be substantial).
Entry is at market (next London open bar's open) — live-safe.

The economic rationale: overreaction days are driven by herding or short-term imbalanced flow;
by the following session, liquidity normalises and prices mean-revert to fair value. The
cross-day temporal horizon is explicitly differentiated from the **intraday** mean-reversion
family (which is 4/4 closed across EURUSD M15 intraday anchors).

## Sources

1. Caporale & Plastun (2019/2020) "Price Overreactions in the Forex and Trading Strategies"
   — SSRN 3362142 / Journal of Economic Studies 2020. Documents next-day reversal in EURUSD,
   USDJPY, USDCAD, AUDUSD, EURJPY for 2008–2018.
   URL: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3362142

2. Emerald published version: https://www.emerald.com/jes/article/48/1/211/224523/daily-abnormal-price-changes-and-trading

## Relation to prior library work

**Differentiated from the closed mean-reversion family (4/4):**
- [[2026-06-08-asian-sweep-fade]], [[2026-06-10-asian-sweep-fade-rr]], [[2026-06-16-vwap-stretch-reversion]],
  [[2026-06-19-session-range-false-break-fade]]: all were **within-session** fades of an intraday
  price extension relative to an intraday anchor (Asian range, session VWAP, session OR). They
  used price structure within the SAME session as both signal and anchor.
- This candidate uses a **prior CALENDAR DAY's total return** as the signal, entering the NEXT
  day's London session. The temporal scale differs by an order of magnitude; the anchor is the
  prior session close, not any intraday structure.

**Differentiated from [[2026-06-17-intraday-seasonality-drift]]** (closed, fixed-time): that
strategy used a fixed-clock directional leg with no price-level conditioning. This strategy is
conditioned on the MAGNITUDE of the prior day's move, not the time of day.

The differentiation was judged legitimate; the probe was warranted before spending a trial.

## Strategy spec (probe only — never implemented)

- **Session:** London open, 07:00–08:00 UTC; entry at the open of the first London bar.
- **Signal:** |daily_return_prior_day_pips| > threshold, where daily return = open-to-close of the
  prior calendar day (computed from M15 data).
- **Threshold options probed:**
  - ATR-multiple: |ret| > k×rolling_20d_ATR_HL, for k ∈ {0.5, 0.7, 1.0, 1.2}
  - Z-score: |z| > {1.5, 2.0} where z = (ret − roll_mean) / roll_std over 20 days
- **Direction:** fade the prior day's direction (short if prior day was up, long if down).
- **Exit probed:** end of London session (16:00 UTC) or by 10:00 / 12:00 UTC.
- **Entry:** market fill at London open bar's open (always live-safe).

Exit geometry (for a trial, if probe had passed):
- Stop: 1.5×ATR (wider than incumbent; reversal needs room as prior-day momentum may persist
  briefly before reversing).
- Target: 1.5R (R:R 1:1 minimum, with asymmetric upside if reversal materialises).
- Rationale: reversal is expected to be moderate in magnitude but directionally persistent;
  1.5×ATR stop avoids premature exit on residual prior-day momentum, 1.5R target captures
  the reversal if it occurs.

## Implementation notes

Not implemented. Probe only (scripts/probe inline). No files created; pytest unaffected; no
writes to state/ or live path.

## Backtest results

**Probe results (direct on parquet, not full harness):**

Data: 625 trading days, 2024-01-02 to 2026-05-29.

| threshold | n events | gross mean | net mean | win rate |
|---|---|---|---|---|
| k=0.5×ATR | 247 | −1.03p | −2.03p | 45.7% |
| k=0.7×ATR | 153 | +0.65p | −0.35p | 49.7% |
| k=1.0×ATR | 66 | +0.23p | −0.77p | 47.0% |
| k=1.2×ATR | 38 | −3.38p | −4.38p | 44.7% |
| z>1.5, exit 10UTC | 74 | −3.10p | −4.10p | 52.7% |
| z>1.5, exit 12UTC | 74 | −4.59p | −5.59p | 44.6% |
| z>1.5, exit 16UTC | 74 | −4.13p | −5.13p | 47.3% |
| z>2.0, exit 10UTC | 32 | −3.65p | −4.65p | 56.2% |
| z>2.0, exit 12UTC | 32 | −7.15p | −8.15p | 43.8% |
| z>2.0, exit 16UTC | 32 | −3.44p | −4.44p | 46.9% |

Cost assumed ~1.0p round-trip (liquid London hours). Standard deviation ~37–43p across all
cells vs mean of −7 to +0.65p → signal-to-noise ratio ≈ 0.

## Verdict

**PROBE-REJECTED. No trial spent. Trials remain at 171; W26 budget 9/10 remaining.**

The next-day reversal signal is absent in the 2024-2026 EURUSD data:
- Best cell: k=0.7, gross +0.65p (n=153) → net −0.35p after cost. Standard deviation 38p
  over 153 events = t-statistic ≈ 0.21. Not significant.
- Z-score versions are uniformly negative at every exit window.
- The sign is inconsistent: some cells are slightly positive, some strongly negative.
  There is no threshold that gives consistent directionality.

The Caporale-Plastun (2008-2018) finding does not replicate on 2024-2026 data. Likely causes:
1. Market regime changed: post-2020 EURUSD volatility structure is different from 2008-2018.
2. The paper's 10-year sample included multiple distinct macro regimes; 2024-2026 is one regime.
3. Effect may have been arbitraged away since the paper's study period.

## Lessons

1. **Cross-day temporal scale ≠ automatic differentiation from intraday mean-reversion.**
   The mechanism is different (prior-day total return vs intraday extension), but the
   EMPIRICAL RESULT is the same: EURUSD does not mean-revert predictably on either intraday
   OR daily timeframes within this 2024-2026 dataset. The family closure may be broader than
   "intraday."
2. **Academic paper results from 2008-2018 may not transfer to 2024-2026.** FX mean-reversion
   anomalies documented in the pre-2020 era should be probed on current data before trialing.
   Time-stability of the effect is as important as statistical significance.
3. **Short dataset (2.5 years) magnifies estimation noise.** With std dev ~40p and n=74–247
   events, confidence intervals are ±5–10p — too wide to distinguish a real 1-2p edge from
   zero. Longer history would be needed to detect a subtle reversal effect.
4. **Probe cost: ≈ 1 hour, 0 trials.** Always worth checking cross-day mean-reversion
   empirically before claiming the family differentiation extends to daily scale.

## Next steps

- No variants worth probing. The daily overreaction reversal lacks the gross expectancy even
  at liberal thresholds. A larger dataset might reveal the effect if it exists; not testable
  with current data.
- The "real lever" remains longer history / second instrument export ([[2026-06-14-trend-aligned-orb]]
  and the subtractive filter queue are waiting on it).
