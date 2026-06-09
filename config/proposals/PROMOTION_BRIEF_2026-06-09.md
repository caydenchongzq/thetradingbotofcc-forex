# Promotion Brief — 2026-06-09

**Analyst:** Backtest Analyst (scheduled run) · **HEAD:** config v4 · **Period:** 2026-W24 (cumulative trials 5/cap 10)

## Verdict summary

| Proposal file | proposal_id | Author | Result | Why |
|---|---|---|---|---|
| example.json | 2026-06-02-w23-001 | strategy_researcher | **REJECTED (validation)** | parent v1 ≠ current v4 — stale |
| er_033.json | 2026-06-02-w23-002 | strategy_researcher | **REJECTED (validation)** | parent v1 ≠ current v4 — stale |
| atr_floor_5.json | 2026-06-02-w23-003 | strategy_researcher | **REJECTED (validation)** | parent v1 ≠ current v4 — stale |
| scaled_exits_example.json | 2026-06-03-w23-exits-scaleout | strategy_researcher | **REJECTED (validation)** | parent v3 ≠ current v4 — stale |
| opt_2026-06-07-opt-025424.json | 2026-06-07-opt-025424 | optimizer | **REJECTED (validation)** | empty diff — changes no lever |

**Nothing to promote.** No proposal passed. None reached the backtester / walk-forward / lockbox, so there is no expectancy, PF, Sharpe, fold-stability, or lockbox result to report — each was rejected at the compare-and-swap validation gate that runs *before* any simulation. Consistent with this, none consumed a trial: the ledger and cumulative trial count (5) are unchanged, and HEAD stays v4.

## Detail

The first four are stale parent-version mismatches. `ConfigStore` promotion is a compare-and-swap on the parent pointer: a proposal can only be evaluated against the HEAD it was branched from. HEAD has since advanced to v4 (these were written against v1/v3 back on 2026-06-02–03), so they can never validate as-is. The two "example" files (`example.json`, `scaled_exits_example.json`) are templates and were never intended for promotion — `scaled_exits_example.json` is self-labelled "EXPECTED TO BE REJECTED".

The fifth, `opt_2026-06-07-opt-025424.json`, is a malformed optimizer output: its `diff` array is empty, so it changes no lever and is rejected before evaluation. Its hypothesis text claims a grid sweep over `exits.target_r_multiples` / `exits.move_be_after_r` with OOS expectancy +0.283R, but the recorded diff carries none of those changes — likely a serialization bug in that optimizer run. **No action needed**; the later, well-formed sweeps (`opt_2026-06-08-opt-001519`, already passed-but-not-promoted; trailed HEAD v4 OOS) supersede it.

## Recommendation

No review or promotion action for Cayden this run. The unprocessed queue is just stale templates plus one empty-diff artifact — all correctly rejected, none touching live. If you want the stale researcher hypotheses (ER tighten, ATR floor) re-tested, they'd need to be re-branched against v4 and re-proposed; the optimizer already covers that lever space in its weekly sweeps.

*No `--approve` was issued (analyst never promotes). No trades placed. Gates untouched.*
