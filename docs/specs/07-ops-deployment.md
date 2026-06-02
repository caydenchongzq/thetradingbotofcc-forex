# 07 — Ops & Deployment (R7)

> How the engine runs reliably, unattended — phased **local Windows PC first, London VPS before the funded account**. Supervision, watchdog, alerting, secrets, backups, safe restart, parity, and the runbook. Same artifact, env-driven config, on every host.
>
> Source: R7 findings + the 2026-06-02 host-phasing decision. The hard external rule: **never log the MT5 account in from a US geolocation, even via VPN** (FTMO).

---

## 1. Host phasing (the decision)

| Phase | Host | Account stage | Why here |
|---|---|---|---|
| **A** | **Local Windows PC** | dev → demo → free-trial → **challenge** | Parity is free (MT5 is Windows-only anyway); a home-PC outage on demo/challenge only costs a retry — challenges have no time limit. Iterate cheaply. |
| **B** | **London Windows VPS** (4 vCPU / 8 GB target, NVMe, 99.9%+, LD4 proximity) | **funded** | An outage on funded capital is an uninsurable breach risk → pay for 24/5 exactly when uptime protects real money. |
| **C** | VPS unchanged; AI loop on a separate Linux box | funded (scaled) | Restores live/improvement isolation; full API runtime (spec 06 §2.2). |

**Local-phase hardening (do it anyway, makes cut-over a formality):** disable sleep/hibernate and auto-restart-after-update; UPS if available; confirm watchdog + heartbeat fire; keep the off-box journal backup. These are the same controls the VPS gets.

**Migration (A→B):** provision the VPS in advance, run it in parallel on **demo** for a few sessions to confirm parity, then cut over before the funded account. Same `git pull` + service-restart path, same reconcile-on-startup.

---

## 2. Two processes to keep alive (Windows box)

1. **The MT5 terminal GUI** — a GUI app needing an interactive desktop session (R7). Keep the box auto-logged-in to a console session; launch MT5 into it; the **watchdog** owns restarting it.
2. **The Python engine** — supervised as a **Windows service via NSSM or WinSW** (not Task Scheduler, which is per-user/run-and-exit). NSSM wraps `python.exe engine.py`, integrates with the Service Control Manager, and auto-restarts on failure.

So: supervise the *engine* as a service; let the watchdog own the *terminal*. (PM2 is fine for the Python side on the **Linux AI box** in Phase C, not for the Windows GUI terminal.)

---

## 3. Application-level watchdog (R3 requirement)

A loop (in-engine or sibling process) every N seconds:
- Calls `mt5.terminal_info()` / `account_info()`; if `None` or `last_error()` signals disconnect → tear down and **re-`initialize()`/`login()`** with exponential backoff (spec 03 §6).
- Pulls the latest EURUSD tick/bar and checks **freshness** (within tolerance for the active session). Stale ⇒ trigger the **fail-safe (flatten or hold, never guess)**, not a new trade.
- If MT5's process is gone, restarts the terminal executable.
- Emits the **heartbeat** (§5) meaning "engine alive **and** MT5 connected **and** data fresh".

---

## 4. What to detect & alert on (R7)

Process crash (service/watchdog down); MT5 disconnect / failed `initialize`; stale data during an active session; failed/rejected orders (retcode ≠ DONE); **approaching the daily-loss limit** (from the Risk Governor, spec 02); **request-budget approaching 2,000/day**; reconciliation ambiguity on restart; backup failure; disk pressure.

---

## 5. Alerting + heartbeat (dead-man's-switch)

Two layers (R7):
1. **Telegram bot** for actionable events (order reject, disconnect, daily-loss proximity, fail-safe flatten, kill-switch). A bot token + chat id + a one-line HTTP POST; email as slower backup.
2. **healthchecks.io dead-man's-switch**: the engine pings a healthchecks URL on every successful loop iteration; if pings stop on schedule, healthchecks notifies (Telegram + 25+ channels). This is the catch-all that fires **even if the whole box dies** — which in-process alerts cannot. Design the ping to mean "alive + connected + fresh," so silence unambiguously means "go look."

---

## 6. Secrets (R7)

MT5 login/password, Telegram token, healthchecks URL, any API keys. Never hard-code or commit. Baseline on a single box: **env vars / a `.env` outside the repo with locked-down NTFS ACLs**, loaded at process start. Stronger: **Windows DPAPI-encrypted file** (machine-bound) or a hosted secrets manager if already on that cloud (Phase C). Pair with: strong unique passwords, 2FA on the box and trading accounts, **RDP locked to a known IP / non-default port**, dedicated IP (VPS).

---

## 7. State backups (R7, ties to spec 04 §6)

- **On-box:** timestamped SQLite + the day's JSONL to a second path, hourly + at the 00:00 reset.
- **Off-box:** mirror to object storage / the AI box (Phase A: another disk or cloud off the local PC; Phase B: off the VPS).
- **Restore test** is part of the B→C readiness gate: prove a backup restores into a runnable state.

---

## 8. Safe restart that does not double-trade (the crown jewel — R7, spec 03 §5)

