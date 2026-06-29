# Promotion Brief — 2026-06-19 (Backtest Analyst)

**HEAD: config v4 (unchanged). Nothing PASSED. No action required from Cayden.**

## Summary

No promotable candidate this run. The only unprocessed files in `config/proposals/` are the
five stale seed/example fixtures — each was deterministically **REJECTED at validation** (before
any backtest), so none consumed a trial, touched `trial_ledger.jsonl`, or spent weekly budget.
Cumulative trials remain **13 (period 2026-W25, cap 10)** per the validator; the ledger tail is
unchanged.

There is **no 2026-06-19 auto-loop candidate** — the research engine has not written a proposal
for today (latest in the ledger is `2026-06-18-nr7-volatility-breakout`, already recorded FAILED).
So there was nothing new to backtest this cycle.

## Unprocessed proposal files (all rejected on the safety/lever validator)

| File | proposal_id | Verdict | Reason |
|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (no lever changed) |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | stale parent (v3 ≠ HEAD v4) |

These are repo seed/example files from the June 2–3 setup (plus the deliberately-rejected
scale-out worked example). They reference old parent versions or carry an empty diff, so the
validator rejects them **before** the backtester — correct behaviour, not a regression. A
`rejected_validation` outcome is intentionally NOT written to the ledger, so these will keep
reappearing as "unprocessed" every run.

## Recommendation

- **Do not run `--approve` on anything this cycle.** HEAD stays at config v4.
- Optional housekeeping (recurring): archive/delete the five stale fixtures from
  `config/proposals/` so future analyst runs aren't noise. Leaving them is harmless.

_Analyst run note: sandbox was missing `pyarrow`; installed it to load the parquet. All five
proposals re-confirmed REJECTED_VALIDATION via `scripts/process_proposal.py`; no `--approve` used,
ledger untouched._
