"""NR7VolatilityBreakout — Crabel narrow-range (NR7) volatility-compression breakout.

DEV / RESEARCH strategy (spec 08 §5.1), registered but NEVER promoted. A standalone *new
family* — a volatility contraction->expansion breakout, not the incumbent's session opening-
range breakout, not a mean-reversion fade.

Mechanism (Toby Crabel, 1990): when a bar's high-low range is the *strictest narrowest of the
last ``lookback`` bars* (NR7 for lookback=7) the market is coiled; the subsequent break of that
bar's extreme tends to expand. We ARM a two-sided resting-stop OCO at the NR7 bar's close (a buy
stop at its high + buffer, a sell stop at its low - buffer); whichever level is touched intrabar
fills, the sibling cancels. The arm expires after ``entry_valid_bars`` bars if untouched.

WHY THIS IS LIVE-FILLABLE (the seam that bit the incumbent, CLAUDE.md invariant 3 /
docs/RESTING_STOP_FIX.md): the NR7 *setup completes at the NR7 bar's close* and the trigger
levels are that closed bar's extremes — both known BEFORE any breakout. So the resting stops can
be placed the moment the NR7 bar closes and are genuinely live-placeable (no retcode 10015). This
is the exact opposite of SessionBreakoutER, whose selection needed the *breakout bar's* close,
making a level-fill temporally unplaceable. Here selection PRECEDES the fill, so the intrabar
touch the backtester models is the same fill the live path can rest in advance ->
``live == backtest`` at the entry seam.

Exit geometry is pre-registered per spec 08 §5.8 in the dev config (stop ~1.0xATR, target 2.0R,
R:R 1:2 for an expected sub-50% win-rate breakout) — NOT inherited from the incumbent's 1.2/1R.

Subclasses ``SessionBreakoutER`` for ALL shared machinery (``_regime``, ``_signal``, ``manage``,
``_blackout``, ``_london``); only ``evaluate`` (and warmup) are replaced. The incumbent class is
untouched. No new manage semantics (single broker SL+TP, the validated seam) -> no live-mirror
needed."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias

from .indicators import is_narrow_range
from .strategy import SessionBreakoutER
from .types import ArmSignal, Direction, NoSignal, VolState


class NR7VolatilityBreakout(SessionBreakoutER):
    name = "NR7VolatilityBreakout"

    def __init__(self, config: dict):
        super().__init__(config)
        nr = (self.config.get("nr7", {}) or {})
        self.nr_lookback = int(nr.get("lookback", 7))
        self.entry_valid_bars = int(nr.get("entry_valid_bars", 4))
        # The contraction IS the setup, so by default we do NOT require the incumbent's
        # ER>=threshold *trend* pre-condition (that is the incumbent's mechanism, not this one).
        # Set True to additionally require a directional regime.
        self.require_trend = bool(nr.get("require_trend", False))

    def warmup_bars(self) -> int:
        return max(self.er_window, self.atr_window, self.nr_lookback) + 2

    def evaluate(self, bars, now_utc, context_bias, calendar=None):
        """Arm a two-sided resting-stop OCO when the last CLOSED bar is a strict NR(lookback)
        inside the liquid trading window and the volatility regime is tradeable. Returns
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

        # Liquid-hours window only (reuse session.window_start/end). The library's
        # late-session-drift rejection showed thin-hour spread (per-bar in the parquet) kills a
        # marginal edge; restrict arming to the liquid London + overlap block.
        lon_now = self._london(now)
        if not (self.win_start <= lon_now.time() < self.win_end):
            return NoSignal(now, "outside_session")

        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        if not is_narrow_range(highs, lows, self.nr_lookback):
            return NoSignal(now, "not_narrow_range")

        regime = self._regime(bars)
        # NR7 regime gate: a TRADEABLE volatility band only (NORMAL). Avoid the dead-LOW band
        # (a contraction with no expansion fuel) and the HIGH band (fixed-R sizing unsafe). The
        # incumbent's ER>=threshold trend requirement is deliberately NOT applied (opt-in).
        if regime.vol_state is not VolState.NORMAL:
            return NoSignal(now, "vol_state_not_normal")
        if self.require_trend and not (regime.er >= self.er_threshold):
            return NoSignal(now, "trend_gate_failed")

        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        nr_high = last.high
        nr_low = last.low
        buf = self.buffer_pips * self.pip
        long_level = nr_high + buf
        short_level = nr_low - buf

        # Gap guard (defence-in-depth): a buy_stop must rest ABOVE the market, a sell_stop BELOW.
        # The NR7 close is inside [nr_low, nr_high], so both legs normally arm; guard anyway.
        ref = last.close
        long_sig = (self._signal(Direction.LONG, long_level, nr_low, regime, now,
                                 context_bias, long_level, "stop")
                    if ref < long_level else None)
        short_sig = (self._signal(Direction.SHORT, short_level, nr_high, regime, now,
                                  context_bias, short_level, "stop")
                     if ref > short_level else None)
        if long_sig is None and short_sig is None:
            return NoSignal(now, "both_levels_through")

        # Fillable on the NEXT bar through bar i+entry_valid_bars; dropped by the harness once
        # ``now >= expire_utc``. now is the NR7 bar's open; +0.5 tf keeps the boundary clean.
        expire = now + timedelta(minutes=(self.entry_valid_bars + 0.5) * self.tf_min)
        return ArmSignal(instrument=self.config.get("instrument", "EURUSD"),
                         ts_decision_utc=now, long=long_sig, short=short_sig,
                         expire_utc=expire, regime=regime,
                         config_version=self.config_version)
