"""BreakoutRetestER — research-engine candidate (spec 08, 2026-06-11).

Hypothesis: the incumbent SessionBreakoutER enters on the bar that CLOSES beyond the
opening-range level. A large share of intraday FX breakouts immediately pull back ("retest")
to the broken level before continuing, and a meaningful share are *false* breakouts that
never reclaim the level. Entering only AFTER price has broken, returned to the level, and
then RESUMED in the breakout direction acts as a false-breakout filter: it should raise the
per-trade quality (win rate / expectancy) of the same London/NY-overlap ORB, at the cost of
skipping breakouts that run away without retesting (a trade-count risk the arbiter judges).

Mechanism (who is on the other side): a breakout sweeps stops beyond the range; price often
revisits the level as the initiating flow is met by fading liquidity. If the level holds as
new support/resistance on the revisit, the breakout was genuine and trend-followers re-load;
if price closes back inside, it was a false break and no trade is taken. This is the classic
"break and retest" structure documented for EURUSD around high-liquidity sessions.

Relation to prior library work (spec 08 §4.3):
  * Builds on the incumbent breakout family ([[2026-06-02-session-breakout-er]]); same regime
    gate (ER + ATR-normal), same session/opening-range. ONLY the entry trigger + exit
    geometry differ. It trades WITH the breakout — it is NOT a fade, so the closed
    Asian sweep-fade family ([[2026-06-08-asian-sweep-fade]], [[2026-06-10-asian-sweep-fade-rr]])
    failure mode (structurally negative mean-reversion) does not apply.
  * It is NOT the rejected ≥2R exit sweep ([[2026-06-07-tp-2r-sweep]]): that kept the
    incumbent's close-entry and only stretched the TARGET on a wide 1.2×ATR stop. Here the
    ENTRY changes (post-retest) and the STOP is tighter (1.0×ATR), so the 1.5R target is a
    smaller ABSOLUTE move than the rejected ≥2R-on-1.2×ATR geometry — the R-multiples are not
    comparable and the recorded ≥2R failure mode is not inherited.
  * It is NOT a subtractive filter on the incumbent's trades (the gate-blocked compression
    family, [[2026-06-07-pre-session-compression-filter]]): it is a different entry MECHANISM,
    not a veto layered on the incumbent's signals — though its trade count is its own and may
    fall short of the 200-trade floor (reported, not assumed).

Exit geometry (spec 08 §5.8 — chosen per mechanism, NOT inherited from the incumbent):
  * stop = 1.0×ATR (``atr_mult_sl``): a retest that holds defines the line in the sand; if
    price travels ~1 ATR against a confirmed retest entry the thesis is void, so a tighter
    stop than the incumbent's 1.2×ATR is justified (and improves R per pip of follow-through).
  * target = 1.5R (``target_r``; R:R = 1:1.5): breakouts have a sub-50% win rate, so reward
    must exceed risk; 1.5R sits above the 1:1 floor and BELOW the rejected ≥2R territory, and
    on the tighter 1.0×ATR stop it is a modest, reachable follow-through, not a home-run TP.
  * Single target, no partials, NO break-even move (``move_be_after_r = None``) -> the exit is
    a pure broker stop / take-profit. This deliberately introduces NO new ``manage()``
    semantic vs the incumbent, so the candidate needs NO live-mirror session (cf. the
    time-boxed [[2026-06-09-late-session-drift]]): live == backtest already holds.

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses SessionBreakoutER for shared PURE machinery (_regime, _blackout, tz, _london,
    _or_end, warmup, manage). The incumbent class is NOT modified; ``evaluate`` is replaced.
  * PURE function of (bars, now, context_bias, calendar): no clock, no network, no state.
    Every degraded path (short history, bad bar sequence, stand-down, outside session,
    building OR, stale data, regime-fail, blackout, degenerate stop) -> ``NoSignal``.
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``retest:``; defaults chosen a priori, deliberately NOT swept):
    atr_mult_sl: 1.0     # protective stop as an ATR multiple (tighter than incumbent 1.2)
    target_r: 1.5        # single take-profit R-multiple (R:R = 1:1.5)
"""

from __future__ import annotations

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .indicators import breakout_retest_trigger
from .strategy import SessionBreakoutER
from .types import Direction, ExitPlan, NoSignal, Signal


class BreakoutRetestER(SessionBreakoutER):
    name = "BreakoutRetestER"

    def __init__(self, config: dict):
        super().__init__(config)
        r = (config or {}).get("retest", {})
        # Exit geometry is this strategy's own decision (spec 08 §5.8), NOT inherited:
        self.retest_atr_mult_sl = float(r.get("atr_mult_sl", 1.0))
        self.retest_target_r = float(r.get("target_r", 1.5))
        # Pure stop/target exit: disable the inherited break-even manage() (no new semantic).
        self.move_be_after_r = None

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
        # reconstructs the break -> retest -> resume sequence purely from this slice each call.
        post = [b for b in sess
                if self._london(b.ts_open_utc).time() >= or_end
                and ensure_utc(b.ts_open_utc) <= ensure_utc(last.ts_open_utc)]
        highs = [b.high for b in post]
        lows = [b.low for b in post]
        closes = [b.close for b in post]

        if breakout_retest_trigger(highs, lows, closes, long_level, "long"):
            return self._retest_signal(Direction.LONG, last.close, regime, now, context_bias)
        if breakout_retest_trigger(highs, lows, closes, short_level, "short"):
            return self._retest_signal(Direction.SHORT, last.close, regime, now, context_bias)
        return NoSignal(now, "no_retest_entry")

    # ------------------------------------------------------------------
    def _retest_signal(self, direction, entry, regime, now, bias):
        """Honest market fill at the resume bar's CLOSE; stop = 1.0×ATR, single 1.5R target."""
        sl_pips = self.retest_atr_mult_sl * regime.atr_pips
        if sl_pips <= 0:
            return NoSignal(now, "degenerate_stop")
        r = (self.retest_target_r,)
        if direction is Direction.LONG:
            sl_price = entry - sl_pips * self.pip
            targets = (entry + self.retest_target_r * sl_pips * self.pip,)
        else:
            sl_price = entry + sl_pips * self.pip
            targets = (entry - self.retest_target_r * sl_pips * self.pip,)
        plan = ExitPlan(initial_sl_price=sl_price, initial_sl_pips=sl_pips, targets=targets,
                        target_r_multiples=r, partial_fractions=(1.0,),
                        move_be_after_r=None, trail=None)
        return Signal(instrument=self.config.get("instrument", "EURUSD"),
                      ts_decision_utc=now, direction=direction, entry_type="market",
                      entry_price=entry, exit_plan=plan, regime=regime,
                      session="london_ny_overlap", breakout_level=entry,
                      entry_reason="break_retest_resume + ER>=thr + ATR_normal",
                      context_bias=bias, config_version=self.config_version)
