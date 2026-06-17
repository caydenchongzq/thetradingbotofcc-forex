# Promotion Brief — 2026-06-17 (Backtest Analyst)

**Verdict: nothing to promote. HEAD stays v4.**

No new strategy candidate was queued for today. The only proposal JSONs in
`config/proposals/` that are absent from `state/config/trial_ledger.jsonl` are five
**stale templates/examples** from the W23 bootstrap plus one empty optimizer artifact.
All six were re-run through `scripts/process_proposal.py` and were stopped at the
deterministic **validation** stage — none reached the backtester, walk-forward, or
lockbox, so there is no expectancy / PF / Sharpe / fold / lockbox result to report for
any of them.

| Proposal file | proposal_id | Diff | Result | Reason |
|---|---|---|---|---|
| `example.json` | 2026-06-02-w23-001 | er_threshold 0.30→0.38 | REJECTED_VALIDATION | stale parent v1 ≠ current v4 |
| `er_033.json` | 2026-06-02-w23-002 | er_threshold 0.30→0.33 | REJECTED_VALIDATION | stale parent v1 ≠ current v4 |
| `atr_floor_5.json` | 2026-06-02-w23-003 | atr_floor_pips 4.0→5.0 | REJECTED_VALIDATION | stale parent v1 ≠ current v4 |
| `scaled_exits_example.json` | 2026-06-03-w23-exits-scaleout | scaled exits / BE move | REJECTED_VALIDATION | stale parent v3 ≠ current v4 |
| `opt_2026-06-07-opt-025424.json` | 2026-06-07-opt-025424 | (none) | REJECTED_VALIDATION | empty diff — must change ≥1 lever |

Already-processed proposals (in the ledger, skipped): `2026-06-03-opt-084109` (passed),
`2026-06-08-opt-001519` (passed), `2026-06-13-second-entry-orb` (passed — dominated by
HEAD v4, do-not-promote per prior brief). The genuine daily research candidates through
2026-06-16 are all recorded as `failed`.

## What this means
The improvement loop produced **no live candidate** for today, so there is nothing for
you to review or `--approve`. Config HEAD remains **v4**. No trades, no gate edits, no
promotions were made.

## Housekeeping note (no action required, but recommended)
Validation rejections are **not** written to the trial ledger, so these five stale
example/template files will resurface and re-fail validation on every daily run. To stop
the recurring noise, consider moving them out of `config/proposals/` (e.g. into an
`config/proposals/_archive/` or `config/examples/` folder):

- `example.json`, `er_033.json`, `atr_floor_5.json` (W23 single-lever templates, parent v1)
- `scaled_exits_example.json` (parent v3; scaled-exit family already rejected — see EXIT_MODEL.md)
- `opt_2026-06-07-opt-025424.json` (empty-diff optimizer artifact)

Cumulative trial count reported by the engine this run: **12 for period 2026-W25**
(weekly cap 10). Take the authoritative `--trials` figure from the latest library report
rather than the ledger file when launching sweeps.
