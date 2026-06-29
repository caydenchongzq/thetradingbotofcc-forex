# Promotion Brief — 2026-06-20 (Backtest Analyst)

**HEAD: config v4 (unchanged). Nothing PASSED. No action required from Cayden.**

## Summary

No promotable candidate this run. The only JSON files in `config/proposals/` are the five
stale seed/example fixtures from the June 2–3 / June 7 setup. Each was deterministically
**REJECTED at validation** by `scripts/process_proposal.py` — *before* any backtester,
walk-forward, or lockbox ran — so none consumed a trial, wrote to `trial_ledger.jsonl`, or
spent weekly budget. Cumulative trials remain **14 (period 2026-W25, cap 10)** per the
validator; the ledger tail is unchanged (still ends at `2026-06-20-followthrough-time-stop`).

Today's genuine auto-loop candidate, **`2026-06-20-followthrough-time-stop`**, was already
self-recorded **FAILED** by the research engine at `2026-06-20T00:55:10Z` (anti-selective
time-stop exit — cut winners not whipsaws; lockbox FAIL). It is a terminal ledger entry with
no JSON in `config/proposals/`, so it is correctly out of scope for re-processing — no
trial double-count.

## Processed this run (all rejected on the safety/lever validator)

| File | proposal_id | Verdict | Reason |
|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | stale parent (v1 ≠ HEAD v4) |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (no lever changed) |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | stale parent (v3 ≠ HEAD v4) |

Because these reject at the pre-flight validator, no in-sample expectancy / PF / Sharpe, OOS
fold stability, or lockbox numbers exist for any of them — the arbiter never ran. This is
correct behaviour, not a regression: they reference old parent versions or carry an empty
diff. A `REJECTED_VALIDATION` outcome is intentionally NOT written to the ledger, which is
why these same five files keep resurfacing as "unprocessed" on every run.

## Recommendation

- **Do not run `--approve` on anything this cycle.** HEAD stays at config v4.
- Optional recurring housekeeping: archive or delete the five stale fixtures from
  `config/proposals/` so future analyst runs aren't noise. Leaving them is harmless — the
  validator stops them before they can ever touch the arbiter or the trial ledger.

_Analyst run note: executed autonomously (scheduled run, user not present). All five fixtures
re-confirmed REJECTED_VALIDATION via `scripts/process_proposal.py`; no `--approve` used; HEAD
pointer and `trial_ledger.jsonl` verified unchanged after the run._
