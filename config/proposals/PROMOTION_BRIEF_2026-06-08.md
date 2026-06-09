# Promotion Brief — 2026-06-08

**Analyst:** automated Backtest Analyst run (scheduled task `ftmo-analyst`)
**HEAD at run time:** config **v4** (`SessionBreakoutER`, ER 0.32 / ATR floor 5.0)
**Data:** `state/parquet/eurusd_m15.parquet` present.
**Trials:** ledger shows period 2026-W24 count 4 of 10. Note the ledger undercounts the all-time total — the latest optimizer library report puts cumulative trials at ~80; use that for any manual `--trials` runs.

## TL;DR — one PASS awaiting your decision, five rejects

Six un-ledgered proposals were run through `process_proposal.py`. Verdicts are deterministic; nothing was promoted.

| Proposal | File | Change | Verdict |
|---|---|---|---|
| `2026-06-08-opt-001519` | `opt_2026-06-08-opt-001519.json` | ER 0.32→0.34, ATR floor 5.0→4.5 | **PASSED** |
| `2026-06-07-opt-025424` | `opt_2026-06-07-opt-025424.json` | (empty diff) | REJECTED_VALIDATION (empty diff — sweep winner was HEAD itself) |
| `2026-06-02-w23-001` | `example.json` | ER 0.30→0.38 | REJECTED_VALIDATION (stale parent v1 ≠ v4) |
| `2026-06-02-w23-002` | `er_033.json` | ER 0.30→0.33 | REJECTED_VALIDATION (stale parent v1 ≠ v4) |
| `2026-06-02-w23-003` | `atr_floor_5.json` | ATR floor 4.0→5.0 | REJECTED_VALIDATION (stale parent v1 ≠ v4) |
| `2026-06-03-w23-exits-scaleout` | `scaled_exits_example.json` | scale-out exits | REJECTED_VALIDATION (stale parent v3 ≠ v4) |

## PASSED: `2026-06-08-opt-001519` (weekly sweep winner, coarse-to-fine, 79 sweep trials)

- In-sample: 229 trades, expectancy **+0.274R**, PF **1.89**, Sharpe **3.09**, **0** simulated FTMO breaches
- Walk-forward: **6/7 folds profitable**, no stitched-OOS collapse, no severe fold
- Lockbox: **PASSED**
- Ledger: recorded `passed`, 2026-06-08T01:33Z

**Recommendation: review, but lean against promoting.** It clears every R6 gate and the lockbox, yet yesterday's sweep analysis (2026-06-07/08 session) found its OOS expectancy (+0.264R) **trails the incumbent HEAD v4 OOS** — a pass is necessary but not sufficient; it must also beat the incumbent. If after review you still want it, promote it yourself with:

    py scripts\process_proposal.py config\proposals\opt_2026-06-08-opt-001519.json --approve

Otherwise mark it rejected/archive the file so future runs skip it.

## Housekeeping (third consecutive run flagging this)

The four stale w23 files reject pre-trial every run and are never ledgered, so the analyst re-picks them up daily. v4 already embodies their ideas (ER 0.32, ATR floor 5.0). Please archive/delete `example.json`, `er_033.json`, `atr_floor_5.json`, and move `scaled_exits_example.json` (intentional worked example) to e.g. `config/proposals/archive/`. Same for the empty-diff `opt_2026-06-07-opt-025424.json`. New proposals must declare `parent_config_version: 4`.

*Hard rules honored: no `--approve`, no trades, no gate edits.*
