# Promotion Brief — 2026-06-28 (Automated Analyst)

**Run date:** 2026-06-28  
**HEAD:** config v4  
**Cumulative trials:** 16 (ledger count; ledger undercounts vs documented 171 — see `trial-ledger-discrepancy` memory)  
**Weekly budget:** W26 (cap 10) — 0 consumed this run

---

## Summary

**No proposals to analyze.** The 5 JSON files present in `config/proposals/` are the same stale/invalid proposals that have been rejected at validation on every run since 2026-06-05. All were rejected again today before any backtest ran; no trials were consumed and the ledger was not written.

| File | Proposal ID | Verdict | Reason |
|------|-------------|---------|--------|
| `example.json` | `2026-06-02-w23-001` | REJECTED_VALIDATION | parent_config_version 1 ≠ HEAD 4 (stale) |
| `er_033.json` | `2026-06-02-w23-002` | REJECTED_VALIDATION | parent_config_version 1 ≠ HEAD 4 (stale) |
| `atr_floor_5.json` | `2026-06-02-w23-003` | REJECTED_VALIDATION | parent_config_version 1 ≠ HEAD 4 (stale) |
| `scaled_exits_example.json` | `2026-06-03-w23-exits-scaleout` | REJECTED_VALIDATION | parent_config_version 3 ≠ HEAD 4 (stale) |
| `opt_2026-06-07-opt-025424.json` | `2026-06-07-opt-025424` | REJECTED_VALIDATION | empty diff (no levers changed) |

No R6 gates, walk-forward, or lockbox were evaluated. Nothing was promoted.

---

## Status context

- **Idea space exhausted** per the 2026-06-26 session: all testable families (breakout, fade, trend, mean-reversion, exit models) are closed under current data. Real lever is longer data export.
- **`SecondEntryORB` (`2026-06-13-second-entry-orb`)** remains in the ledger as `passed` (+0.266R) but is dominated by HEAD v4 and its edge is suspected to be a level-fill artifact. Do not promote.
- **`TrendAlignedORB`** is the priority re-test candidate on longer data (failed only on sample_size 149 < 200; dominated HEAD on quality metrics). Needs a fresh M15 export covering more history before re-submission.

---

## Housekeeping recommendation (unchanged from prior briefs)

The 5 stale proposal files will continue to trigger this notice every run indefinitely. Consider archiving them:

```
mkdir config\proposals\archive
move config\proposals\example.json config\proposals\archive\
move config\proposals\er_033.json config\proposals\archive\
move config\proposals\atr_floor_5.json config\proposals\archive\
move config\proposals\scaled_exits_example.json config\proposals\archive\
move config\proposals\opt_2026-06-07-opt-025424.json config\proposals\archive\
```

New proposals must declare `parent_config_version: 4`.

---

_No `--approve` was run. No config was promoted. No trades placed. Gates untouched._
