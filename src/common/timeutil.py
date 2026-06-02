"""Time helpers for the FTMO trading day.

The FTMO daily-loss window resets at 00:00 **Europe/Prague** (CET/CEST), with DST
handled by the tz database — never a fixed +1/+2 offset (spec 02 §2). All internal
timestamps are timezone-aware UTC; conversions to Prague happen only here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")
UTC = timezone.utc


def ensure_utc(dt: datetime) -> datetime:
    """Return a tz-aware UTC datetime; naive input is assumed already UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def ftmo_day_start(now_utc: datetime) -> datetime:
    """UTC instant of the most recent 00:00 Europe/Prague at or before ``now_utc``.

    This is the moment the daily loss budget was (or should have been) reset.
    """
    now_utc = ensure_utc(now_utc)
    local = now_utc.astimezone(PRAGUE)
    midnight_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if midnight_local > local:  # only happens with backward DST folds; guard anyway
        midnight_local -= timedelta(days=1)
    return midnight_local.astimezone(UTC)


def next_ftmo_day_start(now_utc: datetime) -> datetime:
    """UTC instant of the next 00:00 Europe/Prague strictly after ``now_utc``."""
    start = ftmo_day_start(now_utc)
    # Add ~25h in local terms then re-snap, so DST transitions don't land us short.
    local_next = (start.astimezone(PRAGUE) + timedelta(hours=25)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return local_next.astimezone(UTC)


def is_new_ftmo_day(last_reset_utc: datetime | None, now_utc: datetime) -> bool:
    """True if a 00:00 Prague boundary has been crossed since ``last_reset_utc``."""
    if last_reset_utc is None:
        return True
    return ftmo_day_start(now_utc) > ensure_utc(last_reset_utc)


def utc_iso(dt: datetime) -> str:
    """ISO-8601 UTC string with a trailing Z, second precision floor preserved."""
    dt = ensure_utc(dt)
    return dt.isoformat().replace("+00:00", "Z")
