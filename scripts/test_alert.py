"""Verify Telegram + healthchecks wiring (spec 07 §5). Run after filling .env.

    py scripts/test_alert.py
Reads the secrets via the config loader (which loads .env), sends a test Telegram
message, and pings the healthchecks URL if set."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.config import load_config        # noqa: E402
from src.ops.alerts import (Severity, format_alert, ping_healthcheck,  # noqa: E402
                            send_discord, send_telegram)


def main() -> int:
    cfg = load_config()
    a = cfg.alerts
    msg = format_alert(Severity.INFO, "test alert",
                       "if you can read this, Telegram is wired", env=cfg.env)
    if not a.telegram_configured:
        print("Telegram NOT configured — add TBOT_TELEGRAM_BOT_TOKEN and "
              "TBOT_TELEGRAM_CHAT_ID to your .env (in the project root).")
    else:
        ok = send_telegram(a.telegram_bot_token, a.telegram_chat_id, msg)
        print("Telegram:", "sent OK (check your phone)" if ok
              else "FAILED — check the token / chat id are correct")

    if a.discord_webhook:
        ok = send_discord(a.discord_webhook, msg)
        print("Discord:", "sent OK (check the channel)" if ok else "FAILED — check the webhook URL")
    else:
        print("Discord NOT configured (TBOT_DISCORD_WEBHOOK) — optional.")

    if a.healthchecks_url:
        print("Healthchecks ping:", "OK" if ping_healthcheck(a.healthchecks_url)
              else "FAILED — check the URL")
    else:
        print("Healthchecks NOT configured (TBOT_HEALTHCHECKS_URL) — optional but recommended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
