# Promotion Brief — 2026-06-13 (Backtest Analyst, proposal-pipeline sweep)

**Analyst:** automated run (scheduled task `ftmo-analyst`, spec 06 §4)
**HEAD at run time:** config **v4** (`SessionBreakoutER`, ER 0.32 / ATR floor 5.0)
**Data:** `state/parquet/eurusd_m15.parquet` present.
**Trials:** cumulative **unchanged** (W24 ledger 9/10 — *no slot consumed by this run*).

> Note: this is the *proposal-pipeline* sweep over loose JSON files in `config/proposals/`.
> Today's other brief (`PROMOTION_BRIEF_2026-06-13.md`, from the `ftmo-research-engine` task)
> already covers `SecondEntryORB`, which is recorded `passed` in the ledger and is **not**
> re-processed here.

## TL;DR — nothing to promote

Five proposal JSONs in `config/proposals/` had no `passed`/`failed`/`promoted`/`rejected`
entry in `state/config/trial_ledger.jsonl`, so I ran each through
`scripts/process_proposal.py`. **All five were rejected at the deterministic validation
stage — none reached the backtester, none recorded a trial, none consumed the W24 budget.**
There are **no PASSED proposals**, so there is nothing for you to review or promote.

| proposal file | proposal_id | verdict | reason |
|---|---|---|---|
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff (a proposal must change ≥1 lever) |
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | stale parent: v1 ≠ current v4 |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | stale parent: v1 ≠ current v4 |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | stale parent: v1 ≠ current v4 |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | stale parent: v3 ≠ current v4 |

Because each fails `validate_proposal` *before* the backtest, there is no in-sample
expectancy/PF/Sharpe, no OOS fold breakdown, and no lockbox result to report — the gate
never opened.

## What these files actually are

- **`opt_2026-06-07-opt-025424.json`** — an optimizer artifact (2026-06-07) whose `diff` is
  empty (`[]`). An optimizer run that produced no lever change; correctly a no-op. Its
  hypothesis text claims an OOS sweep result, but the file carries no diff to apply.
- **`example.json`, `er_033.json`, `atr_floor_5.json`, `scaled_exits_example.json`** — W23
  (2026-06-02/03) seed/worked-example fixtures. They diff against config **v1/v3**; HEAD has
  since advanced to **v4** (their `from:` values — ER 0.30, ATR 4.0 — describe v1, not the
  live strategy). `scaled_exits_example.json` is self-described: *"Kept as a worked example
  … EXPECTED TO BE REJECTED."* These predate the trial ledger and are not live proposals
  against the current strategy.

## Housekeeping recommendation (no action taken)

`REJECTED_VALIDATION` does **not** write a ledger entry, so these five files will be flagged
as "unprocessed" on **every** future daily run and re-validated each time. To stop the daily
noise, consider moving the fixtures out of the active proposals folder — e.g.
`config/proposals/examples/` or `config/proposals/archive/` — so only genuine, current-parent
proposals live in `config/proposals/`. I did **not** move anything (read-only analyst run).

If you want any of the W23 ideas re-tested against the live strategy, they must be re-issued
as fresh proposals with `parent_config_version: 4` (and a non-empty diff). At that point the
gate would actually run them.

## Verdict & hygiene

- Proposals validated: **5**; passed gate: **0**; backtests run: **0**.
- Ledger: **untouched** (no trials recorded); cumulative trial count and W24 budget (9/10) unchanged.
- HEAD (`state/config/HEAD`) untouched; live path untouched; config store untouched.

*Hard rules honored: no `--approve`, no trades, no gate edits, no writes to the config store.*
