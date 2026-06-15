"""SessionBreakoutERResting — resting-stop OCO variant (RESTING_STOP_FIX option 1).

DEV / RESEARCH strategy, never the promoted incumbent. It exists to (a) keep the resting-stop
OCO infrastructure (``ArmSignal`` -> OCO pair in ``decide`` -> intrabar touch-fill in the
backtester -> OCO lifecycle in ``run.py``) exercised and reusable by any FUTURE strategy whose
edge genuinely lives in a TOUCH fill, and (b) document, on the record, why this mechanism is
WRONG for ``SessionBreakoutER``: its edge is CLOSE-confirmation, and filling on every intrabar
touch admits the false breakouts that snap back inside the range. Arbiter verdict 2026-06-15:
in-sample expectancy -0.267R, all gates fail. See docs/RESTING_STOP_FIX.md §4.

It subclasses ``SessionBreakoutER`` for ALL shared machinery (regime, blackout, sessionising,
``_signal``, ``manage``) and only replaces ``evaluate``: at opening-range end it ARMS a
two-sided OCO (a stop ``Signal`` per side that can legally rest), to be filled on an intrabar
touch of its level. The per-side legs are ``entry_type="stop"`` at the level, so their exits
are level-anchored (identical geometry to the pre-option-2 incumbent)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .strategy import SessionBreakoutER
from .types import ArmSignal, Direction, NoSignal


class SessionBreakoutERResting(SessionBreakoutER):
    name = "SessionBreakoutERResting"

    def evaluate(self, bars, now_utc, context_bias, calendar=None):
        """Arm a two-sided resting-stop OCO ONCE per session, on the FINAL opening-range bar
        (so the stops are live for the breakout bar). Regime + news read AT OR-end. Returns
        ``ArmSignal`` on the arming bar, else ``NoSignal`` (the caller holds the armed state)."""
        now = ensure_utc(now_utc)
        if len(bars) < self.warmup_bars():
            return NoSignal(now, "insufficient_history")
        last = bars[-1]
        if not getattr(last, "is_closed", True):
            return NoSignal(now, "bad_bar_sequence")
        if len(bars) >= 2 and ensure_utc(bars[-1].ts_open_utc) <= ensure_utc(bars[-2].ts_open_utc):
            return NoSignal(now, "bad_bar_sequence")
        if context_bias is ContextBias.STAND_DOWN:
            return NoSignal(now, "stand_down")

        lon_now = self._london(now)
        or_end = self._or_end()
        if not (self.win_start <= lon_now.time() < self.win_end):
            return NoSignal(now, "outside_session")

        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        day = lon_now.date()
        sess = [b for b in bars
                if self._london(b.ts_open_utc).date() == day
                and self.win_start <= self._london(b.ts_open_utc).time() < self.win_end]
        or_bars = [b for b in sess if self._london(b.ts_open_utc).time() < or_end]
        if not or_bars:
            return NoSignal(now, "outside_session")

        # Arm EXACTLY on the final opening-range bar: its close coincides with OR-end, so the
        # resting stops are placed now and become fillable from the next (first post-OR) bar.
        last_london = self._london(last.ts_open_utc)
        if last_london.time() >= or_end:
            return NoSignal(now, "not_arm_bar")
        if (last_london + timedelta(minutes=self.tf_min)).time() < or_end:
            return NoSignal(now, "building_opening_range")

        regime = self._regime(bars)
        if not regime.regime_gate_passed:
            return NoSignal(now, "regime_gate_failed")
        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        range_high = max(b.high for b in or_bars)
        range_low = min(b.low for b in or_bars)
        buf = self.buffer_pips * self.pip
        long_level = range_high + buf
        short_level = range_low - buf

        # Gap guard: a buy_stop must rest ABOVE the market and a sell_stop BELOW it; if price
        # at OR-end has already traded through a level, that side cannot rest as a stop -> skip.
        ref = last.close
        long_sig = (self._signal(Direction.LONG, long_level, range_low, regime, now,
                                 context_bias, long_level, "stop")
                    if ref < long_level else None)
        short_sig = (self._signal(Direction.SHORT, short_level, range_high, regime, now,
                                  context_bias, short_level, "stop")
                     if ref > short_level else None)
        if long_sig is None and short_sig is None:
            return NoSignal(now, "both_levels_through")

        return ArmSignal(instrument=self.config.get("instrument", "EURUSD"),
                         ts_decision_utc=now, long=long_sig, short=short_sig,
                         expire_utc=self._win_end_utc(lon_now), regime=regime,
                         config_version=self.config_version)

    def _win_end_utc(self, lon_now: datetime) -> datetime:
        """Today's session window-end as a UTC instant (the OCO expiry)."""
        end_local = datetime(lon_now.year, lon_now.month, lon_now.day,
                             self.win_end.hour, self.win_end.minute, tzinfo=self.tz)
        return ensure_utc(end_local)
