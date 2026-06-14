# Promotion Brief — 2026-06-14 (Backtest Analyst, proposal-pipeline sweep)

**Analyst:** automated run (scheduled task `ftmo-analyst`, spec 06 §4)
**HEAD at run time:** config **v4** (`SessionBreakoutER`, ER 0.32 / ATR floor 5.0)
**Data:** `state/parquet/eurusd_m15.parquet` present and read successfully.
**Trials:** cumulative **unchanged** — no backtest ran, no trial recorded, no W24 budget consumed.

> Scope note: this is the *proposal-pipeline* sweep over the loose JSON files in
> `config/proposals/`. Today's research-engine candidate, `2026-06-14-trend-aligned-orb`,
> is already recorded `failed` in `state/config/trial_ledger.jsonl` and has no JSON in the
> proposals folder, so it is **not** re-processed here.

## TL;DR — nothing to promote

Five proposal JSONs had no `passed`/`failed`/`promoted`/`rejected` entry in the trial
ledger, so I ran each through `scripts/process_proposal.py` (no `--approve`). **All five were
rejected at the deterministic validation stage — none reached the backtester, none recorded a
trial, none consumed the W24 budget.** There are **no PASSED proposals**, so there is nothing
for you to review or promote.

| proposal file | proposal_id | verdict | reason |
|---|---|---|---|
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | REJECTED_VALIDATION | empty diff — a proposal must change ≥1 lever |
| `example.json` | 2026-06-02-w23-001 | REJECTED_VALIDATION | stale parent: v1 ≠ current v4 |
| `er_033.json` | 2026-06-02-w23-002 | REJECTED_VALIDATION | stale parent: v1 ≠ current v4 |
| `atr_floor_5.json` | 2026-06-02-w23-003 | REJECTED_VALIDATION | stale parent: v1 ≠ current v4 |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | REJECTED_VALIDATION | stale parent: v3 ≠ current v4 |

Because each fails `validate_proposal` **before** the backtest, there is no in-sample
expectancy/PF/Sharpe, no OOS fold breakdown, and no lockbox result to report — the gate never
opened. (Identical outcome to the 2026-06-13 analyst run; these are the same recurring
fixtures.)

## What these files actually are

- **`opt_2026-06-07-opt-025424.json`** — an optimizer artifact whose `diff` is empty (`[]`).
  An optimizer run that produced no lever change; correctly a no-op. The hypothesis text
  claims a +0.283R OOS sweep result, but the file carries no diff to apply, so nothing can be
  backtested.
- **`example.json`, `er_033.json`, `atr_floor_5.json`, `scaled_exits_example.json`** — W23
  (2026-06-02/03) seed/worked-example fixtures. They diff against config **v1/v3**; HEAD has
  since advanced to **v4** (their `from:` values — ER 0.30, ATR 4.0 — describe v1, not the
  live strategy). `scaled_exits_example.json` is self-described: *"Kept as a worked example …
  EXPECTED TO BE REJECTED."* These predate the live strategy and are not current proposals.

## Recommended action for Cayden

**No promotion to consider** — nothing passed.

Housekeeping (unchanged from yesterday's recommendation, no action taken by me):
`REJECTED_VALIDATION` writes **no** ledger entry, so these five files will be re-flagged as
"unprocessed" and re-validated on **every** future daily run. To stop the recurring noise,
move the fixtures out of the active folder — e.g. `config/proposals/examples/` or
`config/proposals/archive/`. I did **not** move anything (read-only analyst run). If any W23
idea is worth re-testing against the live strategy, re-issue it as a fresh proposal with
`parent_config_version: 4` and a non-empty diff; only then would the gate run it.

## Verdict & hygiene

- Proposals validated: **5**; passed gate: **0**; backtests run: **0**.
- Ledger: **untouched** (14 lines before and after; no trials recorded); W24 budget unchanged.
- HEAD (`state/config/HEAD`) still **v4**; live path untouched; config store untouched.
- The `git` working-tree "modified" marks on the two `opt_*.json` files are pre-existing
  CRLF line-ending normalization (content byte-identical, mtimes unchanged) — **not** caused
  by this run.

*Hard rules honored: no `--approve`, no trades, no gate edits, no writes to the config store.*
