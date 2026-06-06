# Promotion Brief — 2026-06-06

**Analyst:** automated Backtest Analyst run (scheduled task `ftmo-analyst`)
**HEAD at run time:** config **v4** (`SessionBreakoutER`, promoted from optimizer proposal `2026-06-03-opt-084109`)
**Data:** `state/parquet/eurusd_m15.parquet` present.
**Cumulative trials this period (2026-W23):** 1 of 4 cap (unchanged by this run).

## TL;DR
Four unprocessed proposals were found and run through `process_proposal.py`. **All four were rejected deterministically at the validation stage — `REJECTED_VALIDATION` — before any backtest ran**, because each was authored against an older config version than the current HEAD (compare-and-swap on `parent` failed). No R6 gates, walk-forward, or lockbox were evaluated, and **nothing was written to the trial ledger** (validation failures are pre-trial). The proposal that already passed (`2026-06-03-opt-084109`) was skipped — it is the one that became HEAD v4.

| Proposal | File | Change | Parent → HEAD | Verdict |
|---|---|---|---|---|
| `2026-06-02-w23-001` | `example.json` | `regime.er_threshold` 0.30 → 0.38 | v1 → v4 | REJECTED_VALIDATION (stale) |
| `2026-06-02-w23-002` | `er_033.json` | `regime.er_threshold` 0.30 → 0.33 | v1 → v4 | REJECTED_VALIDATION (stale) |
| `2026-06-02-w23-003` | `atr_floor_5.json` | `regime.atr_floor_pips` 4.0 → 5.0 | v1 → v4 | REJECTED_VALIDATION (stale) |
| `2026-06-03-w23-exits-scaleout` | `scaled_exits_example.json` | scale-out exits (1R/2R, BE move) | v3 → v4 | REJECTED_VALIDATION (stale) |

## Why they failed (and what to do)
The verdict is **stale parent**, not a strategy failure — none of these were actually backtested. The validator requires `parent_config_version` to equal the current HEAD (v4) before it will spend a trial on a backtest. Each proposal points at an earlier version.

Two of them are also effectively **already incorporated** in HEAD v4, so re-basing them would be redundant:

- **`atr_floor_5.json`** proposes ATR floor 4.0 → 5.0. **v4 already runs `atr_floor_pips: 5.0`.** No action — already live.
- **`er_033.json` / `example.json`** propose tightening ER above 0.30. **v4 already runs `er_threshold: 0.32`** (the optimizer's promoted value). 0.33 and 0.38 are alternative tightenings that would now need to be expressed as a diff *from 0.32* against parent v4 if you still want to test them. Given the optimizer already swept this lever and landed on 0.32, re-testing 0.33/0.38 is low priority.
- **`scaled_exits_example.json`** is the deliberately-kept worked example that the EXIT_MODEL.md A/B already showed fails the lockbox for `SessionBreakoutER`. It's expected to be rejected; the stale-parent rejection just short-circuits it earlier. No action needed — leave as documentation.

## Recommendation
**No promotions this cycle.** There is nothing to `--approve`: zero proposals passed the gates because zero proposals reached the backtester.

Housekeeping for Cayden, if you want a clean proposals folder:
1. The three v1-parent proposals (`example.json`, `er_033.json`, `atr_floor_5.json`) are obsolete — their changes are either already live (ATR floor 5.0, ER 0.32) or superseded. Safe to archive/delete.
2. Keep `scaled_exits_example.json` as the intentional worked example, but be aware it will keep showing up as "unprocessed" each run since validation rejects it pre-trial without ledgering. Consider bumping its `parent_config_version` to 4 if you want it to actually run to a (rejecting) lockbox verdict, or move it out of `config/proposals/` so the analyst stops re-picking it up.
3. Any genuinely new idea should be authored against **parent_config_version 4** so it isn't rejected as stale.

*Hard rules honored: no configs promoted, no trades placed, no gates edited. Verdicts are the deterministic output of `process_proposal.py` and cannot be overridden.*
