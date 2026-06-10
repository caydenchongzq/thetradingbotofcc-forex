"""AsianSweepFadeRR — research-engine candidate (spec 08, 2026-06-10).

The **asymmetric-R:R** variant of the rejected [[2026-06-08-asian-sweep-fade]]. That report
showed the Asian-range sweep DOES reverse more often than not (win rate 54.7%) but was
*structurally negative* as a **symmetric-1R** system: with the stop at max(structure, 1.2xATR)
the average loss exceeded the average win, so every fold + the lockbox went negative. Its own
Lessons (1) and Next-steps prescribed the precise follow-on tested here:

    "test the asymmetric-R version: tight structural stop above the sweep wick only, >=2R
     target -- but a fade variant must argue why its R distribution differs from the
     [[2026-06-07-tp-2r-sweep]] rejection of >=2R targets on the incumbent."

What is DIFFERENT vs AsianSweepFade (the only changes; entry/regime held constant so the
exit geometry is the cleanly-isolated variable):
  1. **Tight stop at the wick.** sl_pips = max(distance-to-sweep-extreme + wick_buffer,
     1.0xATR). The failed-breakout thesis is invalidated the moment price reclaims the swept
     extreme, so the stop belongs JUST BEYOND the wick -- not floored at the incumbent's
     1.2xATR (which made the rejected version's stop structurally wider than its 1R target).
     The 1.0xATR floor (the bottom of spec 08 §5.8's range) only guards a degenerate
     near-zero stop when the bar closes adjacent to its extreme.
  2. **Single 2.0R target (R:R = 1:2)**, replacing the symmetric 1R. The reversion target
     lies back through the range; per the Costa SSRN evidence (major-pair breakouts invalidate
     / mean-revert in >75% of mapped 20-day-range occurrences) the snap-back routinely travels
     >= 2x a tight wick-stop. A single asymmetric target (no partials, no BE move) cleanly
     tests the payoff hypothesis the 1R version failed.
  3. **Fade window widened 11:00 -> 12:00 London** (a-priori, the ONLY reason being to clear
     the 200-trade sample_size floor: AsianSweepFade got 179 trades in the 3h window; +1h of
     still-liquid pre-overlap London restores headroom). Not tuned on results.

Why the [[2026-06-07-tp-2r-sweep]] rejection does NOT bind this (spec 08 §4.3): that rejected
2R on the *incumbent breakout* -- a spent-momentum continuation whose follow-through rarely
reaches 2R. A fade enters at the reversion extreme with the whole range to travel back
through, a structurally different (higher-hit-rate-at-2R) R-distribution. Falsifiable; the
gates + walk-forward + lockbox are the arbiter.

Dev-isolation (CLAUDE.md + spec 08 §5): subclasses AsianSweepFade -> reuses its evaluate()
(sweep detection), _fade_regime (inverted-ER gate), _already_fired, _blackout, manage, tz.
Only ``__init__`` (one new param) and ``_fade_signal`` (exit geometry) are overridden. The
incumbent AND AsianSweepFade classes are unmodified. PURE function of
(bars, now, context_bias, calendar); every degraded path -> NoSignal. Exits use the standard
ExitPlan seam (broker-side SL + single TP in both live and backtest) so live == backtest is
preserved WITHOUT a live-mirror session. Reaches live ONLY via a human-approved ConfigStore
promotion -- never from a research run.

Config additions (under ``fade:``; defaults a-priori, deliberately NOT swept):
    window_end: "12:00"        # widened from 11:00 to clear the 200-trade floor
    wick_buffer_pips: 0.5      # stop sits just BEYOND the sweep extreme
  and (under ``exits:``):
    atr_mult_sl: 1.0           # floor only; the wick distance is the true stop
    target_r_multiples: [2.0]  # single asymmetric target
    partial_fractions: [1.0]
    move_be_after_r: null
"""

from __future__ import annotations

from src.common.timeutil import ensure_utc

from .strategy_asian_sweep import AsianSweepFade
from .types import Direction, ExitPlan, NoSignal, Signal


class AsianSweepFadeRR(AsianSweepFade):
    name = "AsianSweepFadeRR"

    def __init__(self, config: dict):
        super().__init__(config)
        f = (config or {}).get("fade", {})
        # Stop sits just BEYOND the sweep wick (mechanism's invalidation level).
        self.wick_buffer_pips = float(f.get("wick_buffer_pips", 0.5))

    # ------------------------------------------------------------------
    def _fade_signal(self, direction, last, asian_high, asian_low, regime, now, bias):
        """Asymmetric exit geometry: tight wick stop (1.0xATR floor) + single >=2R target.

        Overrides AsianSweepFade._fade_signal; entry/regime detection is the inherited
        evaluate()/_fade_regime, unchanged."""
        entry = last.close
        if direction is Direction.SHORT:
            struct_pips = (last.high - entry) / self.pip      # distance to the sweep extreme
        else:
            struct_pips = (entry - last.low) / self.pip
        # Tight stop just beyond the wick; 1.0xATR floor only avoids a degenerate stop.
        sl_pips = max(struct_pips + self.wick_buffer_pips, self.atr_mult_sl * regime.atr_pips)
        if sl_pips <= 0:
            return NoSignal(ensure_utc(now), "degenerate_stop")
        if direction is Direction.LONG:
            sl_price = entry - sl_pips * self.pip
            targets = tuple(entry + r * sl_pips * self.pip for r in self.target_r)
        else:
            sl_price = entry + sl_pips * self.pip
            targets = tuple(entry - r * sl_pips * self.pip for r in self.target_r)
        plan = ExitPlan(initial_sl_price=sl_price, initial_sl_pips=sl_pips, targets=targets,
                        target_r_multiples=self.target_r, partial_fractions=self.partials,
                        move_be_after_r=self.move_be_after_r, trail=None)
        return Signal(instrument=self.config.get("instrument", "EURUSD"),
                      ts_decision_utc=ensure_utc(now), direction=direction,
                      entry_type="market", entry_price=entry, exit_plan=plan, regime=regime,
                      session="london_open_fade_rr",
                      breakout_level=asian_high if direction is Direction.SHORT else asian_low,
                      entry_reason="asian_sweep_fade + asymmetric_RR + ER<thr + ATR_normal",
                      context_bias=bias, config_version=self.config_version)
