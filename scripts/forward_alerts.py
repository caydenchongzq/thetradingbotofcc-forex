"""Forward VPS alert files to Telegram from the LOCAL machine (spec 07 §5).

When the VPS network blocks Telegram (TLS interception / firewall), the engine still
writes every alert to state/alerts/<date>.jsonl, which rides the R2 sync. This script —
run on your local PC where Telegram works — reads the synced alert files and forwards any
new ones, tracking a marker so each alert is sent once.

Usage (local):
    py scripts/forward_alerts.py --src C:\\ftmo-sync
Pair it in a scheduled task that first runs:
    py scripts/sync_r2.py pull --prefix vps --dest C:\\ftmo-sync
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.config import load_config           # noqa: E402
from src.ops.alerts import send_telegram             # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Forward synced VPS alerts to Telegram")
    ap.add_argument("--src", default="C:/ftmo-sync", help="folder the VPS state was pulled into")
    args = ap.parse_args(argv)

    cfg = load_config()
    a = cfg.alerts
    if not a.telegram_configured:
        print("Telegram not configured locally (TBOT_TELEGRAM_* in .env) — cannot forward.")
        return 1

    src = Path(args.src)
    alerts_dir = src / "alerts"
    if not alerts_dir.exists():
        print(f"no alerts dir at {alerts_dir} (nothing synced yet) — nothing to forward.")
        return 0

    marker = src / ".alerts_forwarded"
    last = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""

    records = []
    for f in sorted(alerts_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    records.sort(key=lambda r: r.get("ts_utc", ""))
    new = [r for r in records if r.get("ts_utc", "") > last]

    sent = 0
    for r in new:
        text = (f"[{r.get('severity')}] {r.get('env')}/{r.get('symbol')}: "
                f"{r.get('event')}" + (f" — {r.get('detail')}" if r.get('detail') else ""))
        if send_telegram(a.telegram_bot_token, a.telegram_chat_id, text):
            sent += 1
    if new:
        marker.write_text(new[-1]["ts_utc"], encoding="utf-8")
    print(f"forwarded {sent}/{len(new)} new alert(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