1. **MT5 is the source of truth on startup**: after `initialize`/`login`, query live positions + pendings, reconcile against persisted state + intents **before acting**.
2. **Every order tagged with the bot's `magic` number** → distinguish our positions; never re-open one that already exists.
3. **Persist intent before acting, idempotently** (`client_id`/`comment`): on crash mid-order, reconciliation compares persisted intents vs MT5 — position exists ⇒ mark filled (don't resend); intent written but no position/deal ⇒ never landed ⇒ resolve per fail-safe.
4. **On any ambiguity → hold/flatten, never guess**, and alert.
Deploys go through this **same path**, so a deploy mid-position is as safe as a crash recovery.

---

## 9. Local-dev vs prod parity (R7)

- **Pin the toolchain**: same Python version, fully pinned lockfile; pin the **`MetaTrader5` wheel version** *and* the **MT5 terminal build** (behaviour shifts between builds).
- **Config via env, not code**: login, paths, magic number, healthchecks/Telegram ids, request-budget cap — all from env/`.env`, so the same artifact runs in dev and prod with different config.
- **Containerize the non-MT5 parts**: the engine logic, backtester, and the whole AI loop run in Docker on Linux for reproducible dev/CI; only the thin **MT5-IPC execution adapter** is pinned to Windows.
- **Deployment**: start with `git pull` + service restart, gated behind the safe-restart reconciliation; graduate to CI (build/test/backtest on push, deploy on tag) once stable.

---

## 10. Ops runbook (outline, R7)

**Cold boot / new box:**
1. Auto-logon to console session; verify RDP on the locked-down IP/port (VPS).
2. Launch MT5; confirm logged in to the FTMO account on the **London** server (and **not** from a US IP).
3. Start the engine service (NSSM/WinSW) → it runs **startup reconciliation** (§8).
4. Confirm first healthchecks ping + Telegram "engine up, MT5 connected, data fresh".

**Daily checks:** heartbeat green, no missed overnight pings; tick/bar freshness OK; request count well under 2,000; P&L vs daily-loss limit; positions match MT5 = journal; last nightly backup present (on-box + off-box); no unacknowledged alerts.

**Crash recovery:** engine crash → service auto-restarts → reconciliation → verify no duplicate positions. MT5 disconnect → watchdog re-inits with backoff; if unrecoverable, fail-safe flatten/hold + alert. Whole-box outage → healthchecks fires → reprovision/reboot → cold-boot → reconcile vs MT5 before resuming. Stale data → engine refuses new trades, holds/flattens, alerts.

**Deploy / update:** merge to main → CI builds + runs tests/backtests on the pinned stack → on box `git pull` (confirm pinned Python/`MetaTrader5`/MT5 build) → restart engine service → reconciliation runs → confirm heartbeat + Telegram "up" before walking away.

**Kill-switch / flatten:** trigger = approaching daily-loss limit, request-budget near exhaustion, persistent disconnect, stale data, or manual (a Telegram command or a sentinel file the engine polls). Action = cancel pendings, **flatten all engine-owned positions** (by magic) via market closes, set engine to halted/no-new-trades, persist the halt reason, alert. **Stays halted until a human clears it — never auto-resumes after a risk-driven kill** (mirrors spec 02 FLATTEN).

---

## 11. Configuration schema

```yaml
ops:
  host_phase: A                    # A=local | B=vps | C=vps+linux-ai-box
  service:
    supervisor: nssm               # nssm | winsw
    engine_entry: src/engine/run.py
    auto_restart: true
  watchdog:
    poll_seconds: 5
    tick_freshness_seconds: 90
    ipc_backoff_base_seconds: 2
    ipc_backoff_max_seconds: 60
  alerts:
    telegram_bot_token: ${TELEGRAM_BOT_TOKEN}   # secret
    telegram_chat_id: ${TELEGRAM_CHAT_ID}
    healthchecks_url: ${HEALTHCHECKS_URL}       # secret
    daily_loss_warn_pct: 0.40
    request_budget_warn: 1600
  backups:
    on_box_dir: state/backups
    off_box_target: ${BACKUP_OFFBOX_URI}        # cloud/AI-box
    interval_minutes: 60
  network:
    rdp_allowed_ip: ${RDP_ALLOWED_IP}           # VPS
    no_us_geolocation: true                     # FTMO hard rule — enforced operationally
```

---

## 12. Test / validation plan

- **Watchdog**: simulate MT5 disconnect (mock returns None) → asserts re-init with backoff; simulate stale ticks → asserts fail-safe trigger, no new trade.
- **Service**: kill the engine process → NSSM/WinSW restarts it → startup reconciliation runs → heartbeat returns (milestone A2/A5).
- **Heartbeat**: stop pinging → healthchecks alert fires within the grace window (manual/integration check).
- **Backup/restore**: scripted backup then restore into a scratch dir → engine boots and reconciles from the restored state (B→C gate).
- **Deploy drill**: deploy mid-(demo)-position → reconcile leaves the position intact and correctly accounted.
- **Parity check**: the same artifact + a VPS `.env` reproduces local behaviour on the parallel-run demo before cut-over.
- **Geolocation guard**: operational checklist item + a startup log of the outbound IP region (alert if US) — defence against the FTMO VPN rule.
