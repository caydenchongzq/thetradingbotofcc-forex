# Promotion Brief — 2026-06-26 (Automated Analyst)

**Run date:** 2026-06-26  
**HEAD:** config v4  
**Cumulative trials:** 16 (ledger count; ledger undercounts vs the documented 171 — see `trial-ledger-discrepancy` memory)  
**Weekly budget remaining:** 10/10 (W26, cap 10)

---

## Summary

5 proposal files were found with no `passed`/`failed`/`promoted`/`rejected` entry in `state/config/trial_ledger.jsonl`. All 5 were **rejected at validation** — no backtest was run, no trials were consumed, the ledger was not written.

| File | Proposal ID | Verdict | Reason |
|------|-------------|---------|--------|
| `example.json` | `2026-06-02-w23-001` | REJECTED_VALIDATION | parent_config_version 1 ≠ current 4 (stale) |
| `er_033.json` | `2026-06-02-w23-002` | REJECTED_VALIDATION | parent_config_version 1 ≠ current 4 (stale) |
| `atr_floor_5.json` | `2026-06-02-w23-003` | REJECTED_VALIDATION | parent_config_version 1 ≠ current 4 (stale) |
| `scaled_exits_example.json` | `2026-06-03-w23-exits-scaleout` | REJECTED_VALIDATION | parent_config_version 3 ≠ current 4 (stale) |
| `opt_2026-06-07-opt-025424.json` | `2026-06-07-opt-025424` | REJECTED_VALIDATION | empty diff (no levers changed) |

---

## Detail

### `2026-06-02-w23-001` — ER threshold 0.30 → 0.38
Stale: written against config v1, HEAD is now v4. Hypothesis (tighten ER to cut early-2024 chop) is interesting but the proposal itself cannot be promoted without being re-authored against v4.

### `2026-06-02-w23-002` — ER threshold 0.30 → 0.33  
Stale: written against config v1. Same structural issue as w23-001.

### `2026-06-02-w23-003` — ATR floor 4.0 → 5.0  
Stale: written against config v1. Hypothesis (filter dead low-vol sessions) is valid in principle but needs a fresh v4 proposal.

### `2026-06-03-w23-exits-scaleout` — scale-out 50% at 1R + runner to 2R  
Stale: written against config v3. Also known-rejected by the exit-model A/B (docs/EXIT_MODEL.md) — the multi-R exit family failed the lockbox for SessionBreakoutER. Do not re-author.

### `2026-06-07-opt-025424` — optimizer sweep result  
Empty diff. The optimizer likely produced this as a "no-change winner" (incumbent best). Cannot be submitted; re-run the optimizer if a fresh sweep is wanted.

---

## Recommendation

**No proposals to approve.** Nothing reached the backtest stage.

The three ER/ATR parameter proposals (`w23-001`, `w23-002`, `w23-003`) could be worthwhile to re-author against config v4 when the idea space opens up — but as of 2026-06-26 the documented research direction is to obtain longer data (priority: TrendAlignedORB re-test once a longer M15 export is available) before expending more trials on filter tweaks.

Do **not** re-author `w23-exits-scaleout` — the exit-model family is closed (0/4 exit variants passed).
