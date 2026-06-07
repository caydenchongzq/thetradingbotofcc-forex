---
id: 2026-06-03-full-exit-model
name: FullExitModel (scaled partials + BE + trailing)
family: exit-model
status: tested-rejected
related: [2026-06-02-session-breakout-er]
sources: ["docs/EXIT_MODEL.md"]
trials_used: 0   # pre-dated per-trial ledgering of structural work; counted in the 2026-06-03 batch (9)
verdict: "Rejected for SessionBreakoutER: lockbox +0.093R / PF 1.17 vs incumbent +0.303R / 2.03. Code kept, off."
---

# Full exit model — 0.5 @ 1R + break-even + runner to 2R (optional trail)

## Hypothesis & market rationale
Letting winners run (partial at 1R, move stop to BE, runner to 2R, optional trail) should
raise expectancy per trade vs closing 100% at 1R.

## Sources
Full write-up and exact algorithm: `docs/EXIT_MODEL.md` (spec 01 §3.5).

## Relation to prior library work
Exit-model change on [[2026-06-02-session-breakout-er]]; first structural A/B of the project.

## Strategy spec
Backtester honors the full `ExitPlan`: intrabar-exact initial stop + final target;
close-based partials / BE move / trailing (conservative: management on bar N affects
N+1…). All legs aggregate to one blended-R `SimTrade`.

## Implementation notes
Implemented + unit-tested in `EventDrivenBacktester`; **live path unchanged** (would need
the live mirror: `strategy.manage` + `decide_manage` + adapter). Code remains in the
engine, switched off — `config/default.yaml` pinned to single 1R target to preserve
live == backtest.

## Backtest results (real EURUSD M15, 2024-01 → 2026-05, HEAD v2, $100k)
| metric | OLD: 100% @ 1R | NEW: 0.5@1R + BE, runner→2R |
|---|---|---|
| in-sample expectancy | **+0.272R** | +0.189R |
| win rate | **72.1%** | 56.1% |
| PF / Sharpe | **1.88 / 3.28** | 1.41 / 1.69 |
| walk-forward | +0.261R, clean | +0.224R, severe fold −0.278R |
| **lockbox** | **+0.303R, PF 2.03** | **+0.093R, PF 1.17 — FAIL** |

## Verdict
REJECT for SessionBreakoutER (lockbox fail + severe fold). Single 1R target retained.

## Lessons
- **Per-trade expectancy is not a verdict** — this is the project's canonical example.
- The strategy's edge is its 73% win rate to 1R; scaling out + BE converts clean winners
  into half-winners-and-scratches.
- The machinery is general and likely *right* for a future trend/momentum strategy where
  running winners is the point — re-test it there, not here.

## Next steps
Re-evaluate only attached to a trend-following candidate; then partials/BE/trail params
become auto-tunable levers and the live mirror (Phase-2 work) becomes worthwhile.
