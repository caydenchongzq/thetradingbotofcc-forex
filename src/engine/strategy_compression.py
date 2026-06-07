"""SessionBreakoutERCompression — research-engine candidate (spec 08, 2026-06-07).

SessionBreakoutER + a Crabel-style PRE-SESSION volatility-compression entry filter:
only take the opening-range breakout when the London morning (the `recent_bars` M15
bars before the session window opens) was quiet relative to the immediately preceding
baseline. Rationale: contraction precedes expansion (Crabel's NR/ORB research) — a
quiet morning makes the afternoon range break more likely to be a genuine expansion.

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
- ENTRY-SIDE ONLY: subclasses the incumbent, overrides ``evaluate`` to add one extra
  rejection path. ``manage`` / exits are inherited unchanged, so no live-path mirror is
  needed (live == backtest preserved through the shared decision chain).
- PURE: the filter is a pure function of the injected ``bars``/``now`` — no clock,
  no network, no state. Every degraded path resolves to ``NoSignal`` (fail safe:
  ``compression_pct`` returns 1.0 on insufficient history, which blocks).
- The incumbent class is NOT modified; this strategy reaches live only via a
  human-approved ConfigStore promotion of a config whose ``name`` selects it.

Config (under ``compression:``, defaults chosen a priori from the cited sources —
deliberately NOT swept; the median cut is the single pre-registered threshold):
    recent_bars: 20     # ~5h London morning before the session window
    baseline_bars: 60   # the 60 single-bar TRs immediately preceding the morning
    max_pct: 0.50       # trade only if morning mean-TR <= median of baseline TRs
"""

from __future__ import annotations

from src.common.timeutil import ensure_utc

from .indicators import compression_pct
from .strategy import SessionBreakoutER
from .types import NoSignal


class SessionBreakoutERCompression(SessionBreakoutER):
    name = "SessionBreakoutERCompression"

    def __init__(self, config: dict):
        super().__init__(config)
        c = (config or {}).get("compression", {})
        self.cmp_recent_bars = int(c.get("recent_bars", 20))
        self.cmp_baseline_bars = int(c.get("baseline_bars", 60))
        self.cmp_max_pct = float(c.get("max_pct", 0.50))

    def warmup_bars(self) -> int:
        # Needs the morning window + baseline before the session opens.
        return max(super().warmup_bars(),
                   self.cmp_recent_bars + self.cmp_baseline_bars + 2)

    # ------------------------------------------------------------------
    def evaluate(self, bars, now_utc, context_bias, calendar=None):
        base = super().evaluate(bars, now_utc, context_bias, calendar)
        if isinstance(base, NoSignal):
            return base
        if not self._pre_session_compressed(bars, now_utc):
            return NoSignal(ensure_utc(now_utc), "pre_session_not_compressed")
        return base

    # ------------------------------------------------------------------
    def _pre_session_compressed(self, bars, now_utc) -> bool:
        """True iff the morning before TODAY's session window was quiet vs baseline.

        Uses only bars strictly before today's London ``window_start`` so the opening
        range / breakout bars never contaminate the measurement. Fail-safe: not enough
        pre-session history -> compression_pct = 1.0 -> blocked.
        """
        day = self._london(ensure_utc(now_utc)).date()
        pre = []
        for b in bars:
            lon = self._london(b.ts_open_utc)
            if lon.date() < day or (lon.date() == day and lon.time() < self.win_start):
                pre.append(b)
        pct = compression_pct([b.high for b in pre], [b.low for b in pre],
                              [b.close for b in pre],
                              self.cmp_recent_bars, self.cmp_baseline_bars)
        return pct <= self.cmp_max_pct
