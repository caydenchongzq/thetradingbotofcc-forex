"""VWAPStretchReversion — research-engine candidate (spec 08, 2026-06-16).

Fade a statistical OVER-EXTENSION of price away from the volume-weighted session mean
(session VWAP), back toward that mean, in a RANGING regime. Falsifiable spec pre-registered
in docs/research/strategies/2026-06-16-vwap-stretch-reversion.md BEFORE this implementation.

Economic rationale (who is on the other side): session VWAP is the intraday "fair value"
institutional execution benchmarks against; benchmarked flow leans against large excursions
from it, so in a non-trending session a price stretched far from VWAP tends to revert. The
edge, if real, is liquidity provision into a transient imbalance — NOT a directional bet.

Why this is NOT the closed Asian sweep-fade family (spec 08 §4.3 differentiation):
  * The sweep-fade ([[2026-06-08-asian-sweep-fade]] / [[2026-06-10-asian-sweep-fade-rr]],
    family CLOSED) triggers on a STRUCTURAL event — a poke through a fixed overnight-range
    high/low that closes back inside. Its recorded failure mode: fading a swept *level*
    stands in front of stop-run momentum (the sweep is often the START of expansion), giving
    a constant-negative PF that neither 1R nor 2R rescues.
  * This candidate has NO level and NO failed-breakout requirement. The trigger is a
    continuous *distance from the session VWAP* (a statistical mean), selecting "price is far
    from today's fair value in a choppy session", not "price just ran a key level". Different
    trade population, different conditional distribution — so the sweep-fade failure mode is
    not assumed to carry over (the backtester arbitrates).

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
- Subclasses the incumbent for shared, already-tested machinery (_regime, _blackout, manage,
  tz handling); ``evaluate`` is fully replaced. The incumbent class is NOT modified.
- MARKET entry at the confirmed close (entry_price == last.close): the live fill ≈ the signal
  price, so it is live-fillable from day one (the central lesson of
  [[2026-06-15-resting-stop-and-market-entry]] — validate live-fillability, not just gates).
- PURE function of (bars, now, context_bias, calendar): no clock, no network, no state. Every
  degraded path (short history, building VWAP, degenerate VWAP/regime, bad bar sequence,
  ambiguous two-sided stretch) resolves to ``NoSignal`` (fail safe).
- Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Exit geometry (spec 08 §5.8 — pre-registered, NOT inherited by reflex):
    stop  = max(distance-to-this-bar's-extreme, atr_mult_sl * ATR), atr_mult_sl = 1.0
            (a dedicated lever, deliberately NOT the incumbent's 1.2: a reversion trade wants
            room past the excursion's tip — it is only wrong if the stretch keeps extending
            into a genuine trend, which the 1.0xATR-beyond-extreme stop catches cleanly).
    target = 1.5R fixed (target_r_multiples = [1.5]).  The mechanism's natural target is the
            mean: entry is >= stretch_atr_mult(=1.5) x ATR from VWAP, and stop ~= 1.0 x ATR,
            so reverting toward VWAP travels ~1.5 x ATR ~= 1.5R. R:R 1.5:1 (>= 1:1 floor;
            the >=2R rejections [[2026-06-07-tp-2r-sweep]] do not bind a 1.5R target derived
            from the reversion distance, not bolted on). Single full exit, no scaling.

Config (under ``vwap:``; defaults chosen a priori, deliberately NOT swept):
    anchor: "08:00"          # London time; session-VWAP accumulation start (London open)
    window_start: "08:00"    # trade window — liquid London + overlap hours only (the
    window_end: "16:00"      #   thin-hour spread that killed LateSessionDrift is avoided)
    min_session_bars: 8      # >= 2h of M15 bars since the anchor or VWAP is not meaningful
    stretch_atr_mult: 1.5    # fade when |close - vwap| >= this * ATR
The regime gate is INVERTED on ER vs the incumbent (ER < er_threshold => ranging) with the
same NORMAL ATR band, identical to the fade family's a-priori choice — mean reversion wants a
non-trending session. The DIFFERENTIATOR here is the entry trigger, not the gate.
"""

from __future__ import annotations

from dataclasses import replace

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .indicators import session_vwap
from .strategy import SessionBreakoutER, _t
from .types import Direction, ExitPlan, NoSignal, Signal


