# Promotion Brief — 2026-06-11

**Analyst:** automated Backtest Analyst run (spec 06 §4)
**Config HEAD:** v4 (unchanged) · **Period:** 2026-W24, cumulative trials = 7 (cap 10)
**Data:** `state/parquet/eurusd_m15.parquet` present.

## Summary

Five proposals in `config/proposals/` had no terminal status in the trial ledger and were
processed. **All five were REJECTED at validation — none reached the backtester**, so no
gates/lockbox were evaluated and nothing was promoted. HEAD remains v4. **No action
recommended.** These are stale leftovers, not live candidates.

| Proposal | File | Verdict | Reason |
|---|---|---|---|
| 2026-06-02-w23-001 | example.json | REJECTED_VALIDATION | stale parent: parent v1 ≠ current v4 |
| 2026-06-02-w23-002 | er_033.json | REJECTED_VALIDATION | stale parent: parent v1 ≠ current v4 |
| 2026-06-02-w23-003 | atr_floor_5.json | REJECTED_VALIDATION | stale parent: parent v1 ≠ current v4 |
| 2026-06-03-w23-exits-scaleout | scaled_exits_example.json | REJECTED_VALIDATION | stale parent: parent v3 ≠ current v4 |
| 2026-06-07-opt-025424 | opt_2026-06-07-opt-025424.json | REJECTED_VALIDATION | empty diff (no lever changed) |

## Detail

The first four are pre-promotion **example/template files** parented to old config versions
(v1/v3). The ConfigStore compare-and-swap requires a proposal's `parent_config_version` to
equal current HEAD (now v4), so each is correctly rejected as stale before any backtest runs.
`scaled_exits_example.json` is the deliberately-kept worked example documented to fail the
lockbox — it never even gets that far now because of the stale parent.

`opt_2026-06-07-opt-025424.json` is parented to v4 (current) but carries an **empty diff** —
the optimizer's exit-multiple sweep found no improving change, so the proposal changes no
lever and is rejected as a no-op.

## Notes for Cayden

- **No promotions available** this run — nothing passed.
- Validation rejections are **not** written to the trial ledger (no backtest = no trial), so
  these five files will be re-picked as "unprocessed" on every future analyst run. To stop the
  recurring noise, consider archiving/deleting the stale examples
  (`example.json`, `er_033.json`, `atr_floor_5.json`, `scaled_exits_example.json`,
  `opt_2026-06-07-opt-025424.json`) or re-parenting any you still want tested to v4.
- Cumulative W24 trial budget untouched: 7/10 used.
