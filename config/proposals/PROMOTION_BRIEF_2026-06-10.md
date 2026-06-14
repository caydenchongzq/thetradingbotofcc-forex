# Promotion Brief — 2026-06-10

**Analyst:** Backtest Analyst (scheduled run) · **HEAD:** config v4 · **Period:** 2026-W24 (cumulative trials 6 / cap 10)

## Verdict summary

| Proposal file | proposal_id | Author | Result | Why |
|---|---|---|---|---|
| example.json | 2026-06-02-w23-001 | strategy_researcher | **REJECTED (validation)** | parent v1 ≠ current v4 — stale |
| er_033.json | 2026-06-02-w23-002 | strategy_researcher | **REJECTED (validation)** | parent v1 ≠ current v4 — stale |
| atr_floor_5.json | 2026-06-02-w23-003 | strategy_researcher | **REJECTED (validation)** | parent v1 ≠ current v4 — stale |
| scaled_exits_example.json | 2026-06-03-w23-exits-scaleout | strategy_researcher | **REJECTED (validation)** | parent v3 ≠ current v4 — stale |
| opt_2026-06-07-opt-025424.json | 2026-06-07-opt-025424 | optimizer | **REJECTED (validation)** | empty diff — changes no lever |

**Nothing to promote.** No proposal passed. None reached the backtester / walk-forward / lockbox, so there is no expectancy, PF, Sharpe, fold-stability, or lockbox result to report — each was rejected at the compare-and-swap validation gate that runs *before* any simulation. Consistent with this, none consumed a trial: the cumulative trial count (6) and HEAD (v4) are unchanged.

## Detail

The first four are stale parent-version mismatches. `ConfigStore` promotion is a compare-and-swap on the parent pointer, so a proposal can only validate against the exact HEAD it was branched from. HEAD has since advanced to v4 while these were written against v1/v3 (back on 2026-06-02–03), so they can never validate as-is. Two of them (`example.json`, `scaled_exits_example.json`) are templates never intended for promotion — `scaled_exits_example.json` is self-labelled "EXPECTED TO BE REJECTED" and matches the documented exit-model rejection in `docs/EXIT_MODEL.md`.

The fifth, `opt_2026-06-07-opt-025424.json`, is a malformed optimizer output: its `diff` array is empty, so it changes no lever and is rejected before evaluation. Its hypothesis text claims a grid sweep over `exits.target_r_multiples` / `exits.move_be_after_r` at OOS expectancy +0.283R, but the recorded diff carries none of those changes — a serialization bug in that one optimizer run. The later, well-formed sweep `opt_2026-06-08-opt-001519` (passed-but-not-promoted; trailed HEAD v4 OOS) supersedes it.

This is the same unprocessed queue as the 2026-06-09 run, with the same deterministic verdicts. Validation rejections are intentionally not written to the trial ledger (they consume no trial), so these files keep resurfacing as "unprocessed" each run until they are removed or re-branched.

## Recommendation

No review or promotion action for Cayden this run — nothing reached the gates, nothing touched live. Two housekeeping options to stop the queue from re-surfacing the same five files nightly:

- Archive or delete the two example templates (`example.json`, `scaled_exits_example.json`) and the empty-diff artifact (`opt_2026-06-07-opt-025424.json`) — they will never validate.
- If you still want the stale researcher hypotheses re-tested (ER tighten 0.30→0.33/0.38, ATR floor 4.0→5.0), they must be re-branched against v4 and re-proposed. The weekly optimizer sweep already covers that lever space, so this is optional.

*No `--approve` was issued (analyst never promotes). No trades placed. Gates untouched.*
