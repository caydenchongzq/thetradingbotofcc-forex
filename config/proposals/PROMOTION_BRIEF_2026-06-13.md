# Promotion Brief — 2026-06-13

**Analyst:** automated research-engine run (scheduled task `ftmo-research-engine`, spec 08)
**HEAD at run time:** config **v4** (`SessionBreakoutER`, ER 0.32 / ATR floor 5.0)
**Data:** `state/parquet/eurusd_m15.parquet` present (59,993 bars, 2024-01 → 2026-05).
**Trials:** cumulative **164** after this candidate (W24 ledger 7/10 spent). DSR run at `--trials 164`.

## TL;DR — one PASS, but it does NOT beat the incumbent → lean against promoting

`SecondEntryORB` is the **first** research-engine candidate ever to clear **all R6 gates + the
walk-forward + the sealed lockbox**. The additive "second attempt" hypothesis is confirmed in its
weak form: re-break entries are marginally *profitable* (~+0.04R each), not noise. **But** the
candidate is **dominated by HEAD v4 on every risk-adjusted axis** — a pass is necessary, beating the
incumbent is the sufficiency test (CLAUDE.md playbook §4). **Recommendation: do not promote.**

| metric | SecondEntryORB | incumbent HEAD v4 | Δ |
|---|---|---|---|
| trades (in-sample) | 252 | 224 | +28 |
| expectancy | +0.266R | +0.294R | **−0.028R** |
| profit factor | 1.84 | 1.99 | **−0.15** |
| Sharpe / Sortino | 3.10 / 4.70 | 3.36 / 5.36 | **−0.26 / −0.66** |
| max drawdown | $2,614 | $1,883 | **+$731 (worse)** |
| deflated Sharpe | 0.964 | 0.989 | −0.025 |
| WF folds profitable | 6/7 (1 weak −0.081R) | 7/7 | **−1 fold** |
| lockbox exp / PF | +0.248R / 1.75 | +0.324R / 2.15 | **−0.076R / −0.40** |
| net P&L | +$23,298 | +$22,875 | +$423 |

**Why it passes yet loses:** the 28 added re-break trades contribute ≈ +1.1 R total (≈ +0.04R each)
— above the cost line, but ~7× below the incumbent's +0.294R/trade. They add a little gross return
while *raising* drawdown, so return-per-unit-risk falls. Trade count was never the binding constraint
here (HEAD already clears the 200 floor by 24); **per-trade quality is**.

This is the same shape as the **2026-06-08 weekly-sweep winner**: a clean gate+lockbox pass that
nonetheless trails HEAD OOS → review, lean against promoting.

## If you want it anyway

This is a **strategy-name swap** (`SessionBreakoutER` → `SecondEntryORB`) plus one new param
(`second_entry.max_entries_per_side: 2`), not an `ALLOWED_LEVER` diff — so `process_proposal.py`
cannot auto-apply it. Promote by hand, after review, via `ConfigStore.promote(...)` with a config
whose `name` is `SecondEntryORB` (fully reversible via `rollback`). The candidate needs **no
live-mirror session** (exit/`manage()` path is byte-for-byte the incumbent's).

## Verdict & hygiene

- Library report: `docs/research/strategies/2026-06-13-second-entry-orb.md` (status **tested-passed**).
- Proposal JSON: `config/proposals/2026-06-13-second-entry-orb.json` (status `proposed`,
  `recommendation: do-not-promote`).
- Ledger: recorded `passed`, cumulative trials **164**, W24 **7/10**.
- Code/tests/docs committed; **nothing promoted**, `state/config/HEAD` untouched, live path untouched.

*Hard rules honored: no `--approve`, no trades, no gate edits, no writes to the config store.*
