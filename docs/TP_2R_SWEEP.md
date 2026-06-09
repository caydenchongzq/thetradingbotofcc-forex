# ≥2R take-profit sweep — REJECTED (2026-06-07)

**Question:** can `SessionBreakoutER` clear the R6 gates with 100% out at a ≥2R target?
(User-requested. Distinct from the scaled 1R+runner-to-2R exit already rejected in
`docs/EXIT_MODEL.md` — this tested a *pure single target* at 2R/2.5R/3R, which keeps
`live == backtest` since live exits 100% at the broker TP.)

**Spec:** `config/optimize/tp2r.yaml` — grid 18 = `target_r_multiples` {[2.0],[2.5],[3.0]}
× `atr_mult_sl` {0.8…1.8 step 0.2}. Base = HEAD **v4** (ER 0.32, ATR floor 5.0).
`move_be_after_r` stayed null (BE is not mirrored live). Judged at **trial_count = 40**
(18 + 22 prior cumulative). Data: real EURUSD M15, 2024-01 → 2026-05, $100k.

## Result: all 18 candidates FAIL — nothing to propose

Every candidate failed the **deflated-Sharpe gate** (best DSR 0.84 vs ≥ 0.95), and the
best candidate also **fails the held-out lockbox outright**:

| | INCUMBENT v4 (1R) | best ≥2R: tp 2.5 / sl 1.4 |
|---|---|---|
| in-sample expectancy | +0.294R | +0.312R |
| win rate | **73.2%** | 42.8% |
| profit factor | **1.99** | 1.47 |
| Sharpe / Sortino | **3.36 / 5.36** | 1.75 / 3.37 |
| DSR @ 40 trials | **0.997 PASS** | 0.766 **FAIL** |
| stitched OOS exp | +0.28R | +0.40R (looks better — see below) |
| **lockbox (held out)** | **+0.303R, PF 2.03 PASS** | **+0.074R, PF 1.08, Sharpe 0.31 FAIL** |
| FTMO breaches | 0 | 0 |

Full leaderboard: every tp∈{2.0, 2.5, 3.0} × sl combination had PF 1.34–1.51,
Sharpe 1.14–1.91, DSR 0.38–0.84 — uniformly below the incumbent on every risk-adjusted
metric. Win rate drops from ~73% to 36–48% at all ≥2R targets.

## Why it fails (same lesson as EXIT_MODEL.md, sharper)

- The edge is **"reach 1R reliably"**: a high-win-rate mean-reversion-to-target profile.
  Doubling the target trades a 73% win rate for a 43% one; the larger R per winner does
  not buy back the lost consistency (Sharpe halves).
- The seductive number — stitched OOS expectancy +0.40R vs +0.28R — is exactly the trap
  the lockbox exists for: on the truly held-out final 6 months the best ≥2R config
  collapses to **+0.07R / PF 1.08**, below every core gate. Higher per-trade expectancy
  that fails the lockbox = REJECT (hard invariant #2).
- The DSR gate independently rejected all 18 at an honest 40-trial penalty.

**Decision: keep the single 1R target (HEAD v4 unchanged). No proposal written.**

## Bookkeeping

- Cumulative DSR trial count is now **40** (9 on 2026-06-03 + 13 prior + 18 here).
  Pass `--base-trials 40` to the next sweep.
- Raw per-candidate results were checkpointed during the run (sandbox-side); the spec
  `config/optimize/tp2r.yaml` reproduces them deterministically (`seed 0`, grid).
