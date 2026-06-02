"""Alert formatting + guarded senders (spec 07 §5)."""

from src.ops.alerts import Severity, format_alert, ping_healthcheck, send_telegram


def test_format_alert_is_scannable():
    msg = format_alert(Severity.CRITICAL, "fail-safe flatten", "stale data 200s",
                       env="challenge", symbol="EURUSD")
    assert "CRITICAL" in msg and "challenge/EURUSD" in msg
    assert "fail-safe flatten" in msg and "stale data 200s" in msg


def test_format_alert_without_detail():
    msg = format_alert(Severity.INFO, "engine up", env="demo")
    assert msg.endswith("engine up")


def test_senders_are_guarded_when_unconfigured():
    # No token / no url -> returns False, never raises (must not crash the loop).
    assert send_telegram(None, None, "x") is False
    assert send_telegram("", "", "x") is False
    assert ping_healthcheck(None) is False
