"""TrendPullbackEMA — research-engine candidate (spec 08, 2026-06-12).

Hypothesis: in an ER-confirmed directional trend during the London/NY overlap, a SHALLOW
pullback to a rising (resp. falling) fast EMA that then RESUMES in the trend direction is a
high-probability continuation entry. The economic story: an impulse leg attracts profit-takers
and late counter-trend fades; when that supply/demand is absorbed at the EMA and price reasserts
(closes back through the EMA *and* past the prior bar's extreme), the trend's initiating flow is
still in control and continues. The trader on the other side is the fader who is now offside.

This is a NEW signal source — a structural RETRACEMENT entry — NOT a subset of the incumbent's
breakout-close entries. It is therefore distinct from the rejected breakout entry-timing subset
[[2026-06-11-breakout-retest]] (which was subtractive on breakouts and double-jeopardy on the
200-trade floor): a pullback fires on its OWN structure, additive to the strategy library rather
than carving the incumbent's trade set. It is also distinct from the rejected trend probes —
serial-correlation [[2026-06-07-intraday-ts-momentum]] and time-of-day drift
[[2026-06-09-late-session-drift]] — because the edge claim here is a STRUCTURAL retracement in a
confirmed trend, not an autocorrelation or a clock effect.

Sources (hypothesis only; the backtester is the arbiter — spec 08 §6):
  * 20-MA pullback continuation rules (slope filter + reversal-candle confirmation, intraday
    1m/5m/15m): https://www.tradingsim.com/blog/20-moving-average-pullback
  * 9/20-EMA pullback day-trading rules (trend filter, enter on resume close, stop beyond EMA,
    target 1:2+): https://forexalgo-trader.com/resources/282-the-50-ema-pullback-strategy-a-clean-repeatable-approach-to-trend-trading
    and https://fxnx.com/en/blog/master-20-ema-pullback-strategy
  * Moving-average strategy backtest survey (short-window EMA as an intraday momentum filter):
    https://www.quantifiedstrategies.com/moving-average-trading-strategy/

Exit geometry (spec 08 §5.8 — chosen per mechanism, NOT inherited from the incumbent):
  * stop = max(structural, 1.0×ATR): the structural stop sits just beyond the pullback extreme
    (the swing low/high the entry leans on); a 1.0×ATR floor keeps thin-bar noise from stopping
    a valid hold. This is TIGHTER than the incumbent's 1.2×ATR because a pullback entry sits at
    a favourable retracement location (near support), so it does not need the breakout's wider
    cushion — justified a priori, not defaulted.
  * target = 2.0R (R:R = 1:2): the discounted entry near the EMA leaves room for the trend to
    resume toward and beyond the prior swing extreme. The recorded ≥2R rejection on the
    incumbent [[2026-06-07-tp-2r-sweep]] does NOT bind: that failure was specific to
    BREAKOUT-CLOSE entries whose win rate did not sustain to 2R; a pullback enters at a tighter,
    structurally-supported stop and a better location, so the per-trade reward potential differs.
    The arbiter (gates + walk-forward + lockbox) still decides.
  * break-even after 1R via the INCUMBENT manage() — no new manage semantics, so NO live-mirror
    flag is required (contrast [[2026-06-09-late-session-drift]]'s time-box close).

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses SessionBreakoutER for shared PURE machinery (_regime, _blackout, tz, manage).
    The incumbent class is NOT modified; ``evaluate`` is fully replaced; ``manage`` is inherited
    (break-even-after-1R only — an existing, already-live-mirrored semantic).
  * PURE function of (bars, now, context_bias, calendar): no clock, no network, no state. Every
    degraded path (short history, bad bar sequence, stand-down, stale data, degenerate regime/
    stop, no EMA) resolves to ``NoSignal`` (fail safe).
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``pullback:``; defaults chosen a priori, deliberately NOT swept):
    ema_window: 20           # fast EMA the pullback leans on
    slope_lookback: 5        # EMA[-1] vs EMA[-1-slope_lookback] sets trend direction
    pullback_lookback: 6     # how many recent bars to scan for the EMA touch
    atr_mult_sl: 1.0         # ATR floor on the structural stop (disaster-guard)
    target_r: 2.0            # take-profit R-multiple (R:R = 1:2)
    move_be_after_r: 1.0     # inherited manage(): SL -> break-even after +1R
  Session window reuses the incumbent ``session.window_start/window_end`` (London/NY overlap).
"""

from __future__ import annotations

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .indicators import ema_series
from .strategy import SessionBreakoutER
from .types import Direction, ExitPlan, NoSignal, Signal


