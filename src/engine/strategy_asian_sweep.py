"""AsianSweepFade — research-engine candidate (spec 08, 2026-06-08).

Fade the FAILED breakout of the Asian-session range in early London ("liquidity sweep" /
ICT turtle soup / AMD): London open often pushes through the Asian high/low to trigger
stops, then reverses back into the range. Falsifiable spec pre-registered in
docs/research/strategies/2026-06-07-asian-sweep-fade.md BEFORE this implementation:

  * Asian range = London 00:00-08:00 M15 high/low. Trade window = London 08:00-11:00.
  * Short: a closed bar's high exceeds asian_high + buffer AND the bar CLOSES back inside
    the range  =>  market entry at that close. Long is the mirror at the asian low.
  * Stop above the sweep extreme: sl_pips = max(structure distance, atr_mult_sl * ATR).
  * Single 1R target (the incumbent's validated exit machinery — no live-mirror needed).
  * Regime gate INVERTED vs the incumbent (a-priori decision, recorded in the idea report
    before testing): mean reversion wants the market NOT to be trending, so require
    ER < er_threshold (the exact complement of the incumbent's trend gate — no new free
    parameter) while keeping the same NORMAL ATR band (too quiet = no sweep energy and
    costs dominate; too wild = unsafe for fixed-R sizing).

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
- Subclasses the incumbent for shared, already-tested machinery (_regime, _blackout,
  manage, tz handling); ``evaluate`` is fully replaced. The incumbent class is NOT
  modified. Exits use the standard ExitPlan seam (initial SL + final TP are broker-side
  in both live and backtest), so live == backtest is preserved without a mirror session.
- PURE function of (bars, now, context_bias, calendar): no clock, no network, no state.
  Every degraded path (short history, missing Asian range, ambiguous double-sided sweep,
  bad bar sequence, degenerate regime) resolves to ``NoSignal`` (fail safe).
- Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``fade:``; defaults chosen a priori, deliberately NOT swept):
    asian_start: "00:00"     # London time; Asian/overnight range accumulation
    asian_end: "08:00"
    window_start: "08:00"    # fade window — early London only
    window_end: "11:00"
    sweep_buffer_pips: 1.5   # reuse of the incumbent's default breakout buffer; not tuned
    min_asian_bars: 16       # >= 4h of M15 bars or the range is not meaningful (fail safe)
    one_shot_per_side: true
"""

from __future__ import annotations

from dataclasses import replace

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .strategy import SessionBreakoutER, _t
from .types import Direction, ExitPlan, NoSignal, Signal


class AsianSweepFade(SessionBreakoutER):
    name = "AsianSweepFade"

    def __init__(self, config: dict):
        super().__init__(config)
        f = (config or {}).get("fade", {})
        self.asian_start = _t(f.get("asian_start", "00:00"))
        self.asian_end = _t(f.get("asian_end", "08:00"))
        self.fade_win_start = _t(f.get("window_start", "08:00"))
        self.fade_win_end = _t(f.get("window_end", "11:00"))
        self.sweep_buffer_pips = float(f.get("sweep_buffer_pips", 1.5))
        self.min_asian_bars = int(f.get("min_asian_bars", 16))
        self.fade_one_shot = bool(f.get("one_shot_per_side", True))

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
        if not (self.fade_win_start <= lon_now.time() < self.fade_win_end):
            return NoSignal(now, "outside_session")

        # Stale data guard (same convention as the incumbent).
        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        # Today's Asian range (same London date, strictly before the fade window).
        day = lon_now.date()
        asian = [b for b in bars
                 if self._london(b.ts_open_utc).date() == day
                 and self.asian_start <= self._london(b.ts_open_utc).time() < self.asian_end]
        if len(asian) < self.min_asian_bars:
            return NoSignal(now, "insufficient_asian_range")
        asian_high = max(b.high for b in asian)
        asian_low = min(b.low for b in asian)
        buf = self.sweep_buffer_pips * self.pip

        regime = self._fade_regime(bars)
        if not regime.regime_gate_passed:
            return NoSignal(now, "regime_gate_failed")

        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        swept_high = last.high > asian_high + buf
        swept_low = last.low < asian_low - buf
        closed_inside = asian_low < last.close < asian_high
        if swept_high and swept_low:
            return NoSignal(now, "ambiguous_sweep")     # fail safe: both stops run

        if swept_high and closed_inside:
            if self.fade_one_shot and self._already_fired(
                    bars, day, asian_high, asian_low, buf, side="short"):
                return NoSignal(now, "sweep_already_faded")
            return self._fade_signal(Direction.SHORT, last, asian_high, asian_low,
                                     regime, now, context_bias)
        if swept_low and closed_inside:
            if self.fade_one_shot and self._already_fired(
                    bars, day, asian_high, asian_low, buf, side="long"):
                return NoSignal(now, "sweep_already_faded")
            return self._fade_signal(Direction.LONG, last, asian_high, asian_low,
                                     regime, now, context_bias)
        return NoSignal(now, "no_sweep")

    # ------------------------------------------------------------------
    def _fade_regime(self, bars):
        """Incumbent regime measurement, gate INVERTED on ER (a-priori, see module doc).

        Pass iff: not degenerate AND vol_state is NORMAL AND er < er_threshold."""
        r = super()._regime(bars)
        degenerate = not (r.atr_pips > 0) or r.er != r.er
        passed = ((not degenerate)
                  and r.vol_state.value == "normal"
                  and r.er < self.er_threshold)
        return replace(r, regime_gate_passed=passed)

    def _already_fired(self, bars, day, asian_high, asian_low, buf, side) -> bool:
        """True if an EARLIER closed bar in today's fade window already met the same-side
        sweep-entry condition (close-based, like the incumbent's one-shot)."""
        last_open = ensure_utc(bars[-1].ts_open_utc)
        for b in bars:
            lon = self._london(b.ts_open_utc)
            if lon.date() != day:
                continue
            if not (self.fade_win_start <= lon.time() < self.fade_win_end):
                continue
            if ensure_utc(b.ts_open_utc) >= last_open:
                continue
            inside = asian_low < b.close < asian_high
            if side == "short" and b.high > asian_high + buf and inside:
                return True
            if side == "long" and b.low < asian_low - buf and inside:
                return True
        return False

    def _fade_signal(self, direction, last, asian_high, asian_low, regime, now, bias) -> Signal:
        entry = last.close
        if direction is Direction.SHORT:
            struct_pips = (last.high - entry) / self.pip   # distance to the sweep extreme
        else:
            struct_pips = (entry - last.low) / self.pip
        sl_pips = max(struct_pips, self.atr_mult_sl * regime.atr_pips)
        if sl_pips <= 0:
            return NoSignal(now, "degenerate_stop")
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
                      ts_decision_utc=now, direction=direction, entry_type="market",
                      entry_price=entry, exit_plan=plan, regime=regime,
                      session="london_open_fade",
                      breakout_level=asian_high if direction is Direction.SHORT else asian_low,
                      entry_reason="asian_sweep_fade + ER<thr + ATR_normal",
                      context_bias=bias, config_version=self.config_version)
