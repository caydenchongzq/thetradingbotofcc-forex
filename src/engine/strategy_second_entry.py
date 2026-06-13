"""SecondEntryORB — research-engine candidate (spec 08, 2026-06-13).

Hypothesis: the incumbent ``SessionBreakoutER`` is *one-shot per side per day* — it enters on
the FIRST bar that closes beyond the London/NY-overlap opening-range level and never re-enters
that side. Practitioner ORB literature (and the "turtle soup +1" / second-attempt tradition)
holds that a first breakout which fails and is *retaken* — price closes back inside the range,
then breaks the SAME level again — is itself a tradeable continuation: the first attempt flushed
weak hands and stops, and the second break runs on cleaner footing. This candidate keeps the
incumbent's first-break entry UNCHANGED and ADDS a second (and only a second) re-break entry per
side per day, capped by ``second_entry.max_entries_per_side``.

Why this is the inverse of the rejected break-retest variant ([[2026-06-11-breakout-retest]]):
that candidate REPLACED the immediate close-entry with a retest-only entry — subtractive, it
discarded the incumbent's 73%-win immediate-continuation winners AND halved the trade count below
the 200 floor (double-jeopardy). SecondEntryORB is strictly ADDITIVE: it never removes an
incumbent trade; it can only add re-break trades on top, raising the trade count. The open
question the arbiter settles is whether those added re-break trades carry their weight or merely
dilute the incumbent's expectancy.

Exit geometry (spec 08 §5.8 — pre-registered, and here *deliberately identical* to the incumbent,
with the required justification, NOT an unexamined inheritance):
  * A re-break of the opening-range level is the SAME momentum-continuation mechanism as the
    incumbent's first break — same level, same direction, same session/regime. The whole library
    record (the ≥2R sweep [[2026-06-07-tp-2r-sweep]] and the pullback [[2026-06-12-trend-pullback-ema]]
    both reconfirm it) says EURUSD M15 overlap rewards *high-win-rate ~1R breakout* structures and
    punishes low-win-rate high-R ones. Because the second entry shares the incumbent's mechanism,
    reusing its validated ``stop = max(structural, 1.2×ATR)`` / single-1R / break-even ``manage()``
    machinery is the geometry the mechanism *implies* — pre-registered with this rationale, so the
    A/B isolates a single variable (allow the second episode) rather than confounding entry + exit.
  * Because ``manage()`` and the exit plan are byte-for-byte the incumbent's, the candidate
    introduces NO new manage semantic and needs NO live-mirror session: ``live == backtest`` already
    holds for the exit path; only ``evaluate`` differs.

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses ``SessionBreakoutER`` for ALL shared PURE machinery (``_regime``, ``_blackout``,
    ``_signal``, ``manage``, tz, ``_london``, ``_or_end``, ``warmup_bars``). The incumbent class is
    NOT modified; only ``evaluate`` is overridden and it reuses ``self._signal`` verbatim.
  * PURE function of (bars, now, context_bias, calendar): no clock, no network, no state. Every
    degraded path (short history, bad bar sequence, stand-down, outside session, building OR,
    stale data, regime-fail, blackout) -> ``NoSignal``.
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``second_entry:``; chosen a priori, deliberately NOT swept):
    max_entries_per_side: 2   # 1 == incumbent; 2 == first break + one re-break
"""

from __future__ import annotations

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .indicators import second_entry_breakout_trigger
from .strategy import SessionBreakoutER
from .types import Direction, NoSignal


class SecondEntryORB(SessionBreakoutER):
    name = "SecondEntryORB"

    def __init__(self, config: dict):
        super().__init__(config)
        se = (config or {}).get("second_entry", {})
        self.max_entries_per_side = int(se.get("max_entries_per_side", 2))

    # ------------------------------------------------------------------
    def evaluate(self, bars, now_utc, context_bias, calendar=None):
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
        if self._london(last.ts_open_utc).time() < or_end:
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

        # Post-opening-range session bars, time-ordered, INCLUDING the current bar. The trigger
        # reconstructs the episode count (first break + any re-breaks) purely from these closes.
        post = [b for b in sess
                if self._london(b.ts_open_utc).time() >= or_end
                and ensure_utc(b.ts_open_utc) <= ensure_utc(last.ts_open_utc)]
        closes = [b.close for b in post]

        if second_entry_breakout_trigger(closes, long_level, "long", self.max_entries_per_side):
            return self._signal(Direction.LONG, long_level, range_low, regime, now, context_bias)
        if second_entry_breakout_trigger(closes, short_level, "short", self.max_entries_per_side):
            return self._signal(Direction.SHORT, short_level, range_high, regime, now, context_bias)
        return NoSignal(now, "no_range_break")
