# Full exit model (spec 01 §3.5)

Status: **implemented + unit-tested in the backtester; NOT adopted for SessionBreakoutER**
(A/B below). Live path is unchanged (still 100% at the broker TP). Date: 2026-06-03.

## What was built

`EventDrivenBacktester` now honors the complete `ExitPlan` the strategy already emits —
scaled partial take-profits, a break-even stop move, and an optional trailing stop —
instead of closing 100% at the first target. One position at a time; all legs of a scaled
exit aggregate into a single `SimTrade` (blended R) so the metrics/gates are unchanged.

### The exact algorithm (so a live mirror can match it bit-for-bit)

Two classes of exit, sequenced per bar:

1. **Broker-side, intrabar-exact** — the *initial stop* and the *final target* behave like a
   broker stop + take-profit. They fill the instant the bar's range touches them. If a bar's
   range spans both, the **stop is taken first** (pessimistic). The final target is
   `targets[-1]`; it fills at the exact level (limit-style, no extra slippage).

2. **Management-driven, close-based** — intermediate partials, the break-even move, and the
   trailing stop are decided at **bar close** (one request each), exactly as a live
   `strategy.manage` on a closed bar would:
   - **Partial:** when a bar *closes* beyond an intermediate target, close that target's
     `fraction * initial_lots` at the bar close (with exit slippage). Dust below `min_lot`
     either rolls into the runner or is skipped.
   - **Break-even:** when the close-based favorable excursion reaches `move_be_after_r`,
     move the stop to entry.
   - **Trailing** (off by default): once favorable excursion ≥ `trail.activate_after_r`,
     ratchet the stop to `close ∓ distance_pips`, never loosening, throttled by
     `min_seconds_between_modifies` (converted to bars).

A management action on bar *N* only affects bars *N+1…* — it cannot change an intrabar fill
that already happened during bar *N*. This makes the model **conservative**: partials are
close-based (we never assume we caught an intrabar spike we couldn't have managed), while the
stop and final target stay intrabar-exact.

`exit_reason` on the aggregated trade is the final leg's reason (`tp` / `sl` / `be` / `eod` /
`manage_close`) with a `+p` suffix when more than one leg was realized.

## A/B result — real EURUSD M15, 2024-01 → 2026-05, config HEAD v2, $100k

| metric | OLD: 100% at 1R | NEW: 0.5@1R + BE, runner→2R |
|---|---|---|
| in-sample expectancy | **+0.272R** | +0.189R |
| win rate | **72.1%** | 56.1% |
| profit factor | **1.88** | 1.41 |
| Sharpe / Sortino | **3.28 / 5.18** | 1.69 / 2.90 |
| in-sample max DD | **$2,216** | $3,272 |
| walk-forward stitched OOS | +0.261R, no severe fold | +0.224R, **severe fold −0.278R** |
| **lockbox (held out)** | **+0.303R, PF 2.03, Sharpe 4.32** | **+0.093R, PF 1.17 — FAILS gate** |
| FTMO breaches | 0 | 0 |

**Conclusion:** the full exit model is *worse* for SessionBreakoutER and fails the held-out
lockbox. The edge is "reach 1R reliably"; scaling out + break-even turns clean winners into
half-winners-and-scratches, collapsing the win rate. **Decision: keep the single 1R target.**

The code stays in the engine because it is correct, general, and likely *beneficial for a
future trend/momentum strategy* (where letting winners run is the whole point). When such a
strategy is added, these become auto-tunable levers (target Rs, fractions, BE, trail).

## Parity note (important)

Because the engine now honors `target_r_multiples` / `partial_fractions` / `move_be_after_r`,
a config that lists multiple targets will make the **backtester** scale out while the **live**
path still exits 100% at the broker TP. `config/default.yaml` is therefore set to a single 1R
target (the validated behavior, and `live == backtest`). Adopting the multi-target model live
would require Phase 2: mirror the close-based partial/BE/trail into `strategy.manage` +
`decide_manage` + the execution adapter (with per-ticket management state), validated via
FakeBroker — only worthwhile for a strategy where the backtest A/B shows a gain.
