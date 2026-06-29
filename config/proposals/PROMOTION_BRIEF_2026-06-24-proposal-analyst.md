# Promotion Brief — 2026-06-24 (Backtest Analyst, spec 06 §4)

**Verdict: nothing to promote. No actionable proposals.**

HEAD = config **v4**. Ledger trial count = 15. W26 budget = 10, none spent today.
No state was mutated by this run: `trial_ledger.jsonl` (19 lines) and `HEAD` (v4) are
MD5-identical before and after, zero trials consumed, zero config-store changes.

## What was found

`config/proposals/` holds **5 proposal JSONs whose IDs are absent from `trial_ledger.jsonl`**.
Every genuine research_engine / optimizer proposal through 2026-06-21 is already recorded
(passed/failed) in the ledger. The 5 stragglers are the same **stale W23 seed / worked-example
fixtures** that every prior daily run has correctly rejected — they target an old parent config
(or change no lever), so they can never clear the deterministic validation gate against HEAD v4.

I ran `scripts/process_proposal.py` on each. The gate rejected all five at **validation**,
*before any backtest* — so no in-sample / OOS / lockbox numbers are produced, no trial is
recorded, and the config store is never touched:

| File | proposal_id | Verdict | Reason |
|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | parent v1 ≠ current v4 (stale) |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | parent v1 ≠ current v4 (stale) |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | parent v1 ≠ current v4 (stale) |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | parent v3 ≠ current v4 (stale) |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (no lever changed) |

A proposal must target the live HEAD (v4) and change at least one allowed lever; none of these
do. `scaled_exits_example.json` is explicitly the "expected to be rejected" worked example
(the EXIT_MODEL.md scale-out that fails the lockbox); `opt_2026-06-07` is an optimizer artifact
whose winning diff resolved to HEAD itself (empty). The backtester never ran for any of them —
validation is the terminal stop.

## Recommendation

**No promotions.** Nothing here is a live candidate, so there is nothing for Cayden to review
and `--approve`. No action required.

Housekeeping (optional, your call — untouched): these 5 permanently-stale fixtures resurface in
this folder every day. To stop the analyst listing them, archive them under
`config/proposals/_fixtures/` or delete the three v1 seeds outright. The genuine pipeline
(research_engine + optimizer) is unaffected either way.

---
*Process: read `trial_ledger.jsonl` → identified 5 IDs not yet processed → ran
`process_proposal.py` on each (deterministic gate; verdict not editable) → confirmed
ledger (19 lines) and HEAD (v4) MD5-unchanged after. The arbiter, not the analyst, decides
every verdict. Sandbox note: `pyarrow` was pip-installed so the backtester could read the
parquet; all five still stopped at validation regardless.*
