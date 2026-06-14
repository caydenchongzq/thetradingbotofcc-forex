"""TrendAlignedORB — research-engine candidate (spec 08, 2026-06-14).

Hypothesis: the incumbent ``SessionBreakoutER`` takes the London/NY-overlap opening-range
breakout in EITHER direction whenever its ER/ATR regime gate passes — it never asks whether
the break runs WITH or AGAINST the prevailing multi-day drift. Practitioner ORB literature is
near-unanimous that breakouts *aligned with the higher-timeframe trend* follow through more
reliably, while counter-trend breakouts are a larger share of the false breaks that snap back
into the range. If that holds on EURUSD M15, the incumbent's losers are disproportionately
counter-trend breaks, and skipping them should RAISE win rate / PF / risk-adjusted return —
the only way to actually *beat* (not merely match) a strong incumbent (cf. the additive but
dominated [[2026-06-13-second-entry-orb]]).

This candidate is a STRICTLY SUBTRACTIVE directional FILTER. It changes nothing about entry
price, stop, target, or ``manage`` — it only *vetoes* an incumbent signal whose direction
disagrees with a slow-EMA trend computed PURELY from the M15 closes. Mechanically it calls
``super().evaluate(...)`` and passes the result through unchanged unless the signal's direction
is mis-aligned with the trend, in which case it returns ``NoSignal``. So every trade it takes
is byte-for-byte an incumbent trade; it can only ever take a SUBSET of them. The A/B therefore
isolates exactly one variable: the trend-alignment veto.

Why this is NOT a repeat of a closed/rejected entry (spec 08 §4.3):
  * The trend family rejections ([[2026-06-09-late-session-drift]], IntradayTSMomentum,
    [[2026-06-12-trend-pullback-ema]]) all failed because their *entry* was a low-win-rate
    trend mechanism. TrendAlignedORB introduces NO new entry — it reuses the incumbent's
    73%-win 1R break verbatim. The recorded failure mode (selectivity of a weak entry) cannot
    apply: there is no new entry to be weak.
  * It is not the compression filter ([[2026-06-07-pre-session-compression-filter]]): that was
    a *volatility-timing* veto that went degenerate (3 trades). This is a *directional* veto on
    a different axis; it cuts at most the counter-trend share of an already-large trade base.

Acknowledged risk (the arbiter settles it): like every subtractive filter, this can be
ANTI-selective (the overlap is so directional that counter-drift breaks are fine, so we'd be
discarding winners — cf. [[2026-06-11-breakout-retest]]) and it can push trade count toward the
200 floor. Both are exactly what the gates + walk-forward + lockbox decide.

Exit geometry (spec 08 §5.8 — pre-registered; deliberately the incumbent's, with rationale,
NOT an unexamined inheritance):
  * Stop = ``max(structural box, 1.2xATR)`` — UNCHANGED. The filter does not alter the breakout
    mechanism, only which breaks are taken; the surviving trades are the incumbent's own
    breaks, so their validated stop is exactly right.
  * Target = single 1.0R, 100% out (R:R 1:1) — UNCHANGED. The surviving trades are the
    incumbent's high-win-rate ~1R breakouts; the library has twice reconfirmed that EURUSD M15
    overlap rewards high-win-rate ~1R structures and punishes high-R ones
    ([[2026-06-07-tp-2r-sweep]], [[2026-06-12-trend-pullback-ema]]). Changing R here would
    confound the filter's effect with an exit change.
  * Rationale: to measure a FILTER you must hold geometry fixed. Reusing the incumbent's exact
    machinery is what makes the A/B a clean one-variable test.
  * Because ``manage`` and the exit plan are byte-for-byte the incumbent's, this candidate
    introduces NO new manage semantic and needs NO live-mirror session: ``live == backtest``
    already holds for the exit path; only ``evaluate`` adds a veto.

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses ``SessionBreakoutER`` for ALL shared PURE machinery. The incumbent class is NOT
    modified; only ``evaluate`` / ``warmup_bars`` are overridden, and ``evaluate`` delegates the
    entire entry decision to ``super().evaluate`` (no logic is duplicated, so it cannot drift).
  * PURE function of (bars, now, context_bias, calendar): no clock, no network, no state. Every
    degraded path inherited from the incumbent stays ``NoSignal``; the added veto only ever
    turns a Signal into ``NoSignal`` (fail safe — never the reverse).
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``trend_filter:``; chosen a priori, deliberately NOT swept):
    ema_window: 96      # ~1 trading day of M15 bars -> a "daily trend" proxy
    slope_lookback: 16  # ~4 hours -> slope must be non-flat in the trade direction
"""

from __future__ import annotations

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias  # noqa: F401  (kept for signature parity / readability)

from .indicators import ema_slope_sign
from .strategy import SessionBreakoutER
from .types import Direction, NoSignal, Signal


class TrendAlignedORB(SessionBreakoutER):
    """SessionBreakoutER + a higher-timeframe trend-alignment veto (additive subclass)."""

    name = "TrendAlignedORB"

    def __init__(self, config: dict):
        super().__init__(config)
        t = (self.config.get("trend_filter") or {})
        self.trend_ema_window = int(t.get("ema_window", 96))
        self.trend_slope_lookback = int(t.get("slope_lookback", 16))

    def warmup_bars(self) -> int:
        # Need enough history for the slow EMA slope on top of the incumbent's warmup.
        return max(super().warmup_bars(),
                   self.trend_ema_window + self.trend_slope_lookback + 2)

    def _trend_sign(self, bars) -> int:
        """+1 up / -1 down / 0 unconfirmed — slope of EMA(ema_window) over slope_lookback."""
        closes = [b.close for b in bars]
        return ema_slope_sign(closes, self.trend_ema_window, self.trend_slope_lookback)

    def evaluate(self, bars, now_utc, context_bias, calendar=None):
        sig = super().evaluate(bars, now_utc, context_bias, calendar)
        if not isinstance(sig, Signal):
            return sig  # pass through every incumbent NoSignal unchanged
        trend = self._trend_sign(bars)
        want = 1 if sig.direction is Direction.LONG else -1
        if trend == 0:
            return NoSignal(ensure_utc(now_utc), "trend_unconfirmed")
        if trend != want:
            return NoSignal(ensure_utc(now_utc), "trend_misaligned")
        return sig  # aligned -> the incumbent signal, byte-for-byte
