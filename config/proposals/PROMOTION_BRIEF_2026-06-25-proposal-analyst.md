# Promotion Brief — 2026-06-25

**Analyst:** Backtest Analyst (scheduled, automated)
**HEAD config version:** v4
**Cumulative trials (per ledger):** 16 (note: ledger undercounts vs. documented ~170; see trial-ledger-discrepancy memory)
**W26 budget remaining:** 10/10 (no trials consumed today — all rejections were pre-backtest)

---

## Proposals Evaluated

All 5 unprocessed proposals in `config/proposals/` were rejected at **validation** — none reached the backtester, so no trials were consumed.

| File | Proposal ID | Outcome | Reason |
|------|-------------|---------|--------|
| `example.json` | `2026-06-02-w23-001` | REJECTED_VALIDATION | Stale — parent v1 ≠ current v4 |
| `er_033.json` | `2026-06-02-w23-002` | REJECTED_VALIDATION | Stale — parent v1 ≠ current v4 |
| `atr_floor_5.json` | `2026-06-02-w23-003` | REJECTED_VALIDATION | Stale — parent v1 ≠ current v4 |
| `scaled_exits_example.json` | `2026-06-03-w23-exits-scaleout` | REJECTED_VALIDATION | Stale — parent v3 ≠ current v4 |
| `opt_2026-06-07-opt-025424.json` | `2026-06-07-opt-025424` | REJECTED_VALIDATION | Empty diff — no lever changed |

---

## Summary

No promotable candidates. All remaining proposals in the queue are historical artifacts (from W23, when HEAD was v1–v3) or malformed (empty diff). None consumed a trial.

**Recommendation:** These files can be archived or deleted to keep the proposals folder clean. The three W23 ER/ATR proposals (`example.json`, `er_033.json`, `atr_floor_5.json`) test ideas that may still be worth exploring against HEAD v4 — if so, they need fresh proposal files with `parent_config_version: 4`.

**No action required from Cayden today.**
