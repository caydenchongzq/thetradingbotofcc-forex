# Promotion Brief — 2026-06-07

**Analyst:** automated Backtest Analyst run (scheduled task `ftmo-analyst`)
**HEAD at run time:** config **v4** (`SessionBreakoutER`, ER 0.32 / ATR floor 5.0)
**Data:** `state/parquet/eurusd_m15.parquet` present.
**Cumulative trials (2026-W23):** 1 of 4 cap — unchanged by this run.

## TL;DR — no promotions, nothing to approve

Four proposals remain un-ledgered and were run through `process_proposal.py`. All four were again **REJECTED_VALIDATION (stale parent)** — identical to the 2026-06-06 run. No backtest, walk-forward, or lockbox was executed; no trial was recorded.

| Proposal | File | Change | Parent → HEAD | Verdict |
|---|---|---|---|---|
| `2026-06-02-w23-001` | `example.json` | ER 0.30 → 0.38 | v1 → v4 | REJECTED_VALIDATION (stale) |
| `2026-06-02-w23-002` | `er_033.json` | ER 0.30 → 0.33 | v1 → v4 | REJECTED_VALIDATION (stale) |
| `2026-06-02-w23-003` | `atr_floor_5.json` | ATR floor 4.0 → 5.0 | v1 → v4 | REJECTED_VALIDATION (stale) |
| `2026-06-03-w23-exits-scaleout` | `scaled_exits_example.json` | scale-out exits (1R/2R, BE) | v3 → v4 | REJECTED_VALIDATION (stale) |

`2026-06-03-opt-084109` was skipped (ledger: passed; it is HEAD v4).

## Status

This is the second consecutive run with this exact outcome. These rejections happen pre-trial and are never ledgered, so the analyst will keep re-picking these files up every day until the folder is cleaned. Repeating yesterday's housekeeping recommendation:

- `atr_floor_5.json`, `er_033.json`, `example.json` — obsolete: v4 already runs ATR floor 5.0 and ER 0.32 (optimizer-swept). Safe to archive/delete.
- `scaled_exits_example.json` — intentional worked example expected to fail; move it out of `config/proposals/` (e.g. `config/proposals/archive/`) or rebase to parent v4 if you want a full lockbox verdict on record.
- New proposals must declare `parent_config_version: 4`.

*Hard rules honored: no `--approve`, no trades, no gate edits. Verdicts are the deterministic output of `process_proposal.py`.*
