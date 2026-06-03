# Deploying for forward testing — local PC + VPS split

The improvement loop (Reviewer/Researcher/Analyst) runs as **Cowork scheduled tasks**, which
only run where the Claude desktop app runs — **your local PC**. So the split is fixed:

| Host | Role | Why |
|---|---|---|
| **VPS** (Windows, London/EU region) | **Live engine only** — `py -m src.engine.run` as a service | Light: one symbol, 15m bars, 5s poll. Fits 5 GB / 4 vCPU + the MT5 terminal. |
| **Local PC** | Improvement loop (scheduler) + **backtests** | Backtests (60k bars × walk-forward) are heavy — never run them on the 5 GB VPS. |

**Hard requirements for the VPS** (or FTMO won't work):
1. **Windows** — the `MetaTrader5` Python package is Windows-only.
2. **London / EU region** — FTMO bans login from a **US IP, even via VPN**. A US VPS is disqualifying.
3. MT5 terminal installed, logged into the FTMO server, **Algo Trading enabled**.

---

## 1. VPS setup (one time)
1. Install Python 3.10+ and the FTMO **MT5 terminal**; log in to the London server.
2. `git clone` this repo somewhere (code is < 5 MB).
3. `py -m pip install -e ".[live]"` (pulls `MetaTrader5`, pandas, pyarrow, PyYAML).
4. Create `.env` with the trial creds, `TBOT_ENV=trial`, `TBOT_ACCOUNT_INITIAL=<trial balance>`,
   Telegram, and **`TBOT_BACKUP_OFFBOX_URI`** pointing at a cloud-synced folder (see §3).
5. `py scripts\mt5_probe.py` → confirm account + EURUSD specs.
6. `py -m src.engine.run --diagnose` → confirm session/regime read.
7. Install the service (run shell **as Administrator**, `WinSW.exe` renamed `ftmo-bot.exe`):
   ```
   cd scripts\service
   .\ftmo-bot.exe install
   .\ftmo-bot.exe start
   .\ftmo-bot.exe status
   ```

## 2. Local PC (unchanged)
- Keep running the Claude scheduler tasks (`ftmo-reviewer` / `analyst` / `researcher`) and any
  backtests. These read the journal the VPS produces (synced per §3) and the local config store.

## 3. State sync
**Journal: VPS → local (one-way).** On the VPS, schedule `py scripts\backup_state.py` hourly with
`TBOT_BACKUP_OFFBOX_URI` set to a folder synced by OneDrive/Dropbox (or `rclone` to S3/B2). It copies
`live.sqlite` + the day's JSONL into timestamped snapshots. On the local PC, point the Reviewer/
backtests at the newest synced snapshot:
```
py scripts\review_journal.py --state "C:\path\to\synced\backups\<latest-timestamp>"
```
(The journal is the read side for the loop; live.sqlite stays single-writer on the VPS, so this is safe.)

**Config promotions: local → VPS (manual, infrequent).** When you `--approve` a config locally,
ship the new version to the VPS and restart so it adopts at the next session boundary:
```
# local: after process_proposal ... --approve  (writes state\config\versions\vN.json + HEAD)
#   commit/push or copy state\config\ to the VPS, then on the VPS:
.\ftmo-bot.exe restart
```
Promotions are rare during a forward test — keep this manual; automate only in Phase C.

## 4. What NOT to do
- Don't run `run_backtest.py` on the 5 GB VPS (too heavy).
- Don't share `live.sqlite` as a read-write file across both machines (SQLite over cloud sync
  corrupts) — the VPS is the only writer; the local side reads snapshots.
- Don't log the FTMO account in from a US IP, ever.

## 5. Daily check (forward test)
- VPS: `state\logs\engine.log` shows heartbeats + per-bar decisions; Telegram fires on entries/alerts.
- Local: the `ftmo-reviewer` task posts a daily summary once trades exist; watch for drift flags.
- Confirm positions in MT5 == the journal; request count well under 2,000/day.
