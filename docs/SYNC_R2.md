# Journal sync via Cloudflare R2

The VPS runs the engine and writes the trade journal. Your **local** Claude scheduler tasks
(Reviewer/Researcher/Analyst) need to read that journal. R2 is the bus: VPS **pushes**, local
**pulls**. R2 is S3-compatible, has **no egress fees**, and a free tier that easily covers this.

```
 VPS engine  --push-->  Cloudflare R2 (bucket)  --pull-->  Local PC
 writes state/journal + live.sqlite             Reviewer/backtests read it
```

`boto3` (pure Python) does the transfer — fine on the constrained VPS CPU. Credentials live in
`.env` only, never in git.

---

## 1. One-time Cloudflare setup
1. Cloudflare dashboard → **R2** → **Create bucket** (e.g. `ftmo-bot-state`). Region: Automatic.
2. R2 → **Manage R2 API Tokens** → **Create API token**:
   - Permissions: **Object Read & Write**, scoped to that one bucket.
   - Create it; copy the **Access Key ID** and **Secret Access Key** (shown once).
3. Note your **Account ID** (R2 overview page, or the S3 endpoint
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`).

## 2. `.env` on BOTH machines
Add these (same values on VPS and local). Use the **S3 endpoint** Cloudflare shows for your
bucket (it already contains your account id):
```
TBOT_R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
TBOT_R2_ACCESS_KEY_ID=<access key id>
TBOT_R2_SECRET_ACCESS_KEY=<secret access key>
TBOT_R2_BUCKET=ftmo-bot-state
```
Cloudflare's R2 token screen gives you an **Access Key ID**, a **Secret Access Key**, and an
**S3 endpoint** (the "S3 client" URL). Map those three + the bucket name as above. The separate
**Token value** (Cloudflare API Bearer token) is NOT used by the S3 path — ignore it.
Install boto3 on both:  VPS → it's in `requirements-live.txt`;  local → `pip install boto3` (or `-r requirements-loop.txt`).

## 3. VPS — push on a schedule
The engine writes `state/journal/` + `state/live.sqlite` as it trades. Push them to R2 every
~15 minutes with **Windows Task Scheduler** (the WinSW service runs the engine; this is a
separate small job):

- Program/script: `py`
- Arguments: `-3.12 scripts\sync_r2.py push --paths journal live.sqlite config --prefix vps`
- Start in: `C:\Users\Administrator\Documents\thetradingbotofcc-forex`
- Trigger: every 15 minutes.

Test it once by hand first:
```
py -3.12 scripts\sync_r2.py push --paths journal live.sqlite config --prefix vps
```
You should see `pushed N files to r2://ftmo-bot-state/vps/`.

## 4. Local — pull, then review
Pull the VPS state into a local sync folder, then point the Reviewer/backtests at it:
```
py scripts\sync_r2.py pull --prefix vps --dest C:\ftmo-sync
py scripts\review_journal.py --state C:\ftmo-sync
py scripts\run_backtest.py --state C:\ftmo-sync --walkforward    # optional: analyse live trades
```
`--state` makes those scripts read `C:\ftmo-sync\live.sqlite` + `C:\ftmo-sync\journal\` instead
of the local `state\`.

The local **`ftmo-reviewer` scheduled task** is updated to do the pull automatically before
reviewing, so once the engine is trading you get daily summaries with no manual step.

## 5. Config promotions (local → VPS), optional via R2
When you `--approve` a config locally it lands in `state\config\`. To ship it to the VPS:
```
# local: push the config store up
py scripts\sync_r2.py push --paths config --prefix promote
# VPS: pull it into the engine's state, then restart so it adopts at the next session
py -3.12 scripts\sync_r2.py pull --prefix promote --dest state
.\scripts\service\ftmo-bot.exe restart
```
Promotions are rare during a forward test — do this deliberately, not on a timer.

## 6. Safety notes
- The VPS is the **only writer** of `live.sqlite`; local only reads its pulled copy. No two-writer
  corruption.
- R2 token is **scoped to one bucket, read+write only** — it can't touch the rest of your account.
- Don't commit `.env`. The R2 secret is as sensitive as the MT5 password.
