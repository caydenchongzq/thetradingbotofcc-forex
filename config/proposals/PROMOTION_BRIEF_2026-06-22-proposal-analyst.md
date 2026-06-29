# Promotion Brief — 2026-06-22 (Backtest Analyst, spec 06 §4)

**Verdict: nothing to promote. No actionable proposals.**

HEAD = config **v4**. Cumulative trials (ledger) = 15. W26 budget = 10, none spent today.
No state was mutated by this run: zero ledger writes, zero config-store changes, no trials consumed.

## What was found

`config/proposals/` holds **5 proposal JSONs whose IDs are absent from `trial_ledger.jsonl`**.
Every genuine research_engine / optimizer proposal through 2026-06-21 is already recorded
(passed/failed) in the ledger. The 5 stragglers are all **stale W23 seed / worked-example
fixtures** that target an old parent config and can never pass the deterministic validation
gate against the current HEAD.

I ran `scripts/process_proposal.py` on each. The gate rejected all five at **validation**
(before any backtest, so no trial is recorded and the config store is never touched):

| File | proposal_id | Verdict | Reason |
|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | parent v1 ≠ current v4 (stale) |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | parent v1 ≠ current v4 (stale) |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | parent v1 ≠ current v4 (stale) |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | parent v3 ≠ current v4 (stale) |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (no lever changed) |

These are the same fixtures that have correctly been skipped by every prior daily run — a
proposal must target the live HEAD (currently v4) and change at least one allowed lever, and
none of these do. `scaled_exits_example.json` is explicitly a "expected to be rejected" worked
example (the EXIT_MODEL.md scale-out that fails the lockbox); `opt_2026-06-07` is an optimizer
artifact whose winning diff resolved to HEAD itself (empty). No in-sample / OOS / lockbox
numbers are produced for any of them because the backtester never ran — validation is the
terminal stop.

## Recommendation

**No promotions.** Nothing here is a live candidate, so there is nothing for Cayden to review
and `--approve`. No action required.

Housekeeping (optional, your call — I did not touch them): these 5 permanently-stale fixtures
will keep surfacing in this folder daily. If you'd rather the analyst stop listing them,
archive them under e.g. `config/proposals/_fixtures/` or delete the three v1 seeds outright.
The genuine pipeline (research_engine + optimizer) is unaffected either way.

---
*Process: read `trial_ledger.jsonl` to identify unprocessed IDs → ran `process_proposal.py`
on each (deterministic gate, verdict not editable) → confirmed ledger/HEAD unchanged after.
The arbiter, not the analyst, decides every verdict.*
