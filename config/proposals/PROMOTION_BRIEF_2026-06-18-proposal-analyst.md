# Promotion Brief — 2026-06-18 (Backtest Analyst)

**HEAD: config v4 (unchanged). No promotable candidate this run. No action required from Cayden.**

## Summary

No proposal PASSED. The five unprocessed proposal files in `config/proposals/` are all stale
seed/example fixtures — every one was deterministically **REJECTED at validation** (before any
backtest), so none consumed a trial, touched the ledger, or spent weekly budget. Today's actual
auto-loop candidate (`2026-06-18-nr7-volatility-breakout`) was already built, tested, and recorded
as **FAILED** by the research engine's own run at 00:54 UTC — nothing new for me to re-run.

## Unprocessed proposal files (all rejected on the allowed-lever gate)

| File | proposal_id | Verdict | Reason |
|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (no lever changed) |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | stale parent (v3 ≠ HEAD v4) |

These are repo seed/example files from the initial June 2–3 setup (and the deliberately-rejected
scale-out worked example). They reference old parent versions, so the safety validator rejects
them before the backtester — this is correct behaviour, not a regression. They will keep
re-appearing as "unprocessed" because a `rejected_validation` outcome is intentionally NOT written
to the ledger. **Recommend Cayden archive/delete these five fixtures** out of `config/proposals/`
so future analyst runs aren't noise (optional housekeeping; leaving them is harmless).

## Today's auto-loop candidate (already processed — context only)

`2026-06-18-nr7-volatility-breakout` (NR7VolatilityBreakout) — **FAILED**, recorded by the
research engine (1 trial used).

- In-sample: 354 trades (clears the 200 floor — additive), expectancy **−0.263R**, win 35.0%,
  PF **0.68**, Sharpe **−3.04**, DSR **0** → **fails 5/7 in-sample gates** (expectancy, PF, Sharpe,
  Sortino, DSR). FTMO breaches: none in-sample, but see below.
- OOS / walk-forward / lockbox: folds ~empty because the Risk Governor's FLATTEN latch tripped on
  an early ≥85%-of-daily-budget loss day and halted the sim account — capital protection working
  as designed (invariant #4), not a data gap.
- Takeaway: a live-faithful resting-stop OCO armed at the NR7 bar's close (genuinely live-placeable,
  no retcode 10015). The NR7 volatility-contraction filter did **not** cure the adverse selection —
  the touch fill still catches the false pokes. This is the **third** live-faithful confirmation
  that breakout-bar continuation on EURUSD M15 isn't harvestable with a live-placeable fill. No
  promotion warranted; the breakout-continuation direction looks closed.

## Recommendation

Nothing to promote — **do not run `--approve` on anything this cycle.** HEAD stays at config v4.
Optional: clear the five stale fixture files from `config/proposals/`.