class TrendPullbackEMA(SessionBreakoutER):
    name = "TrendPullbackEMA"

    def __init__(self, config: dict):
        super().__init__(config)
        p = (config or {}).get("pullback", {})
        self.ema_window = int(p.get("ema_window", 20))
        self.slope_lookback = int(p.get("slope_lookback", 5))
        self.pullback_lookback = int(p.get("pullback_lookback", 6))
        # Exit geometry is this strategy's own decision (spec 08 §5.8), NOT inherited:
        self.pb_atr_mult_sl = float(p.get("atr_mult_sl", 1.0))
        self.pb_target_r = float(p.get("target_r", 2.0))
        self.pb_move_be_after_r = p.get("move_be_after_r", 1.0)
        # manage() inherited from SessionBreakoutER honours this BE threshold:
        self.move_be_after_r = self.pb_move_be_after_r

    # ------------------------------------------------------------------
    def warmup_bars(self) -> int:
        base = super().warmup_bars()
        return max(base, self.ema_window + self.slope_lookback + self.pullback_lookback + 2)

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
        if not (self.win_start <= lon_now.time() < self.win_end):
            return NoSignal(now, "outside_session")

        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        regime = self._regime(bars)
        if not regime.regime_gate_passed:
            return NoSignal(now, "regime_gate_failed")

        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        # Today's session bars (same London date, inside the overlap window).
        day = lon_now.date()
        sess = [b for b in bars
                if self._london(b.ts_open_utc).date() == day
                and self.win_start <= self._london(b.ts_open_utc).time() < self.win_end]
        if len(sess) < 2:
            return NoSignal(now, "building_session")

        closes = [b.close for b in bars]
        es = ema_series(closes, self.ema_window)
        if len(es) < self.slope_lookback + 1:
            return NoSignal(now, "no_ema")

        side = self._resume_side(bars, es)
        if side is None:
            return NoSignal(now, "no_pullback_resume")

        # One-shot per side per session: do not re-enter if an earlier session bar this day
        # already completed the same resume for this side (mirrors the incumbent's one_shot).
        if self.one_shot and self._already_fired(bars, es, sess, side):
            return NoSignal(now, "already_entered")

        return self._pullback_signal(bars, es, side, regime, now, context_bias)

    # ------------------------------------------------------------------
    def _ema_at(self, es, k: int):
        """EMA aligned to ``bars[-1-k]`` (k=0 is the last bar). None if out of range."""
        if 0 <= k < len(es):
            return es[-1 - k]
        return None

    def _resume_side(self, bars, es):
        """Return Direction if the LAST bar completes a valid pullback->resume, else None.

        LONG: EMA rising (slope up) AND last close > EMA  ->  some recent bar dipped its LOW
        to/through its EMA (pullback)  AND  the last bar closes back above EMA and above the
        prior bar's HIGH (momentum resume). SHORT is the mirror. Pure, fail-safe."""
        ema_now = self._ema_at(es, 0)
        ema_ref = self._ema_at(es, self.slope_lookback)
        if ema_now is None or ema_ref is None:
            return None
        last = bars[-1]
        prev = bars[-2]
        # LONG branch
        if ema_now > ema_ref and last.close > ema_now and last.close > prev.high:
            if self._recent_touch(bars, es, "long"):
                return Direction.LONG
        # SHORT branch
        if ema_now < ema_ref and last.close < ema_now and last.close < prev.low:
            if self._recent_touch(bars, es, "short"):
                return Direction.SHORT
        return None

    def _recent_touch(self, bars, es, side: str) -> bool:
        """True if any of the last ``pullback_lookback`` bars BEFORE the current bar touched
        the EMA from the trend side (a shallow pullback)."""
        for j in range(1, self.pullback_lookback + 1):
            ema_j = self._ema_at(es, j)
            if ema_j is None or (len(bars) - 1 - j) < 0:
                break
            b = bars[-1 - j]
            if side == "long" and b.low <= ema_j:
                return True
            if side == "short" and b.high >= ema_j:
                return True
        return False

    def _already_fired(self, bars, es, sess, side: Direction) -> bool:
        """One-shot: re-check the resume condition on each earlier session bar this day; if a
        prior bar already completed the same-side resume, the trade was taken — block."""
        if not sess:
            return False
        first_ts = ensure_utc(sess[0].ts_open_utc)
        last_ts = ensure_utc(bars[-1].ts_open_utc)
        # Indices (from the end) of session bars strictly before the current bar.
        for idx in range(1, len(bars)):
            b = bars[-1 - idx]
            ts = ensure_utc(b.ts_open_utc)
            if ts < first_ts:
                break
            if ts >= last_ts:
                continue
            sub = bars[: len(bars) - idx]
            if len(sub) < 2:
                continue
            sub_es = ema_series([x.close for x in sub], self.ema_window)
            if len(sub_es) < self.slope_lookback + 1:
                continue
            if self._resume_side(sub, sub_es) is side:
                return True
        return False

    def _pullback_signal(self, bars, es, side: Direction, regime, now, bias) -> Signal:
        entry = bars[-1].close
        # Structural stop: just beyond the pullback extreme over the lookback window.
        lo = entry
        hi = entry
        for j in range(0, self.pullback_lookback + 1):
            if (len(bars) - 1 - j) < 0:
                break
            b = bars[-1 - j]
            lo = min(lo, b.low)
            hi = max(hi, b.high)
        atr_pips = regime.atr_pips
        if atr_pips <= 0:
            return NoSignal(now, "degenerate_stop")
        if side is Direction.LONG:
            struct_pips = (entry - lo) / self.pip
            sl_pips = max(struct_pips, self.pb_atr_mult_sl * atr_pips)
            if sl_pips <= 0:
                return NoSignal(now, "degenerate_stop")
            sl_price = entry - sl_pips * self.pip
            targets = (entry + self.pb_target_r * sl_pips * self.pip,)
        else:
            struct_pips = (hi - entry) / self.pip
            sl_pips = max(struct_pips, self.pb_atr_mult_sl * atr_pips)
            if sl_pips <= 0:
                return NoSignal(now, "degenerate_stop")
            sl_price = entry + sl_pips * self.pip
            targets = (entry - self.pb_target_r * sl_pips * self.pip,)
        plan = ExitPlan(initial_sl_price=sl_price, initial_sl_pips=sl_pips, targets=targets,
                        target_r_multiples=(self.pb_target_r,), partial_fractions=(1.0,),
                        move_be_after_r=self.pb_move_be_after_r, trail=None)
        return Signal(instrument=self.config.get("instrument", "EURUSD"),
                      ts_decision_utc=now, direction=side, entry_type="market",
                      entry_price=entry, exit_plan=plan, regime=regime,
                      session="london_ny_overlap", breakout_level=entry,
                      entry_reason="ema_pullback_resume + ER>=thr + ATR_normal",
                      context_bias=bias, config_version=self.config_version)
