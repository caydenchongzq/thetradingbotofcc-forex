"""Alerting + dead-man's-switch (spec 07 §5) — Telegram + healthchecks.io.

The formatter is pure and tested; the senders do a single guarded HTTP POST and never
raise into the trading loop (an alert failure must not crash the engine). Network calls
use urllib (stdlib) so there is no extra dependency on the live box."""

from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
from enum import Enum


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


def format_alert(severity: Severity, event: str, detail: str = "", *,
                 env: str = "dev", symbol: str = "EURUSD") -> str:
    """One-line, scannable alert message. Pure."""
    icon = {Severity.INFO: "ℹ️", Severity.WARN: "⚠️", Severity.CRITICAL: "🚨"}[severity]
    base = f"{icon} [{severity.value}] {env}/{symbol}: {event}"
    return f"{base} — {detail}" if detail else base


def send_telegram(token: str | None, chat_id: str | None, text: str,
                  *, timeout_s: float = 8.0) -> bool:
    """Best-effort Telegram POST. Returns True on apparent success; never raises."""
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        with urllib.request.urlopen(url, data=data, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def send_discord(webhook_url: str | None, text: str, *, timeout_s: float = 8.0) -> bool:
    """Best-effort Discord webhook POST. Often reachable where Telegram is blocked.
    Returns True on apparent success; never raises."""
    if not webhook_url:
        return False
    try:
        data = json.dumps({"content": text}).encode()
        req = urllib.request.Request(webhook_url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def ping_healthcheck(url: str | None, *, fail: bool = False, timeout_s: float = 8.0) -> bool:
    """Ping the healthchecks.io dead-man's-switch. ``fail=True`` posts to the /fail
    endpoint to signal an explicit problem. Silence (no ping) is what fires the alert,
    so this must mean 'alive + connected + fresh'. Never raises."""
    if not url:
        return False
    try:
        target = url.rstrip("/") + "/fail" if fail else url
        with urllib.request.urlopen(target, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def append_alert_file(state_dir, severity, event: str, detail: str = "", *,
                      env: str = "dev", symbol: str = "EURUSD", now=None) -> None:
    """Append an alert to state/alerts/<date>.jsonl — a durable sink that works even when
    every network channel is blocked. It rides the R2 sync so a local box can forward it."""
    d = Path(state_dir) / "alerts"
    d.mkdir(parents=True, exist_ok=True)
    ts = now or datetime.now(tz=timezone.utc)
    rec = {"ts_utc": ts.isoformat().replace("+00:00", "Z"),
           "severity": getattr(severity, "value", str(severity)),
           "event": event, "detail": detail, "env": env, "symbol": symbol}
    with open(d / f"{ts.date().isoformat()}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
