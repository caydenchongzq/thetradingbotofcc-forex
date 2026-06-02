# Implementation status

Tracks `docs/specs/` against the Phase-A milestones (`00-phase-roadmap.md` §2.2).
Build order: **04 journal → 02 risk → 03 execution → 05 backtest → 01 strategy → 06 improvement → 07 ops.**

## The deterministic spine is complete (implemented + tested)

| Milestone | Component | Tests |
|---|---|---|
| **A0** | Scaffold, env+`.env` config loader (MT5/execution), FTMO time utils | `tests/common/` |
| **A0** | **Journal & State** (04) — JSONL→SQLite→Parquet, crash-safe writes, partial-tail recovery, v2→v3 migration, staged-trade merge, read-only reader | `tests/journal/` (incl. property crash recovery) |
| **A1** | **Risk Governor** (02) — envelope, sizing, kill-switch + latch + daily reset, request budget, 13 forbidden checks | `tests/risk/` (incl. 400-case no-breach property) |
| **A2 (code)** | **Execution / MT5 adapter** (03) — `Broker` seam, idempotent persist-before-act, reconciliation (ticket-keyed), retcodes, request funding, advance-based health | `tests/execution/` |
| **A3** | **Backtest harness** (05) — event loop driving real Strategy+Governor, cost/fill model, FTMO breach sim, metrics, gates, deflated-Sharpe (tightens w/ trials) | `tests/backtest/` |
| **A4 (code)** | **Strategy engine** (01) — `SessionBreakoutER`: ER + Wilder ATR, DST-aware session gate, opening-range breakout + one-shot, regime gate, blackout (fail-closed), exit plan, move-BE | `tests/engine/` (incl. real-strategy-through-real-harness run) |
| A6 (partial) | Proposal allowed-lever validation (06 §3) | `tests/agents/` |

`178 passed`. Run: `python -m pytest`.

## Scripts (Windows host w/ MT5)
- `scripts/mt5_probe.py` — read-only terminal/account/symbol check.
- `scripts/mt5_smoke.py` — A2 live place→modify→close→reconcile (DRY-RUN unless `--yes`).
- `scripts/mt5_export.py` — pull EURUSD M15 from the FTMO terminal → clean → Parquet (server-tz→UTC).
- `scripts/run_backtest.py` — run SessionBreakoutER through the harness; `--walkforward` adds OOS folds + lockbox verdict (**A4**).
- `scripts/process_proposal.py` — run a proposal through the real backtester + gates, record the trial, `--approve` to promote (**A6**).
- `scripts/backup_state.py` — on/off-box state backup (schedule hourly + at the 00:00 reset).
- `scripts/service/` + `docs/RUNBOOK.md` — Windows service install + ops procedures (**07**).

## Pending / next
| Item | State |
|---|---|
| **A2 live** | Optional re-run of `mt5_smoke.py --yes` (now returns real fills) + kill-and-restart no-dupes check. |
| **A4 data** | Pipeline built (`src/data/`: clean/resample/store) + wired into `run()`. Remaining: run `mt5_export.py` then `run_backtest.py` on real history to see if the edge clears the gates. |
| **06 improvement loop** | Governance backbone DONE + tested (trial ledger, versioned config store w/ CAS mutex, drift policy, gated pipeline, agent specs, process_proposal CLI). Pending: wire the 3 agents as Cowork scheduled tasks. |
| **07 ops** | DONE: active-config HEAD loader (closes the promotion loop), watchdog backoff, Telegram alerts + healthchecks dead-man ping, on/off-box backups, sentinel kill-switch, live runner skeleton (`src/engine/run.py`), WinSW/NSSM service + `docs/RUNBOOK.md`. MT5-bound live loop validated on the Windows host. |
| vectorbt sweep | Deferred pre-filter (05 §2). |

## Broker facts (FTMO Free Trial demo, EURUSD)
Account 1513571406 @ FTMO-Demo, USD, 1:100, $100k. EURUSD 5-digit, pip $10/lot, lot step 0.01 (min 0.01/max 50), stops_level 0, ~0.1 pip demo spread. FTMO trial reports `trade_mode=0` (expected). Comments not reliably preserved → matching is ticket-keyed.

## Design notes
- **Broker seam:** all `MetaTrader5` calls isolated in `RealMT5Broker`; adapter logic tested via FakeBroker.
- **Signal seam:** Governor consumes its own request type (`risk/types.py:Signal`); the loop bridges the engine Signal via `engine/strategy.py:to_risk_signal()`.
- **Same code, two paths:** the backtester drives the *production* Strategy + RiskGovernor — a passing backtest is a statement about the code that will trade.
