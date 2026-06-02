# Running the engine as a Windows service (spec 07 §2)

Supervise the **engine** as a service; let the **watchdog** own the MT5 terminal.

## Option A — WinSW (self-contained, recommended for the local box)
1. Download `WinSW.exe`, rename it `ftmo-bot.exe`, place it beside `ftmo-bot.xml`.
2. `ftmo-bot.exe install` then `ftmo-bot.exe start`.
3. Logs land next to the exe; the service auto-restarts on failure (`onfailure`).

## Option B — NSSM
1. `nssm install ftmo-bot "C:\path\to\py.exe" "-m src.engine.run"`
2. Set **AppDirectory** to the repo root, **AppEnvironmentExtra** for `TBOT_*`.
3. `nssm set ftmo-bot AppExit Default Restart` ; `nssm start ftmo-bot`.

## Critical host setup (do on the local PC too — makes the VPS cut-over a formality)
- Auto-logon to a **console** session; launch the **MT5 terminal** into it and log in to
  the FTMO **London** server. **Never log in from a US IP, even via VPN** (FTMO hard rule).
- Disable sleep/hibernate and auto-restart-after-update; UPS if available.
- Enable **Algo Trading** in the terminal (toolbar + Tools>Options>Expert Advisors).
- Keep secrets in a `.env` outside source control with locked-down NTFS ACLs.
- Confirm the first healthchecks ping + Telegram "engine up" before walking away.
