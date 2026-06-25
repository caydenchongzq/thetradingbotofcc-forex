"""SessionBreakoutERStructuralExit — research-engine candidate (spec 08, 2026-06-25).

Hypothesis:
  A bar that CLOSES back inside the opening range after an incumbent market-fill entry is a
  STRUCTURAL REJECTION signal — the breakout has definitively failed to hold the level — and
  scratching the trade at that point is SELECTIVE (cuts confirmed losers, not winners).

Pre-registered probe result (2026-06-25, scripts/probe_structural_rejection_exit.py):
  224 incumbent market-fill trades; 87 (38.8%) had ≥1 close-back-inside bar:
    With rejection:  mean R = −0.386R, win 42.5% (50 SL, 37 TP)
    No rejection:    mean R = +0.114R, win 67.2% (10 SL, 127 TP)
    Delta R = −0.501R  (pre-registered threshold ≤−0.15R → WORTH A TRIAL)
  Rejection-bar timing: median bar 3, mean 4.2, min 2 (bars from entry).

Mechanism:
  Inherits ALL of SessionBreakoutER (entry selection, ER/ATR regime gate, market fill,
  break-even management). The ONLY addition is in manage():
    LONG:  if current bar's close < or_high  → ManageDecision("close_all")
    SHORT: if current bar's close > or_low   → ManageDecision("close_all")
  where or_high / or_low are the opening-range bounds computed from the bars history.

This is ADDITIVE management (zero entries cut → 224-trade base preserved, no 200-floor
risk). It is IMMUNE to the fill-offset anti-selection that killed SessionBreakoutERFollowThrough
(2026-06-20): that strategy scratched when "underwater by N bars" — but since fill is above
OR_high, winners are technically underwater early. This strategy scratches on a price-action
event (close below OR_high), which winners NEVER trigger (they hold above OR_high after entry).

Exit geometry (spec 08 §5.8 — unchanged from incumbent; ADDITIVE on management only):
  stop:   1× original sl_pips below OR level (incumbent, unchanged)
  target: 1R (incumbent, unchanged)
  Justification: the structural exit REPLACES the stop for trades that fail; geometry is
  inherited not from habit but because we are testing the MANAGEMENT change only. If the
  geometry were also changed we could not isolate the structural-rejection hypothesis.

Live-mirror note: the manage() logic here is new; it will need to be mirrored into
run.py/_manage + decide_manage before promotion (CLAUDE.md invariant #3 / spec 08 §5.4).
Flag this in the report if all gates pass.

Dev-only: registered as "SessionBreakoutERStructuralExit"; never promoted here.
"""
from __future__ import annotations

from datetime import timedelta, time

from .strategy import ManageDecision, SessionBreakoutER


class SessionBreakoutERStructuralExit(SessionBreakoutER):
    """SessionBreakoutER + structural-rejection (close-back-inside-OR) exit (additive)."""

    name = "SessionBreakoutERStructuralExit"

    def manage(self, open_trade, bars, now_utc) -> ManageDecision:
        """Scratch trade if the current bar closes back inside the opening range.

        OR bounds are reconstructed from the bars history for the current London date and
        the configured or_minutes window — no new state, fully deterministic.
        """
        if not bars:
            return super().manage(open_trade, bars, now_utc)

        current_bar = bars[-1]

        # ── Reconstruct OR bounds from history ────────────────────────────────
        now_london = now_utc.astimezone(self.tz)
        today_london = now_london.date()

        # OR window: [win_start, win_start + or_minutes)
        or_end_dt = (
            now_london.replace(
                hour=self.win_start.hour,
                minute=self.win_start.minute,
                second=0,
                microsecond=0,
            )
            + timedelta(minutes=self.or_minutes)
        )
        or_end_time = or_end_dt.time()

        or_highs: list[float] = []
        or_lows: list[float] = []
        for bar in bars:
            bar_london = bar.ts_open_utc.astimezone(self.tz)
            if bar_london.date() != today_london:
                continue
            t = bar_london.time()
            if self.win_start <= t < or_end_time:
                or_highs.append(bar.high)
                or_lows.append(bar.low)

        if not or_highs:
            # OR not reconstructable from current history window (should not happen in
            # normal session flow; fail safe = hold, let existing SL/TP manage)
            return super().manage(open_trade, bars, now_utc)

        or_high = max(or_highs)
        or_low = min(or_lows)

        # ── Structural rejection check ─────────────────────────────────────────
        close = current_bar.close
        if open_trade.direction == "long" and close < or_high:
            return ManageDecision("close_all")
        if open_trade.direction == "short" and close > or_low:
            return ManageDecision("close_all")

        # No rejection — delegate to incumbent's break-even management
        return super().manage(open_trade, bars, now_utc)
