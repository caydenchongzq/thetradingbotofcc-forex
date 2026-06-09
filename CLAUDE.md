# CLAUDE.md — FTMO EURUSD trading bot

Standing brief for **any agent session**. Read this first, then open the relevant spec.
Canonical detail lives in `docs/specs/00–07` (`docs/specs/README.md` indexes them).
Current build state + backlog: `docs/IMPLEMENTATION_STATUS.md`.

## What this is
A deterministic EURUSD intraday bot for the FTMO 2-Step Challenge (strategy
`SessionBreakoutER`: London/NY-overlap opening-range breakout, ER + ATR regime gate),
wrapped in an **offline** AI improvement loop. The deterministic spine trades; the AI only
ever proposes config changes that the backtester and a human must approve.

## Hard invariants — never violate
1. **Deterministic spine.** `Strategy.evaluate/manage` are PURE functions of
   `(bars, now, context_bias, calendar)`: no wall-clock reads (only the injected `now`),
   no network, no hidden state. Same input ⇒ same output.
2. **The backtester is the arbiter.** Nothing ships unless `EventDrivenBacktester` clears
   every R6 gate **and** the walk-forward **and** the held-out lockbox. Per-trade
   expectancy alone is NOT a verdict — judge on the gates + lockbox. (See
   `docs/EXIT_MODEL.md`: a change with higher raw expectancy still got rejected for failing
   the lockbox.)
3. **live == backtest.** `src/engine/decide.py` is the one decision chain both paths run.
   If you change entry/exit/management semantics you MUST mirror them in BOTH the engine and
   the live path before promoting. All MT5 calls are isolated in `RealMT5Broker`; logic is
   tested via `FakeBroker`.
4. **Fail safe.** Any ambiguous/degraded state ⇒ no new trade (`NoSignal`). The Risk
   Governor can only ever reduce risk relative to the strategy's request, never increase it.
5. **AI is never inline on a live trade.** Improvement is offline: propose ⇒ backtest ⇒
   human-approved promotion through the versioned `ConfigStore` (compare-and-swap on parent,
   `HEAD` pointer, fully reversible).

## Security — non-negotiable
- `.env` is NEVER committed (MT5 password, R2 secret, Telegram token). `state/` is
  gitignored — never commit live data.
- Never log the MT5 account in from a US geolocation, even via VPN (FTMO ToS).
- Never disable TLS certificate verification in code.

## Commands
- Tests: `python -m pytest -q` (use the `py` launcher on Windows). Keep green.
- In-sample backtest: `py scripts/run_backtest.py`
- **Full OOS verdict (the bar every change must clear):** `py scripts/run_backtest.py --walkforward`
- A/B two configs on the same data: `py scripts/compare_exits.py` (copy as the template for any A/B)
- Sweep params for the best value (generic, any strategy): `py scripts/optimize.py config/optimize/example.yaml`
  (ranks by an OOS objective with the lockbox sealed; counts every combo into the DSR trial penalty; writes the winner as a proposal — never auto-promotes)
- Promote a human-approved config: `ConfigStore.promote(...)` in `src/agents/config_store.py`
  (or `scripts/process_proposal.py --approve` for loop-generated proposals).
- Data: the backtest reads `state/parquet/eurusd_m15.parquet` (export via
  `scripts/mt5_export.py` on the Windows host).

## Definition of done — R6 gates
expectancy ≥ 0.10R, PF ≥ 1.3, annualized Sharpe ≥ 1.0, Sortino ≥ 1.5, ≥ 200 trades,
DSR ≥ 0.95, and **ZERO** simulated FTMO breaches (hard gate). Walk-forward: no stitched-OOS
collapse, no severe fold (< −0.25R), ≥ 60% of folds profitable, and the held-out lockbox
passes its core gates. Raise `--trials` to the cumulative trial count (it tightens DSR).

## Layout
`src/engine` strategy + pure decision chain · `src/risk` Governor · `src/execution` MT5 seam
· `src/backtest` the arbiter (engine/metrics/gates/walkforward) · `src/journal` state ·
`src/agents` improvement loop + `ConfigStore` · `src/ops` live runner/alerts/watchdog ·
`src/data`. Config: `config/default.yaml` (versioned fallback). Both live and backtest load
the ConfigStore **HEAD** (`state/config/HEAD`) via `src/ops/runtime_config.resolve_strategy_config`.

## Strategy selection — registry + dev isolation
Strategies are built ONLY via `build_strategy(config)` in `src/engine/registry.py`
(`config["name"]` selects the class). **Live builds from the ConfigStore HEAD**, so it only
ever runs the *promoted* strategy. A strategy in development is registered there and
backtested **without** being promoted — testing it can never disturb live production.
- Dev backtest by name (keeps HEAD params): `py scripts/run_backtest.py --strategy MyNew`
- Dev backtest with its own config (bypasses HEAD): `py scripts/run_backtest.py --config-file config/dev/my.yaml`
- See registered names: `py scripts/run_backtest.py --list-strategies`
Dev runs print a banner and write NOTHING to the config store. A new strategy reaches live
ONLY by promoting a config whose `name` is it.

## Playbook — add a new indicator / concept / strategy
1. **Indicator** → `src/engine/indicators.py`, pure + unit-tested.
2. **Strategy** → implement the `Strategy` protocol in `src/engine` (`strategy.py`, or a new
   module): `evaluate()` returns `Signal | NoSignal`, `manage()` returns `ManageDecision`.
   Keep it pure; every degraded path ⇒ `NoSignal`. Give it a `name` and add one
   `register("Name", Class)` line in `src/engine/registry.py`.
   Choose **exit geometry from the strategy's own mechanism** — stop ~1.0–2.0×ATR, target
   R:R ≥ 1:1 (1:2–1:3 where a sub-50% win rate is expected). NEVER default to the incumbent's
   `1.2×ATR / 1R`; justify it or say why 1R fits (spec 08 §5.8).
3. Wire nothing live yet. Add unit tests under `tests/engine` and `tests/backtest`.
4. **Validate on real data (dev, store untouched):**
   `py scripts/run_backtest.py --strategy Name --walkforward` + an A/B vs the current HEAD
   (`compare_exits.py` pattern). It must clear ALL gates + lockbox AND not regress the
   incumbent. Higher per-trade expectancy that fails the lockbox = REJECT.
5. If it changes exit/management behavior, **mirror it into the live path**
   (`decide_manage` + `run._manage` + the adapter) and test with `FakeBroker` — restore
   `live == backtest` before promoting.
6. **Promote** via `ConfigStore` (human-approved) → the new version (with its `name`) becomes
   HEAD; live adopts it at the next session boundary. Reversible via `rollback`.
7. New tunable params → add them to `ALLOWED_LEVERS` in `src/agents/proposal.py` so the
   auto-loop can tune them within bounds.

## Gotchas
- VPS needs `numpy<2` (old CPU, no x86-64-v2); Python 3.12 (not 3.14); `tzdata` on Windows.
- Backtester uses a bounded `history_window` to stay O(N·W) — don't reintroduce O(N²) scans.
- If the Linux shell view of a file looks truncated vs the editor after a write, re-write it
  via a shell heredoc and `ast.parse` it before running pytest (a known mount-flush quirk).
