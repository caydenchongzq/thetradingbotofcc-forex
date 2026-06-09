"""LateSessionDrift — research-engine candidate (spec 08, 2026-06-09).

Hypothesis: EURUSD exhibits a persistent POSITIVE price drift during the thin-liquidity
late-London / NY-afternoon window (~21:00-00:00 London). Pre-registered probe over
2024-01..2026-05 (docs/research/strategies/2026-06-09-late-session-drift.md): mean
+2.3 pip/night, 64.7% up-nights, positive in 9/10 calendar quarters incl. the flat/down
2024 regime -- i.e. NOT merely an artifact of the 2025 EURUSD uptrend.

Mechanism (who is on the other side): end-of-(NY)-day positioning and reduced liquidity
after the 16:00 London WM/R fix and into / past the 17:00 NY options-settlement window;
systematic rebalancing and carry-roll flows skew EURUSD demand upward when book depth is
thin. Falsifiable: if the drift is a 2025-trend artifact it collapses on the walk-forward
folds and the sealed lockbox (the arbiter, not the probe, decides).

Design (a-priori, deliberately NOT swept):
  * Entry: ONE long market entry per day, on the M15 bar that OPENS at ``entry_time``
    (21:00 London).
  * Exit: TIME-BOXED -- flat after ``hold_bars`` M15 bars (12 = 3h, ~00:00 London), via an
    explicit ``strategy.manage()`` close (the engine's documented time-stop hook). A
    protective broker stop and a nominal 1R take-profit also ride the trade.
  * Regime: only the incumbent's NORMAL ATR band (fixed-R sizing safety); NO ER trend gate
    -- the drift is a flow phenomenon, not a trend-regime one (a-priori decision).

Exit geometry (spec 08 §5.8 -- chosen per mechanism, NOT inherited from the incumbent):
  * stop = 1.5×ATR: a disaster-guard, not the primary exit; wide enough not to noise-out a
    slow 3-hour drift (the incumbent's 1.2×ATR would be too tight for a multi-hour hold).
  * target = 1.0R (R:R = 1:1 floor): banks only an outsized overshoot; the REAL exit is the
    time-box, so the TP is rarely hit (mean drift << stop). The single-1R machinery is
    reused with explicit justification, not by default.

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses SessionBreakoutER for shared PURE machinery (_regime, _blackout, tz). The
    incumbent class is NOT modified; ``evaluate`` and ``manage`` are fully replaced.
  * PURE function of (bars, now, context_bias, calendar): no clock, no network, no state.
    Every degraded path (short history, bad bar sequence, stand-down, stale data, degenerate
    regime/stop) resolves to ``NoSignal`` (fail safe).
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.
  * LIVE-MIRROR FLAG: the TIME-BOXED exit is a NEW ``manage()`` semantic vs the incumbent
    (which only moves SL to break-even). The backtester models it exactly (engine._manage
    honors ``close_all`` as a close-based time-stop) and the live bridge ``decide_manage``
    maps ``close_all`` -> ``close``, BUT the live runner has not yet exercised a manage-close
    on a real position. Therefore a config naming this strategy needs a human-supervised
    LIVE-MIRROR session before any promotion (spec 08 §5.4). Not promoted here.

Config (under ``drift:``; defaults chosen a priori, deliberately NOT swept):
    entry_time: "21:00"      # London; the single daily entry bar
    hold_bars: 12            # M15 bars held (=3h); time-box exit ~00:00 London
    atr_mult_sl: 1.5         # protective stop as an ATR multiple (disaster-guard)
    target_r: 1.0            # nominal take-profit R-multiple (R:R floor)
"""

from __future__ import annotations

from dataclasses import replace

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .strategy import ManageDecision, SessionBreakoutER, _t
from .types import Direction, ExitPlan, NoSignal, Signal


class LateSessionDrift(SessionBreakoutER):
    name = "LateSessionDrift"

    def __init__(self, config: dict):
        super().__init__(config)
        d = (config or {}).get("drift", {})
        self.entry_time = _t(d.get("entry_time", "21:00"))
        self.hold_bars = int(d.get("hold_bars", 12))
        # Exit geometry is this strategy's own decision (spec 08 §5.8), NOT inherited:
        self.atr_mult_sl = float(d.get("atr_mult_sl", 1.5))
        self.target_r0 = float(d.get("target_r", 1.0))

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

        # Fire on exactly the M15 bar that OPENS at entry_time (one entry per day; evaluate
        # is only called by the engine when flat, so this is inherently one-shot/day).
        lon_now = self._london(now)
        if not (lon_now.hour == self.entry_time.hour
                and lon_now.minute == self.entry_time.minute):
            return NoSignal(now, "outside_entry_bar")

        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        regime = self._drift_regime(bars)
        if not regime.regime_gate_passed:
            return NoSignal(now, "regime_gate_failed")

        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        return self._drift_signal(last, regime, now, context_bias)

    # ------------------------------------------------------------------
    def _drift_regime(self, bars):
        """Incumbent regime measurement; gate keeps ONLY the NORMAL ATR band (fixed-R sizing
        safety). The ER trend gate is intentionally dropped -- the drift is a flow effect."""
        r = super()._regime(bars)
        degenerate = not (r.atr_pips > 0) or r.er != r.er
        passed = (not degenerate) and r.vol_state.value == "normal"
        return replace(r, regime_gate_passed=passed)

    def _drift_signal(self, last, regime, now, bias) -> Signal:
        entry = last.close
        sl_pips = self.atr_mult_sl * regime.atr_pips
        if sl_pips <= 0:
            return NoSignal(now, "degenerate_stop")
        sl_price = entry - sl_pips * self.pip
        targets = (entry + self.target_r0 * sl_pips * self.pip,)
        plan = ExitPlan(initial_sl_price=sl_price, initial_sl_pips=sl_pips, targets=targets,
                        target_r_multiples=(self.target_r0,), partial_fractions=(1.0,),
                        move_be_after_r=None, trail=None)
        return Signal(instrument=self.config.get("instrument", "EURUSD"),
                      ts_decision_utc=now, direction=Direction.LONG, entry_type="market",
                      entry_price=entry, exit_plan=plan, regime=regime,
                      session="late_session_drift", breakout_level=entry,
                      entry_reason="late_session_long_drift + ATR_normal",
                      context_bias=bias, config_version=self.config_version)

    # ------------------------------------------------------------------
    def manage(self, open_trade, bars, now_utc) -> ManageDecision:
        """TIME-BOXED exit (the primary exit; see module docstring + live-mirror flag).

        Close once the position has been held ``hold_bars`` M15 bars. A London-time backstop
        also closes the trade once we have left the night window, so a data gap cannot leave
        the position open past the intended ~00:00 London flat-time."""
        held = getattr(open_trade, "bars_held", None)
        if held is None:
            return ManageDecision("hold")
        if held >= self.hold_bars:
            return ManageDecision("close_all")
        lon = self._london(ensure_utc(now_utc))
        if held >= 1 and not (self.entry_time.hour <= lon.hour <= 23):
            return ManageDecision("close_all")
        return ManageDecision("hold")
