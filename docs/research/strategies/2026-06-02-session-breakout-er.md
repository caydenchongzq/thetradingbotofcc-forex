---
id: 2026-06-02-session-breakout-er
name: SessionBreakoutER
family: breakout
status: promoted
related: []
sources: ["docs/research/R1-signal/findings.md"]
trials_used: 0   # pre-ledger; subsequent tuning trials are ledgered (cumulative 40 as of 2026-06-07)
verdict: "Incumbent. Live as config HEAD v4 (ER 0.32, ATR floor 5, single 1R target); lockbox +0.303R, PF 2.03."
---

# SessionBreakoutER — London/NY-overlap opening-range breakout with ER+ATR regime gate

## Hypothesis & market rationale
The London/NY overlap (13:00–16:00 London) is the most liquid, most directional window of
the EURUSD day. A breakout from the first-30-minute opening range, taken **only** when the
market is trending cleanly (Efficiency Ratio high) and volatility sits in a healthy middle
band (ATR floor/ceiling + percentile band), has follow-through; outside that regime,
breakouts are chop and are skipped. The edge profile is *"reach 1R reliably"* — high win
rate to a modest target, not letting winners run.

## Sources
Internal research track R1 (`docs/research/R1-signal/findings.md`). Full plain-English
description: `docs/STRATEGY_OVERVIEW.md`. Spec: `docs/specs/01-strategy-engine.md`.

## Relation to prior library work
First entry — the incumbent every candidate A/Bs against.

## Strategy spec (HEAD v4, promoted 2026-06-03)
Session 13:00–16:00 London (DST-aware) · opening range first 30 min · stop-order entry at
range ± 1.5-pip buffer on a closed M15 bar · regime gate ER(14) ≥ **0.32** AND ATR(14) in
NORMAL band (floor 5 / ceiling 22 pips, 20%/90% percentiles) · news blackout ±15 min +
2h pre-close, fail-closed · one shot per side per day · stop = max(opposite side of box,
1.2×ATR) · target **single 1.0R, 100% out** · risk 0.35% equity/trade via Governor.
Tunable levers: see `ALLOWED_LEVERS` in `src/agents/proposal.py`.

## Implementation notes
`src/engine/strategy.py` (+ `indicators.py`), registered as `"SessionBreakoutER"` in
`src/engine/registry.py`. Pure `evaluate`/`manage`; every degraded path ⇒ `NoSignal`.
Tests: `tests/engine/`. Live == backtest via `src/engine/decide.py`.

## Backtest results (real EURUSD M15, 2024-01 → 2026-05, $100k, v4)
All R6 gates pass: in-sample expectancy +0.294R · win rate 73.2% · PF 1.99 · Sharpe 3.36 /
Sortino 5.36 · DSR 0.997 @ 40 trials · walk-forward stitched OOS +0.28R, no severe fold ·
**lockbox +0.303R, PF 2.03, Sharpe 4.32 PASS** · zero FTMO breaches.

## Verdict
Promoted. v1→v4 history in the ConfigStore (v4 = ER 0.30→0.32 via optimizer proposal,
human-approved 2026-06-03).

## Lessons
- The win-rate profile is the edge: both attempts to extend reward per trade
  ([[2026-06-03-full-exit-model]], [[2026-06-07-tp-2r-sweep]]) collapsed on held-out data.
- The regime gate does the heavy lifting — most days are (correctly) skipped.

## Next steps
Improvement backlog (IMPLEMENTATION_STATUS §backlog): HTF trend bias, time-of-day/DOW
filters, vol-of-vol gate — all as *filters on this strategy*, each a library entry.
