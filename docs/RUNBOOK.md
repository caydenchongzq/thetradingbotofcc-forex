# Ops runbook (spec 07 §10)

The engine runs as a Windows service (`scripts/service/`), supervised with auto-restart.
The deterministic spine is the source of safety; these procedures keep it alive and honest.

## Cold boot / new box
1. Auto-logon to a **console** session. (VPS: RDP locked to your IP / non-default port.)
2. Launch the FTMO **MT5 terminal**; confirm logged in to the **London** server and **NOT**
   from a US IP (FTMO hard rule). Enable **Algo Trading**.
3. `py scripts/mt5_probe.py` → confirm account + EURUSD specs.
4. Start the engine service (WinSW/NSSM) → it runs **startup reconciliation** before trading.
5. Confirm the first **healthchecks ping** + Telegram "engine up, MT5 connected".

## Daily checks
- Heartbeat green; no missed overnight pings.
- Tick/bar freshness OK; request count well under 2,000/day.
- P&L vs the 5% daily-loss limit; positions in MT5 == journal.
- Last backup present (on-box **and** off-box); no unacknowledged alerts.

## Crash recovery
- **Engine crash** → service auto-restarts → reconciliation → verify no duplicate positions.
- **MT5 disconnect** → watchdog re-inits with exponential backoff; if unrecoverable →
  fail-safe **hold/flatten** + alert.
- **Whole-box outage** → healthchecks fires (silence = go look) → reboot → cold-boot →
  reconcile vs MT5 **before** resuming.
- **Stale data** → engine refuses new trades, holds/flattens, alerts.

## Deploy / update
1. CI builds + runs tests/backtests on the pinned stack.
2. On the box: `git pull` (confirm pinned Python / `MetaTrader5` wheel / **MT5 terminal build**).
3. Restart the engine service → reconciliation runs (a deploy mid-position is as safe as a
   crash, by the same path) → confirm heartbeat + Telegram "up" before walking away.

## Kill-switch / flatten
- **Triggers:** approaching the daily-loss limit, request budget near 2,000, persistent
  disconnect, stale data, or **manual** — create a sentinel file `state\HALT` (the engine
  polls it each loop; `py -c "from src.ops import engage_killswitch as e; e('state','manual')"`).
- **Action:** cancel pendings, **flatten all engine-owned positions** (by magic), set the
  engine to halted, persist the reason, alert.
- **Stays halted until a human clears it** (`del state\HALT`) — never auto-resumes after a
  risk-driven kill (mirrors the Risk Governor's latched FLATTEN).

## Config promotion (improvement loop)
- Promoted versions live in `state\config\versions\` with `state\config\HEAD` the active one.
- The live engine adopts the new HEAD **only at a session boundary** (never mid-session).
- Rollback: `py -c "from src.agents import ConfigStore; ConfigStore('state', {}).rollback(N)"`.

## Backups
- `py scripts/backup_state.py` — schedule hourly + at the 00:00 CE(S)T reset.
- Restore test (B→C gate): restore a snapshot into a scratch dir and boot the engine from it.
