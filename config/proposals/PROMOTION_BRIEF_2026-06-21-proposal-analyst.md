# Promotion Brief — 2026-06-21 (Backtest Analyst)

**HEAD: config v4 (unchanged). Nothing PASSED. No action required from Cayden.**

## Summary

No promotable candidate this run. The five loose JSON proposals in `config/proposals/`
that lack a terminal `trial_ledger.jsonl` entry are the same stale seed/example fixtures
from the June 2–3 / June 7 setup. Each was deterministically **REJECTED at validation** by
`scripts/process_proposal.py` — *before* any backtester, walk-forward, or lockbox ran — so
none consumed a trial, wrote to the ledger, or spent weekly budget. Cumulative trials remain
**14 (period 2026-W25, cap 10)** per the validator; the ledger is unchanged at 18 lines
(still ends at `2026-06-20-followthrough-time-stop`). HEAD pointer verified still **v4**.

The one genuine recent candidate JSON, `2026-06-13-second-entry-orb.json`, already carries a
`passed` entry in the ledger (recorded 2026-06-13) and was correctly **not** re-processed —
no trial double-count. It remains a do-not-promote (PASSED all gates in isolation but is
dominated by HEAD v4; see the 2026-06-13 brief).

## Processed this run (all rejected on the safety/lever validator)

| File | proposal_id | Verdict | Reason |
|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (no lever changed) |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | stale parent (v3 ≠ HEAD v4) |

Because each fails `validate_proposal` *before* the backtest, there is no in-sample
expectancy / PF / Sharpe, no OOS fold breakdown, and no lockbox result to report — the
arbiter never ran. This is correct behaviour, not a regression: they reference old parent
versions or carry an empty diff. A `REJECTED_VALIDATION` outcome is intentionally NOT
written to the ledger, which is why these same five fixtures keep resurfacing as
"unprocessed" on every run.

## Recommendation

- **Do not run `--approve` on anything this cycle.** HEAD stays at config v4.
- Optional housekeeping (recurring): archive or delete the five stale fixtures from
  `config/proposals/` so future analyst runs aren't noise. Leaving them is harmless — the
  validator stops them before they can ever touch the arbiter or the trial ledger.

_Analyst run note: executed autonomously (scheduled run, user not present). All five fixtures
re-confirmed REJECTED_VALIDATION via `scripts/process_proposal.py`; `2026-06-13-second-entry-orb`
skipped as already `passed` in the ledger; no `--approve` used. `trial_ledger.jsonl` (18 lines)
and `state/config/HEAD` (v4) verified unchanged after the run. Sandbox note: `pyarrow` had to be
installed to load the parquet so the validator could run; this does not affect the deterministic
verdicts._
