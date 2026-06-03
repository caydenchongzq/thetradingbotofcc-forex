# Promotion Brief — 2026-06-03

**Analyst:** Backtest Analyst (automated, spec 06 §4)
**Current config head:** v2 (`regime.atr_floor_pips = 5.0`, promoted 2026-06-02)
**Week 2026-W23 trial budget:** 1 of 4 used

## Summary

Two unprocessed proposals were found and run through `scripts/process_proposal.py`. **Both were REJECTED at validation** before reaching the backtester, because each was authored against config v1 while the live head is now v2. No R6 gates, walk-forward folds, or lockbox were evaluated — validation rejection is a pre-flight check, so there are no expectancy/PF/Sharpe/OOS/lockbox numbers to report. These rejections are deterministic and not recorded in the trial ledger (no trial was consumed).

## Proposal 2026-06-02-w23-002 — `er_033.json` — REJECTED (validation)

- **Hypothesis:** Milder ER tighten (0.30 → 0.33) to trim worst low-ER chop while staying above the 200-trade sample floor.
- **Verdict:** `REJECTED_VALIDATION`
- **Reason:** `parent_config_version 1 != current 2 (stale proposal)`
- **Gates evaluated:** none (rejected before backtest)
- **Action needed:** This is a still-viable idea but must be **rebased onto v2** before it can be tested. Update `parent_config_version` to 2 in the proposal and re-run. Note v2 changed `atr_floor_pips`, not the ER gate, so the hypothesis remains intact on the new parent.

## Proposal 2026-06-02-w23-003 — `atr_floor_5.json` — REJECTED (validation)

- **Hypothesis:** Raise ATR floor 4.0 → 5.0 pips to stand aside in dead low-vol sessions.
- **Verdict:** `REJECTED_VALIDATION`
- **Reason:** `parent_config_version 1 != current 2 (stale proposal)`
- **Gates evaluated:** none (rejected before backtest)
- **Action needed:** **Redundant** — this exact change (`atr_floor_pips 4.0 → 5.0`) is already what produced the current head v2. No rebase needed; this proposal can be closed/archived.

## Proposals that PASSED

None. No promotion is recommended this run.

## Hard-rule compliance

No configs were promoted (no `--approve`), no trades placed, no gates edited.
