---
id: 2026-06-26-quality-gated-second-entry
name: QualityGatedSecondEntry
family: breakout
status: probe-rejected (no trial)
related:
  - 2026-06-13-second-entry-orb
  - 2026-06-15-resting-stop-and-market-entry
  - 2026-06-22-volume-confirmed-orb
trials_used: 0
verdict: "Probe-rejected: second-break (episode-2) trades have WORSE expectancy (−0.059R net, WR 47.1%) than first-break trades (−0.035R net, WR 50.5%) under market fill. A quality gate cannot rescue below-zero base expectancy; the re-break advantage claimed in the level-fill version was an artifact. No trial."
---

# QualityGatedSecondEntry — Restrict SecondEntryORB re-breaks to higher-quality episodes

## Hypothesis & market rationale

[[2026-06-13-second-entry-orb]] was the first candidate to clear ALL R6 gates + walk-forward +
lockbox (252 trades, +0.266R, PF 1.84, 6/7 WF folds, lockbox +0.248R). It was "tested-passed
but dominated" by HEAD v4. The hypothesis here: the 28 or so re-break (episode-2) entries are
individually at ~+0.04R; restricting them to a "higher quality" subset (shallower pullback,
higher ER on the second break bar, or shorter time between episodes) might improve the combined
strategy's per-trade expectancy to surpass HEAD.

The economic rationale for quality-gating: a re-break after a very deep pullback (close to the
opposite OR level) may signal a choppy session; a shallow pullback (barely back inside the range)
suggests the bias is clearer and the second attempt is more committed.

## Sources

- Internal library analysis: [[2026-06-13-second-entry-orb]] (INDEX)
- [[2026-06-22-volume-confirmed-orb]] established the general "filter a negative base = still
  negative" principle on the market-fill incumbent.

## Relation to prior library work

**Builds on [[2026-06-13-second-entry-orb]]** which showed 252 trades at +0.266R. However:
- That test predated the [[2026-06-15-resting-stop-and-market-entry]] revelation (June 15).
- SecondEntryORB used the SAME entry mechanism as the incumbent — `_signal()` with a market
  fill at the bar's close or next bar's open. Both first-break AND second-break entries in that
  test may have been computed against the same level-fill fill that gave the incumbent +0.391R.
- The INDEX itself flags: "incumbent-FILTER queue must be re-based on the MARKET-fill incumbent
  (−0.024R) before any 'dominates HEAD' claim counts" — this applies equally to additive
  strategies whose first-break slice IS the incumbent.

**Different from [[2026-06-22-volume-confirmed-orb]]** in that there is more trade-count
headroom (224 first-breaks already above the 200-floor, so a zero-trim of re-breaks still
passes the floor). The floor argument doesn't apply here; the pure expectancy does.

## Strategy spec (probe only — never implemented)

Planned quality dimensions:
1. **Pullback depth**: re-break only allowed if the price during the pullback between episodes
   did NOT reach more than D pips back toward the opposite OR level.
2. **Second-break ER**: the second break bar must have ER > threshold.
3. **Time gap**: fewer than T bars between episode end and episode restart.

The full SecondEntryORB framework (subclass of SessionBreakoutER, same regime gate, same
exit geometry) would have been used.

Exit geometry: identical to incumbent (single 1R, stop = max(structural, 1.2×ATR)), as
the underlying mechanism is the same ORB continuation.

## Implementation notes

Not implemented. Probe only. No files created; pytest unaffected; no writes to state/ or
live path.

## Backtest results

**Probe: market-fill episode-1 vs episode-2 outcomes (direct parquet simulation)**

Using HEAD v4 config parameters (ER ≥ 0.32, ATR range gate, same OR window):

| episode | n trades | net mean | win rate | std |
|---|---|---|---|---|
| episode-1 (first break) | 865 | −0.035R | 50.5% | ~0.89R |
| episode-2 (second break) | 456 | −0.059R | 47.1% | ~0.89R |

Notes:
- Cost model: ~0.5p market-fill spread per half-turn, applied as R fraction vs the SL.
- Episode-1 count (865) differs from the harness-reported 224 because this probe uses a
  simplified signal (no `context_bias`, no full blackout, no harness risk governor). The
  RELATIVE comparison (episode-1 vs episode-2) is valid; the absolute magnitudes approximate.
- Episode-2 is measurably WORSE than episode-1 on both expectancy (−0.059R vs −0.035R)
  and win rate (47.1% vs 50.5%).

## Verdict

**PROBE-REJECTED. No trial spent. Trials remain at 171; W26 budget 9/10 remaining.**

The second-break entries have **inferior** expectancy and win rate compared to first-break
entries. A quality gate applied to an already-negative subset cannot push the combined strategy
positive. This also settles a previously unresolved question: the "+0.04R per re-break trade"
claimed in the SecondEntryORB report was likely a level-fill artifact (the same fill that gave
the incumbent +0.391R instead of −0.024R). Under market fill:

- First-break entry (market): approximately −0.03R per trade
- Second-break entry (market): approximately −0.06R per trade
- Second-break entries are ANTI-selective (worse, not better, than first breaks)

The "flushing weak hands" mechanism does NOT improve subsequent re-break quality on EURUSD M15.

## Lessons

1. **The SecondEntryORB +0.266R result must be treated as a level-fill artifact pending
   market-fill re-test.** The backtest was run before the June-15 fill-realism revelation.
   Before claiming "tested-passed" status, a market-fill SecondEntryORB full harness run
   should be done (but see lesson 2 — it will likely fail).
2. **Re-break entries are NOT higher quality than first-break entries on EURUSD M15.** The
   second attempt of a failed breakout faces the same structural headwind as the first (65%
   double-break chop). The market "memory" of a prior failed level does not confer directional
   bias to the next attempt — it may even be mildly adverse (47.1% WR < 50.5%).
3. **Additive trade count does NOT rescue a strategy with negative first-break base.** Adding
   episodes to a −0.03R first-break strategy only accrues more negative-expectancy trades.
   The lesson from [[2026-06-22-volume-confirmed-orb]] (filter family) now extends to the
   additive direction: you cannot manufacture edge by adding more touches of a level that
   the first touch already proved negative.
4. **Two-probe run day: both rejected at zero trial cost.** The data-exhaustion heuristic
   (M5 review: "real lever = longer data / 2nd instrument") is confirmed. The idea space on
   the 2024-2026 EURUSD M15 dataset is effectively exhausted.

## Next steps

- Do NOT test a market-fill SecondEntryORB full run — the probe shows it will be negative.
  Save the trial budget.
- The QualityGatedSecondEntry idea is **closed**. Update idea queue entry to probe-rejected.
- Priority action for Cayden: **export longer history and/or a second instrument**
  ([[2026-06-14-trend-aligned-orb]] and the filter queue are waiting on ≥3–5 years of data).
  TrendAlignedORB dominates HEAD on quality but failed the 200-trade floor at 2.5 years;
  longer data would likely clear it.
