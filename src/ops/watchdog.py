"""Watchdog backoff + freshness logic (spec 07 §3/§12) — pure, testable.

The watchdog re-initialises MT5 with exponential backoff on disconnect and triggers the
fail-safe (hold/flatten, never a new trade) on stale data."""

from __future__ import annotations


def backoff_delay(attempt: int, base_s: float = 2.0, max_s: float = 60.0) -> float:
    """Exponential backoff, capped. attempt 0 -> base, doubling each retry."""
    if attempt < 0:
        attempt = 0
    return min(base_s * (2 ** attempt), max_s)


def backoff_schedule(n: int, base_s: float = 2.0, max_s: float = 60.0) -> list[float]:
    return [backoff_delay(i, base_s, max_s) for i in range(n)]


def data_is_fresh(last_tick_epoch: float | None, now_epoch: float,
                  tolerance_s: float, *, last_advance_epoch: float | None = None) -> bool:
    """Fresh if the most recent tick advanced within tolerance. Uses the wall-time since
    the last *advance* (robust to broker server-tz offset, mirrors the adapter)."""
    if last_tick_epoch is None:
        return False
    ref = last_advance_epoch if last_advance_epoch is not None else last_tick_epoch
    # When we only have the raw tick time and the broker clock is offset, a tick in the
    # 'future' (negative age) is treated as fresh; only a stale (old) tick fails.
    age = now_epoch - ref
    return age <= tolerance_s
