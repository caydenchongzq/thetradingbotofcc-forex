# Implementation status

Tracks `docs/specs/` against the Phase-A milestones (`00-phase-roadmap.md` §2.2).
Build order: **04 journal → 02 risk → 03 execution → 05 backtest → 01 strategy → 06 improvement → 07 ops.**

## Status: BUILD COMPLETE — forward-testing (2026-06-03)

All eight specs (00–07) implemented, tested (192 passing), committed to git, and deployed.
The engine is running unattended on a London Windows VPS against the FTMO account
(config v2), journal syncing to Cloudflare R2, the local Claude improvement-loop agents
scheduled. Remaining work is validation-process and strategy R&D, not core build.

| Spec | Component | State |
|---|---|---|
| 01 | Strategy engine (SessionBreakoutER) | ⚠️ entry-fill artifact — no live edge (see below); code now market entry, not promotable |
| 02 | Risk Governor | ✅ |
| 03 | Execution / MT5 adapter | ✅ (A2 live place→close verified) |
| 04 | Journal & State | ✅ |
| 05 | Backtest harness + walk-forward + lockbox | ✅ (vectorbt/MC/PBO deferred) |
| 06 | Improvement loop (param tuning) | ✅ governance + 3 scheduled agents |
| 07 | Ops / deployment | ✅ VPS + WinSW + R2 sync + alerts + file-sink |

## ⚠️ 2026-06-15 — SessionBreakoutER has NO live-realizable edge (entry-fill artifact)
The retcode-10015 live rejections exposed a live ≠ backtest break at the **entry seam**: the
backtest filled a breakout stop *at the level*, a fill the live path cannot place after the bar
closes beyond it. A/B on the real Parquet (same 224 trades, only the fill differs): stop-at-level
**+0.391R** (not live-placeable) vs the two live-faithful fills — resting-stop touch **−0.267R**
and market-at-close **−0.024R**; a tight-overshoot filter tops out +0.008R/99 trades. The edge was
the unfillable level fill. **Incumbent code switched to market entry (live-safe, NOT profitable →
do not deploy expecting v4 numbers); needs a strategy rethink, not an entry patch.** Resting-stop
machinery kept as generic capability + dev strategy `SessionBreakoutERResting` + `entry.mode` lever.
Full write-up: `docs/RESTING_STOP_FIX.md` §4–5; library entry `2026-06-15-resting-stop-and-market-entry`;
generalizable rule added to CLAUDE.md invariant #3 + spec 08 validate step.

## Validation in progress
- **A5 forward test** on the FTMO account — running; watching live fills vs backtest.
- **Kill-and-restart no-duplicate drill** — still to do on the demo.

## Improvement backlog (the next round — see chat discussion 2026-06-03)
The live loop AUTO-TUNES PARAMETERS only (the allowed-lever library). Structural change is
human/agent dev work, validated through the SAME harness + walk-forward + lockbox + gates.
Prioritised:
1. **Full exit model in the engine** — 2R + partials + break-even + trailing (currently 100% at 1R).
   Lets winners run; likely the single biggest equity-curve change. Then expose trail params as levers.
2. **New entry/regime filters** — higher-timeframe trend bias, time-of-day/day-of-week, vol-of-vol gate.
3. **New Strategy implementations** — mean-reversion, other sessions; swappable behind the Strategy interface.
4. **Second instrument** — per-instrument config profile; prove the pipeline generalises.
5. **Validation rigor** — Monte-Carlo reshuffle, PBO/CSCV, parameter-stability maps; vectorbt sweep.
6. **R8 fundamental overlay** — shadow-mode news/macro bias into the context_bias seam.
7. **Automated research engine (spec 08)** — daily scheduled session: online research →
   strategy library recall → dev-isolated build → walk-forward → report.
   **M1–M4 built 2026-06-07**: library at `docs/research/strategies/` (3 seeds),
   `RESEARCH_ENGINE` agent spec, weekly cap → config (10), `ftmo-research-engine` task
   daily 08:30 SGT (first run 2026-06-08 = supervised dry run); M5 review one-shot task
   fires 2026-06-21. Plan: `docs/specs/08-research-engine.md`.

## (existing detail below)
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

`190 passed`. Run: `python -m pytest`.

**Live decision loop (A5):** `src/engine/run.py` `_on_tick` now fetches closed bars from MT5, reads live account/day-state (00:00 reset), runs the same strategy->Governor->Execution chain the backtester validated (`src/engine/decide.py`), journals trades, and is idempotent per bar. The full path is tested end-to-end with a FakeBroker (`tests/engine/test_live_loop.py`) — no MT5 needed. Ready to forward-test on the FTMO free trial once `.env` + Algo Trading are set.

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
