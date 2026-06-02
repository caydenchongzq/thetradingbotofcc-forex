"""Session-boundary config-reload trigger (spec 06 §6 / 07)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.engine.run import session_date

LON = ZoneInfo("Europe/London")


def test_session_date_uses_local_calendar_day():
    # 23:30 UTC in summer is already the next day in London (UTC+1) -> boundary crossed.
    d1 = session_date(datetime(2026, 6, 2, 23, 30, tzinfo=timezone.utc), LON)
    d2 = session_date(datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc), LON)
    assert d1 != d2          # a new London day -> triggers a config reload at boundary
    assert d2 == datetime(2026, 6, 2).date()
