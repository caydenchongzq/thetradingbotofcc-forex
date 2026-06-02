# R7 — Infrastructure / VPS & Ops

*Where and how the FTMO EURUSD bot runs reliably, unattended. Research date: June 2026.*

## Summary

The execution baseline (confirmed in R3) forces the hard constraints here: the first-party `MetaTrader5` Python package is **Windows-only**, is **not headless** (a logged-in MT5 terminal GUI process must stay running, and the Python layer is an IPC client to it), and is prone to IPC-timeout/disconnect — so the production host is effectively a **Windows machine running an always-on MT5 terminal plus a supervised Python engine, with a watchdog that re-initialises the IPC link** ([MetaTrader5 on PyPI](https://pypi.org/project/metatrader5/); [MQL5 Python integration docs](https://www.mql5.com/en/docs/python_metatrader5)).

FTMO's matching engine lives in **London (Equinix LD4 in Slough / LD5 in Hayes)**, while FTMO's *company* is in Prague — that Prague address is corporate HQ, not the trade server, so latency planning should target London, not Prague ([tradingfxvps prop-firm VPS guide](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/); [FTMO contact/imprint, Prague office](https://ftmo.com/en/faq/which-platforms-can-i-use-for-trading/)). Important nuance: there is **no first-party "FTMO free VPS"** bundled with challenge accounts the way some prop firms advertise — the "FTMO VPS" hits in search are third-party resellers (vps-mart, NYCServers, etc.). FTMO's own policy simply **permits** VPN/VPS use, with one hard rule: **do not log a MetaTrader/cTrader account in from a US geolocation, even via VPN** ([FTMO FAQ: Can I travel or use VPN/VPS](https://ftmo.com/en/faq/can-i-travel-or-use-vpn-vps/)).

Because we are **intraday, not latency-arbitrage**, true HFT colocation (<1 ms) is unnecessary. London-region placement (1–20 ms) is sufficient for clean fills; we are nowhere near FTMO's intentionally-applied execution delay of up to ~200 ms, so shaving microseconds buys nothing ([tradingfxvps](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/)).

---

## Host phasing — local PC first, VPS before funded (decided 2026-06-02)

The VPS recommendation below is the **production** target; it is **not** the day-one host. Decided rollout: **run the live engine on Cayden's local Windows PC** through dev, demo, free-trial forward-test, and the FTMO **challenge** phase, then **migrate to the London Windows VPS before the funded account.** This loses nothing in the research and gains cost/iteration speed early:

- **Parity is free here.** The whole reason this track is Windows-bound — the `MetaTrader5` package talks to a GUI terminal over Windows IPC — means the **local Windows PC is a genuine parity environment**, not a stand-in. The same artifact, the same pinned `MetaTrader5` wheel and MT5 build, the same NSSM/watchdog supervision, and the same env-driven config run locally and on the VPS; migration is "provision the box, copy the `.env`, `git pull`, start the service," exercising the same cold-boot runbook below.
- **Risk-matched spend.** A home-PC outage (power, ISP, Windows reboot) during **demo/challenge** costs only a retry — there is no capital at stake and FTMO challenges have **no time limit** (README §4). The same outage on a **funded** account is an uninsurable drawdown/breach risk. So we pay for the 24/5 VPS exactly when uptime starts protecting real money, not before.
- **Local-phase hardening (cheap, do it anyway).** Even on the local PC, treat it like a small server: disable sleep/hibernate and automatic restart-after-update, put it on a UPS if available, confirm the watchdog + healthchecks heartbeat fire, and keep the off-box journal backup (so a disk loss isn't terminal). These are the same controls the VPS gets and they make the eventual cut-over a formality.
- **Improvement-loop isolation is relaxed in this phase.** The "separate Linux box for the AI loop" below assumes the VPS topology. In the local phase the R5 agents run as **Cowork scheduled tasks on the same machine**; to honour the intent of the separation (a heavy job must never starve the live trader) we **schedule agent/backtest runs outside active London/NY-overlap trading sessions**. Full box separation is restored at the VPS stage. (See R5 §2.4 and `docs/specs/00-phase-roadmap.md`.)

**Migration trigger (local → VPS):** before the first funded account goes live — provision in advance, run both in parallel on demo for a few sessions to confirm parity, then cut over. Everything in the rest of this document describes that VPS target.

## Deployment recommendation

**Host choice: a London-region Windows VPS, 4 GB RAM / 2 vCPU minimum (target 4 vCPU / 8 GB), NVMe SSD, 99.9%+ uptime.** A single MT5 terminal consumes ~300–500 MB RAM and the Python engine plus an SQLite journal is light, so 4 GB is the floor and 8 GB gives comfortable headroom for the engine, logging, and OS overhead ([tradingfxvps specs table](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/)). Windows Server 2019/2022 is the reliable platform target.

**Why a forex-specialised London VPS over general cloud:**

- **Cost & licensing simplicity.** Forex VPS providers (ForexVPS.net, TradingFXVPS, Cheap Forex VPS, NYCServers) bundle the Windows licence into a flat **$25–60/month mid-tier** plan (4 GB RAM, 2–4 cores, NVMe, 99.99% uptime) and place you in London LD4 by default ([tradingfxvps pricing tiers](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/)). General cloud is fiddlier and not obviously cheaper once Windows licensing is added: **AWS EC2 t3.medium is ~$30/mo on Linux but Windows adds the bundled Server licence per-vCPU on top** ([t3.medium pricing](https://www.economize.cloud/resources/aws/pricing/ec2/t3.medium/); [EC2 on-demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/)), and **Vultr charges a separate $16/core/month Windows licence** — so a $10 base instance is really ~$26/mo, and a 2-core box ~$32/mo for licence alone ([Vultr: is a Windows licence included](https://docs.vultr.com/support/platform/billing/is-a-windows-license-included-in-the-monthly-price)). Contabo is cheap on RAM/€ but adds a Windows licence fee and does not target London-LD4 proximity ([Contabo pricing](https://contabo.com/en/pricing/)).
- **Proximity for fill quality, not speed.** The specialised providers cross-connect inside LD4, giving 1–5 ms to FTMO's engine; AWS `eu-west-2` (London) or Azure UK South are also physically in/near London and perfectly adequate (5–20 ms region latency), so cloud is a fine fallback if you want IaC/snapshots — the deciding factor is operational simplicity, not microseconds ([forexvps best VPS locations](https://www.forexvps.net/resources/best-vps-location-low-latency-trading/)).
- **RDP management.** All of these expose standard Windows RDP, which is the simplest way to run and visually confirm the non-headless MT5 GUI.

**Concrete pick: a mid-tier London Windows VPS from a forex-specialised provider (~$30–50/mo).** If the project standardises on AWS for everything else, an **EC2 Windows instance in `eu-west-2` (London)** is an acceptable equivalent with better snapshot/automation tooling, accepting the licence premium.

**Do not rely on an "FTMO free VPS."** It is not a first-party FTMO offering tied to the account; budget for a paid VPS. (FTMO's Premium Programme perks are unrelated to hosting.)

**OS decision: commit to Windows for the execution box.** The `MetaTrader5` Python package is Windows-only by design (it talks to the terminal over Windows IPC/DLLs), so Windows is the path of least resistance ([MetaTrader5 PyPI](https://pypi.org/project/metatrader5/)). The **Linux + Wine route exists** — `gmag11/MetaTrader5-Docker` (Wine + VNC, ships a Python env and `mt5linux` bridge) and `mt5linux` are the known projects ([gmag11/MetaTrader5-Docker](https://github.com/gmag11/MetaTrader5-Docker); [mt5linux](https://github.com/lucas-campagna/mt5linux)) — **but it is fragile for unattended 24/5 production.** Documented failure modes include MT5 breaking on specific Wine builds (debugger-detection errors on Wine ≥10.3, requiring pinning to 10.2; wineserver pegging 100% CPU on some 6.x builds; missing win32u functions), and MT5 forcing Wine 10 because Wine 9 is unsupported — a moving compatibility target that adds an emulation layer between platform and broker for no latency or cost win that justifies the risk ([MQL5 Wine debugger thread](https://www.mql5.com/en/forum/438067/page2); [tradingfxvps Windows vs Linux](https://tradingfxvps.com/windows-server-vs-linux-vps-for-forex-trading-2025-performance-benchmark/)). **Verdict: Windows for execution; reserve Wine/Docker only for a disposable local dev convenience, never as prod.**

**Where the AI / improvement loop runs: on a separate Linux box, off the hot path.** R3 already mandates the asynchronous AI improvement loop be decoupled from execution. It has no Windows/MT5 dependency, so run it on a cheap Linux VM (or locally) — cheaper, containerisable, and isolation means a heavy training/backtest job can never starve or crash the live trader. The two communicate only through artefacts: the live box writes the trade journal / state DB; the AI box reads it, proposes parameter changes, and changes are promoted by a human-reviewed config bump, never by live mutation.

---

## Supervision, auto-restart, monitoring & alerting

**Two processes to keep alive on the Windows box:** (1) the MT5 terminal GUI, and (2) the Python engine. Both must survive crashes, reboots, and logout.

**Supervision layer — use a Windows service wrapper, not Task Scheduler.** Task Scheduler is per-user and built for run-and-exit jobs; for an always-on process that must auto-restart on crash and run before login / after logout, install it as a **service via NSSM or WinSW** ([NSSM Python-service guide](https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm/); [windowsforum: NSSM resilient automation](https://windowsforum.com/threads/turn-windows-desktop-into-a-resilient-automation-server-with-nssm.390975/)). NSSM wraps `python.exe yourscript.py`, integrates with the Service Control Manager, and auto-restarts on failure; WinSW is the XML-config, actively-maintained equivalent favoured in CI/enterprise contexts. **Caveat specific to MT5:** the terminal is a **GUI** app and needs an interactive desktop session — running it purely as a headless service is unreliable. The robust pattern is: keep the VPS auto-logged-in to a console session (RDP/auto-logon), launch MT5 into that session, and let a **watchdog** (below) own restarting MT5; supervise only the *Python engine* as the NSSM/WinSW service. (PM2 is a fine supervisor for the Python side on the **Linux AI box**, but is not the natural fit for the Windows GUI terminal.)

**Application-level watchdog (the part R3 explicitly requires).** A small loop — either inside the engine or a sibling process — that every N seconds:
- Calls `mt5.terminal_info()` / `mt5.account_info()`; if `None` or `mt5.last_error()` signals disconnect, it tears down and **re-runs `mt5.initialize()` / `mt5.login()`** to recover the IPC link, with exponential backoff ([MQL5 Python integration](https://www.mql5.com/en/docs/python_metatrader5)).
- Pulls the latest tick/bar for EURUSD and checks **freshness** (e.g. last tick timestamp within tolerance for current session). Stale data ⇒ trigger the R3 fail-safe (**flatten or hold, never guess**), not a new trade.
- If MT5's own process is gone, restarts the terminal executable.

**What to detect and alert on:** process crash (service/watchdog down), MT5 disconnect / failed `initialize`, stale data (no new ticks/bars during an active session), failed/rejected orders (`order_send` retcode ≠ DONE), **approaching the daily-loss limit** (per R4 risk model), and **request-budget exhaustion** (approaching FTMO's ≤2,000 server requests/day — the engine must count its own calls and alarm well before the cap).

**Alerting channels + heartbeat (dead-man's-switch).** Layer two things:
1. **Push alerts via a Telegram bot** for actionable events (order reject, disconnect, daily-loss proximity, fail-safe flatten). A bot token + chat ID and a one-line HTTP POST is the lightest reliable channel; email as a slower backup.
2. **A dead-man's-switch heartbeat via [healthchecks.io](https://healthchecks.io/)**: the engine pings a healthchecks URL on every successful loop iteration; if pings stop arriving on schedule, healthchecks notifies you (it supports Telegram and 25+ channels) ([healthchecks dead-man's-switch monitoring](https://blogs.snehangshu.dev/dead-mans-switch-style-application-monitoring-with-healthchecksio); [healthchecks Telegram integration](https://healthchecks.io/integrations/telegram/)). This is the critical catch-all: it fires even if the whole VPS dies, which in-process Telegram alerts cannot do. Design the ping to mean "engine is alive **and** MT5 is connected **and** data is fresh," so a silent heartbeat unambiguously means "something is wrong, go look."

---

## Secrets, state backups & safe restart

**Secrets (MT5 login/password, Telegram token, healthchecks URL, any API keys).** Do not hard-code or commit them. On a single-VPS deployment the pragmatic baseline is **environment variables / a `.env` file outside the repo with locked-down NTFS ACLs**, loaded at process start. Stronger options if warranted: a **Windows DPAPI-encrypted file** (machine/user-bound, decryptable only on that box) or a hosted secrets manager (AWS Secrets Manager / Azure Key Vault) if already on that cloud. Pair with the security hygiene the VPS guides stress: strong unique passwords, 2FA on the VPS and trading accounts, RDP locked to a known IP / non-default port, and a dedicated IP ([tradingfxvps security checklist](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/)).

**State / journal backups.** Persist the trade journal and engine state in an **embedded SQLite DB** (single-node, ideal here) and snapshot it on a schedule — a timestamped copy to a second disk/volume plus an **off-box/offsite copy** (object storage or the AI box) so a VPS loss isn't a total loss ([reconciliation/persistence pattern](https://dev.to/vital7777/automated-trading-with-metatrader5-order-management-and-market-data-collection-4pb8)). Daily backups of the trading setup and offsite storage are standard practice ([tradingfxvps data-protection checklist](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/)).

**Safe restart that does not double-trade.** This is the most important correctness property. Pattern:
1. **MT5 is the source of truth on startup.** After `initialize`/`login`, query live open positions and pending orders via the API and **reconcile against the persisted state** before acting ([reconcile-on-restart pattern](https://dev.to/vital7777/automated-trading-with-metatrader5-order-management-and-market-data-collection-4pb8)).
2. **Tag every order with the bot's `magic` number** so the engine can distinguish its own positions from anything else and never re-open a position that already exists in the terminal ([MQL5 order_send / magic](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)).
3. **Persist intent before acting, idempotently.** Before sending an order, write a record with a unique client-side ID / `comment` and an "intended" status; on `order_send` success flip it to "filled." On a crash mid-order, startup reconciliation compares persisted intents against MT5's actual positions/deals: if the position exists, mark filled (don't resend); if intent was written but no position and no matching recent deal exists, the order never landed — decide per the fail-safe rather than blindly retrying.
4. **On any ambiguity, hold/flatten — never guess** (R3 fail-safe), and alert.

---

## Local-dev vs VPS-prod parity

Keep dev and prod from drifting:
- **Pin the toolchain.** Same **Python version** and a fully pinned lockfile (e.g. `requirements.txt` / `uv.lock` / Poetry lock); the `MetaTrader5` wheel is Windows-only and version-sensitive, so pin its version and the **MT5 terminal build** too, since behaviour and Wine-compat shift between builds ([MetaTrader5 PyPI](https://pypi.org/project/metatrader5/)).
- **Config via env, not code.** All host-specific values (login, paths, magic number, healthchecks/Telegram IDs, request-budget cap) come from env/`.env`, so the same artifact runs in dev and prod with different config.
- **Containerise the non-MT5 parts.** The Python engine logic, backtester, and the whole AI loop can live in Docker on Linux for reproducible dev/CI; only the thin MT5-IPC execution adapter is pinned to the Windows box. This keeps "build once, run anywhere" for everything except the unavoidable Windows surface.
- **Deployment approach.** Start simple and reliable: **git pull + service restart** on the VPS (`git pull`, then `nssm restart <engine-service>` or WinSW restart), gated behind the safe-restart reconciliation above. Graduate to CI (build/test on push, deploy on tag) once the pipeline is stable. Crucially, **deploys go through the same reconcile-on-startup path**, so a deploy mid-position is as safe as a crash recovery.

---

## Ops runbook (outline)

**Startup (cold boot / new VPS):**
1. VPS auto-logon to console session; verify RDP reachable on the locked-down IP/port.
2. Launch MT5 terminal; confirm logged in to the FTMO account and connected to the London server.
3. Start the Python engine service (NSSM/WinSW). Engine runs **startup reconciliation**: `initialize`/`login`, pull live positions/pending orders, reconcile against SQLite + persisted intents by magic number, resolve any mid-order ambiguity (hold/flatten on doubt).
4. Confirm first healthchecks ping lands and a Telegram "engine up, MT5 connected, data fresh" message arrives.

**Daily checks:**
- Heartbeat green on healthchecks; no missed pings overnight.
- Tick/bar freshness OK; request count comfortably under the 2,000/day cap.
- Day's P&L vs daily-loss limit (R4); positions match MT5 = journal.
- Last nightly backup of the SQLite journal succeeded (on-box + offsite copy present).
- No unacknowledged Telegram alerts.

**Crash recovery:**
- *Engine crash:* NSSM/WinSW auto-restarts ⇒ startup reconciliation runs ⇒ verify no duplicate positions, heartbeat returns.
- *MT5 disconnect / IPC timeout:* watchdog re-runs `initialize`/`login` with backoff; if it can't recover, it flattens-or-holds per fail-safe and alerts.
- *Whole-VPS outage:* healthchecks dead-man's-switch fires; provision/reboot the box, run cold-boot startup, reconcile against MT5 (source of truth) before resuming.
- *Stale data:* engine refuses new trades, holds/flattens per R3, alerts.

**Deploy / update:**
1. Merge to main; CI builds and runs tests/backtests on the pinned stack.
2. On the VPS: `git pull` (or pull the tagged artifact); confirm pinned Python/`MetaTrader5`/MT5 build unchanged or intentionally bumped.
3. Restart the engine service; startup reconciliation runs automatically.
4. Confirm heartbeat + Telegram "up" before walking away.

**Kill-switch / flatten procedure:**
- **Trigger:** approaching daily-loss limit, request-budget near exhaustion, persistent disconnect, stale data, or manual command (a Telegram command or a sentinel file the engine polls).
- **Action:** cancel all pending orders, **flatten all open positions** the engine owns (by magic number) via `order_send` market closes, set engine to a halted/no-new-trades state, persist the halt reason, and alert. Engine stays halted until a human clears it — never auto-resumes after a risk-driven kill.

---

## Sources

- [MetaTrader5 — PyPI (Windows-only wheels)](https://pypi.org/project/metatrader5/)
- [MQL5 Docs — Python Integration](https://www.mql5.com/en/docs/python_metatrader5)
- [MQL5 Docs — order_send (magic number, retcodes)](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)
- [Prop Firm VPS Requirements 2025: Pass FTMO & Funded Challenges — TradingFXVPS](https://tradingfxvps.com/prop-firm-vps-requirements-2025-pass-ftmo-funded-challenges/)
- [Windows Server vs Linux VPS for Forex Trading — TradingFXVPS](https://tradingfxvps.com/windows-server-vs-linux-vps-for-forex-trading-2025-performance-benchmark/)
- [Best VPS Locations for Low-Latency Trading — ForexVPS.net](https://www.forexvps.net/resources/best-vps-location-low-latency-trading/)
- [FTMO FAQ — Can I travel or use VPN/VPS?](https://ftmo.com/en/faq/can-i-travel-or-use-vpn-vps/)
- [FTMO FAQ — Which platforms can I use (MT4/MT5/cTrader); Prague HQ in footer](https://ftmo.com/en/faq/which-platforms-can-i-use-for-trading/)
- [gmag11/MetaTrader5-Docker (Wine + VNC + Python)](https://github.com/gmag11/MetaTrader5-Docker)
- [mt5linux (Wine bridge for MetaTrader5 Python)](https://github.com/lucas-campagna/mt5linux)
- [MQL5 forum — MT5 under Wine debugger-detection issues](https://www.mql5.com/en/forum/438067/page2)
- [How to Run a Python Script as a Windows Service using NSSM — MSSQLTips](https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm/)
- [Turn a Windows Desktop into a Resilient Automation Server with NSSM — Windows Forum](https://windowsforum.com/threads/turn-windows-desktop-into-a-resilient-automation-server-with-nssm.390975/)
- [servy — Windows service wrapper, NSSM/WinSW alternative](https://github.com/aelassas/servy)
- [Healthchecks.io — Dead-man's-switch / heartbeat monitoring](https://healthchecks.io/docs/)
- [Dead Man's Switch-style monitoring with Healthchecks.io](https://blogs.snehangshu.dev/dead-mans-switch-style-application-monitoring-with-healthchecksio)
- [Healthchecks.io — Telegram integration](https://healthchecks.io/integrations/telegram/)
- [Automated Trading with MetaTrader5: Order Management & Reconciliation — dev.to](https://dev.to/vital7777/automated-trading-with-metatrader5-order-management-and-market-data-collection-4pb8)
- [AWS EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [EC2 t3.medium pricing (~$30.37/mo Linux base)](https://www.economize.cloud/resources/aws/pricing/ec2/t3.medium/)
- [Vultr — Is a Windows licence included? ($16/core/mo)](https://docs.vultr.com/support/platform/billing/is-a-windows-license-included-in-the-monthly-price)
- [Contabo — Cloud/VPS pricing](https://contabo.com/en/pricing/)