class VWAPStretchReversion(SessionBreakoutER):
    name = "VWAPStretchReversion"

    def __init__(self, config: dict):
        super().__init__(config)
        v = (config or {}).get("vwap", {})
        self.vwap_anchor = _t(v.get("anchor", "08:00"))
        self.vwap_win_start = _t(v.get("window_start", "08:00"))
        self.vwap_win_end = _t(v.get("window_end", "16:00"))
        self.min_session_bars = int(v.get("min_session_bars", 8))
        self.stretch_atr_mult = float(v.get("stretch_atr_mult", 1.5))

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
        if not (self.vwap_win_start <= lon_now.time() < self.vwap_win_end):
            return NoSignal(now, "outside_session")

        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        # Today's session bars: same London date, in [anchor, window_end), up to and
        # including the last (current) bar. VWAP accumulates over exactly these.
        day = lon_now.date()
        sess = self._session_bars(bars, day, upto_open=ensure_utc(last.ts_open_utc))
        if len(sess) < self.min_session_bars:
            return NoSignal(now, "building_session_vwap")

        vwap = session_vwap([b.high for b in sess], [b.low for b in sess],
                            [b.close for b in sess], [b.volume for b in sess])
        if vwap != vwap:  # NaN — degenerate (no usable volume)
            return NoSignal(now, "degenerate_vwap")

        regime = self._mr_regime(bars)
        if not regime.regime_gate_passed:
            return NoSignal(now, "regime_gate_failed")
        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        atr_pips = regime.atr_pips
        thr_pips = self.stretch_atr_mult * atr_pips
        if thr_pips <= 0:
            return NoSignal(now, "degenerate_stretch")

        up_pips = (last.close - vwap) / self.pip      # >0 => price above VWAP
        down_pips = (vwap - last.close) / self.pip     # >0 => price below VWAP
        stretched_up = up_pips >= thr_pips
        stretched_down = down_pips >= thr_pips
        if stretched_up and stretched_down:
            return NoSignal(now, "ambiguous_stretch")  # cannot happen for thr>0; fail safe

        # Edge-trigger: enter only on the bar that FIRST closes beyond the stretch band, not on
        # every bar while it stays stretched (price reverting then re-stretching re-arms it).
        if stretched_up:
            if self._prev_already_stretched(bars, day, vwap, thr_pips, side="short"):
                return NoSignal(now, "stretch_not_fresh")
            return self._stretch_signal(Direction.SHORT, last, vwap, regime, now, context_bias)
        if stretched_down:
            if self._prev_already_stretched(bars, day, vwap, thr_pips, side="long"):
                return NoSignal(now, "stretch_not_fresh")
            return self._stretch_signal(Direction.LONG, last, vwap, regime, now, context_bias)
        return NoSignal(now, "no_stretch")

    # ------------------------------------------------------------------
    def _session_bars(self, bars, day, upto_open):
        """Bars in today's session window (same London date, [anchor, window_end)) whose open
        is <= ``upto_open``. Used both for the VWAP accumulation and the freshness check."""
        out = []
        for b in bars:
            lon = self._london(b.ts_open_utc)
            if lon.date() != day:
                continue
            if not (self.vwap_anchor <= lon.time() < self.vwap_win_end):
                continue
            if ensure_utc(b.ts_open_utc) > upto_open:
                continue
            out.append(b)
        return out

    def _prev_already_stretched(self, bars, day, vwap, thr_pips, side) -> bool:
        """True if the immediately-preceding in-window bar's close was ALREADY beyond the same
        stretch band (so the current bar is a continuation, not a fresh excursion). Uses the
        current VWAP/threshold as a slow-moving reference (O(1), deterministic). A prev bar in a
        different day/window counts as 'not stretched' => the current bar is fresh."""
        if len(bars) < 2:
            return False
        prev = bars[-2]
        lon = self._london(prev.ts_open_utc)
        if lon.date() != day or not (self.vwap_anchor <= lon.time() < self.vwap_win_end):
            return False
        up_pips = (prev.close - vwap) / self.pip
        down_pips = (vwap - prev.close) / self.pip
        if side == "short":
            return up_pips >= thr_pips
        return down_pips >= thr_pips

    def _mr_regime(self, bars):
        """Incumbent regime measurement, gate INVERTED on ER (ranging): pass iff not
        degenerate AND vol_state is NORMAL AND er < er_threshold (mean reversion wants chop)."""
        r = super()._regime(bars)
        degenerate = not (r.atr_pips > 0) or r.er != r.er
        passed = ((not degenerate)
                  and r.vol_state.value == "normal"
                  and r.er < self.er_threshold)
        return replace(r, regime_gate_passed=passed)

    def _stretch_signal(self, direction, last, vwap, regime, now, bias):
        entry = last.close
        if direction is Direction.SHORT:
            struct_pips = (last.high - entry) / self.pip   # distance to this bar's extreme
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
                      session="vwap_session_reversion", breakout_level=vwap,
                      entry_reason="vwap_stretch_fade + ER<thr + ATR_normal",
                      context_bias=bias, config_version=self.config_version)
