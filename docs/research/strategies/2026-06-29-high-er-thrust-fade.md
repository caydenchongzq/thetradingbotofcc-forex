---
id: 2026-06-29-high-er-thrust-fade
name: HighERThrustFade
family: mean-reversion
status: probe-rejected (no trial)
related: [2026-06-16-vwap-stretch-reversion, 2026-06-15-resting-stop-and-market-entry, 2026-06-21-fill-anchored-exit]
sources:
  - "https://paperswithbacktest.com/wiki/strategies-trading-euro (PaperswithBacktest EURUSD strategy catalog)"
  - "https://www.dxpa.in/resources/inside-bar-patterns (DXPA Analytics: inside-bar compression-breakout mechanisms)"
  - "Larry Connors & Linda Bradford Raschke (1995), Street Smarts — NR4/inside-bar pattern mechanics"
trials_used: 0
verdict: "Statistically real (t=3.0 at ER>=60%) but economically nil: gross +0.14p vs 2.6p cost. PROBE REJECT."
---

## Hypothesis & Market Rationale

After a M15 bar with a **high body-to-range efficiency ratio** (ER = |close−open|/(high−low) ≥ 0.7),
the next bar tends to partially REVERSE the directional thrust (mean-reversion). The mechanism:
a "full-body" bar (small shadows, large body) represents a one-sided push that transiently
overshoots liquidity equilibrium; the next bar reprices back toward the thrust-open as trapped
traders cover.

This was queued in the library (idea 2026-06-16-high-er-thrust-fade) with the condition that
**§4.3 requires a prior probe of the conditional reversion sign before trial**, because:
- Mean-reversion fade is 5/5 CLOSED across anchors
- HighER fades INTO the regime where the incumbent CONTINUATION strategy lives

The §4.3 differentiation claim: the ER is a **per-bar microstructure signal** (not an anchor
level, not an intraday drift, not an institutional mechanism) — the closest prior test is
VWAP stretch reversion [[2026-06-16-vwap-stretch-reversion]] (multi-bar session extension)
which is on a different temporal axis. The probe is legitimate.

## Sources (cited)

- PaperswithBacktest.com EURUSD strategy catalog: lists "Enter Narrow Range Patterns" as one
  of three practitioner-standard EURUSD intraday strategies. The mechanism inverts to "fade
  full-range bars."
- DXPA Analytics inside-bar guide: discusses body-to-range ratio as a compression signal;
  motivates the ER measure.
- Connors & Raschke (1995) Street Smarts: the NR4/NR7 contraction pattern (related; our ER
  is a per-bar directional version). NR7 was already tested and rejected [[2026-06-18-nr7-volatility-breakout]].

## Relation to Prior Library Work

- [[2026-06-16-vwap-stretch-reversion]]: faded multi-bar session extension vs VWAP; failed
  (sign wrong, −0.283R). Different axis: session-level vs single-bar.
- [[2026-06-18-nr7-volatility-breakout]]: tested compression→expansion breakout (resting-stop);
  used contraction as the trigger for continuation, not for fade.
- [[2026-06-15-resting-stop-and-market-entry]]: confirmed EURUSD M15 breaks both ways (~65%).
  High-ER bars are the opposite of indecision — they are directional — but they may still
  reverse quickly at M15 timescale.

Differentiation from the closed mean-reversion family: this is a **single-bar microstructure**
signal (not level-anchored, not drift-anchored, not institutional). The probe is warranted.

## Probe Results

**Data**: 59,993 M15 bars, 2024-01-01 to 2026-05-29.
**Definition**: ER = |close−open|/(high−low); real bars only (range > 2 pips, directional body).

| ER Threshold | n bars | Fade Gross | Fade Net | t-stat | p-value |
|---|---|---|---|---|---|
| ER ≥ 60% | 19,591 | **+0.11p** | **−2.49p** | 3.04 | 0.002 |
| ER ≥ 70% | 13,091 | **+0.14p** | **−2.46p** | 2.93 | 0.003 |
| ER ≥ 80% | 7,348 | **+0.14p** | **−2.46p** | 2.14 | 0.032 |
| ER ≥ 85% | 4,840 | **+0.10p** | **−2.50p** | 1.25 | 0.213 |

**Continuation direction** (trade with the ER bar into the next bar): gross = −0.11 to −0.14p
(also negative, confirming micro-reversal exists but neither direction is profitable after cost).

**Cost gate**: 2.6p gross required. Best gross observed: +0.14p (5.4% of cost). **Verdict: PROBE REJECT.**

## A/B vs Incumbent HEAD

Not applicable — probe rejected before building.

## Verdict

**PROBE REJECTED (no trial).** The HighERThrustFade signal is **statistically non-zero**
(t = 3.0, p = 0.002 at ER≥70%) — high-body bars DO mildly reverse on the next M15 bar —
but the effect size (+0.14p gross) is approximately **18× smaller than the 2.6p cost stack**.
The continuation direction is equally negative (−0.14p).

This is the clearest quantification of the mean-reversion-vs-cost trade-off in the library:
the microstructure signal EXISTS but is economically irrelevant at M15 timescale.

Key implications:
- Mean-reversion family CONFIRMED closed 6/6 (including this microstructure probe).
- The ER measure used by the incumbent (regime gate) detects these directional bars; the
  incumbent entry is DESIGNED to go WITH them, but even continuation is marginally negative.
- No single-bar reversal signal reaches the cost gate on M15 EURUSD.

0 trials spent. W27 budget 10/10 remaining.

## Lessons

1. **Microstructure reversal is real but economically sub-threshold at M15**: High-body bars
   (ER≥70%) do revert slightly (+0.14p gross) but not enough to trade. The M15 timeframe is
   too coarse to harvest sub-pip microstructure effects — a tick-level or M1 strategy might
   capture this (blocked on data).
2. **Statistical significance ≠ economic significance**: t=3.0 but 18× short of cost gate.
   Always measure in pips/R, not t-statistics.
3. **The HighERThrustFade idea is definitively closed**: we tested the exact conditioning
   mechanism the queue entry specified; it failed. Do not re-probe without a mechanism that
   lifts gross above 3p.
4. **EURUSD M15 2024–2026 mean-reversion is now closed across 6 mechanisms**: level-anchored
   (Asian fade, VWAP stretch, session-OR false break, ECB institutional), cross-day (prior-day
   overreaction), and now bar-level microstructure. The reverting force exists but is uniformly
   too small to overcome the 2.6p cost floor.

## Next Steps

None — idea closed. The 5/5→6/6 MR closure update is logged in the INDEX.
