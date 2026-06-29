# Promotion Brief — 2026-06-29 (Automated Analyst)

**Result: No proposals to promote. All 5 unprocessed proposals rejected at validation.**

---

## Proposals Processed

| File | ID | Outcome | Reason |
|------|----|---------|--------|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | Stale: parent v1 ≠ current v4 |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | Stale: parent v1 ≠ current v4 |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | Stale: parent v1 ≠ current v4 |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | Stale: parent v3 ≠ current v4 |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | Empty diff (no levers changed) |

No backtests were run. No trials consumed. Cumulative trial count remains **171**.

---

## Notes

- The three W23 example proposals (`er_033`, `atr_floor_5`, `example`) and the scaled-exits example were drafted against config v1/v3 and are now stale. These can be archived or deleted.
- `opt_2026-06-07-opt-025424` has an empty `diff` array — it was likely generated as a placeholder and never populated.
- No action required from Cayden for any of these.
