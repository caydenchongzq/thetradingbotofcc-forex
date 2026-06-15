"""LondonOpenBreakoutER — research-engine candidate (spec 08, 2026-06-15).

Hypothesis: the incumbent ``SessionBreakoutER`` trades exactly ONE window — the London/NY
overlap (13:00–16:00 London), a peak-liquidity *continuation* regime. The **London open**
(~08:00 London) is a structurally different and, in the practitioner literature, the single
most consistent breakout window in FX: ~35–40% of daily turnover enters at the London open,
and the session opens against a compressed overnight (Asian) range, so the first directional
expansion is an *initiation* move, not a mid-trend continuation. Falsifiable claim: the same
opening-range-breakout edge the incumbent harvests at the overlap also exists at the London
open, and because the London-open window is a DIFFERENT time of day it produces an INDEPENDENT
trade stream — not a subset of the incumbent's ~224 trades.

Why this matters for the library's recurring failure mode: every subtractive filter tried so
far ([[2026-06-14-trend-aligned-orb]], [[2026-06-07-pre-session-compression-filter]]) died on
the 200-trade hard floor because the incumbent base is only ~224 (24 above the floor). This
candidate is NOT subtractive — it does not touch the incumbent's trades; it generates its OWN
base from a different session, so it is bounded by its own trade count, not the incumbent's
24-trade headroom. (cf. the additive-but-same-session [[2026-06-13-second-entry-orb]], which
DILUTED the incumbent's expectancy; this stands ALONE on its own gates.)

Entry / fill (CLAUDE.md invariant #3 — live-fillable): inherits ``SessionBreakoutER.evaluate``
byte-for-byte, i.e. the RESTING_STOP_FIX close-confirmation + **market** entry (fill ≈ the
confirmed close). It therefore inherits the fix that exposed the incumbent's level-fill
artifact — so this candidate is tested LIVE-FAITHFULLY from day one (no phantom level-fill
edge possible). The ONLY thing that differs from the incumbent is the session window.

Exit geometry (spec 08 §5.8 — pre-registered, deliberately the incumbent's, WITH rationale,
not an unexamined inheritance):
  * Stop = ``max(structural box, atr_mult_sl×ATR)`` — UNCHANGED. The entry is the same
    range-break momentum structure as the incumbent; the stop the *structure* implies (opposite
    end of the opening range, floored at the ATR multiple so a tight range does not noise-out
    the trade) is the geometry this mechanism implies.
  * Target = single 1.0R (R:R 1:1) — UNCHANGED, and a ≥2R variant is PRE-CLOSED: the incumbent
    exit record (the ≥2R sweep [[2026-06-07-tp-2r-sweep]], all 18 failed DSR+lockbox; the
    scaled-runner [[2026-06-03-full-exit-model]], rejected) establishes that this exact breakout
    mechanism on EURUSD M15 rewards a high-win-rate ~1R structure and punishes high-R targets.
    Same mechanism ⇒ that finding transfers a priori; a 2R London variant would share the
    recorded failure mode (§4.3) absent a new differentiator. 1R is justified by
    mechanism-equivalence, NOT inherited by reflex.
  * ``manage`` (break-even after 1R when configured) is byte-for-byte the incumbent's ⇒ NO new
    manage semantic, NO live-mirror session required; only the session config differs.

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses ``SessionBreakoutER`` for ALL machinery. The incumbent class is NOT modified;
    only ``__init__`` is extended to FORCE the London-open window so a ``--strategy`` run keeps
    HEAD's regime/exit levers while isolating exactly one variable (the session). A standalone
    ``--config-file`` may still tune via the ``london_open`` block below.
  * PURE function of (bars, now, context_bias, calendar): inherits every degraded-path NoSignal.
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``london_open:``; chosen a priori, deliberately NOT swept):
    window_start: "08:00"          # London open
    window_end:   "11:00"          # 3-hour span, mirrors the incumbent's 3-hour overlap window
    opening_range_minutes: 30      # range = 08:00–08:30
"""

from __future__ import annotations

from .strategy import SessionBreakoutER, _t


class LondonOpenBreakoutER(SessionBreakoutER):
    """SessionBreakoutER applied to the London-open session (additive subclass)."""

    name = "LondonOpenBreakoutER"

    def __init__(self, config: dict):
        super().__init__(config)
        # Force the London-open window regardless of the inherited HEAD `session` block, so
        # `--strategy LondonOpenBreakoutER` keeps HEAD's regime/exit params but isolates the
        # SESSION variable. Tunable via a dedicated `london_open` config block (so it never
        # clashes with the incumbent's `session` levers).
        lo = (self.config.get("london_open") or {})
        self.win_start = _t(lo.get("window_start", "08:00"))
        self.win_end = _t(lo.get("window_end", "11:00"))
        self.or_minutes = int(lo.get("opening_range_minutes", 30))
