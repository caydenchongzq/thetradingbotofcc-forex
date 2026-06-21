"""SessionBreakoutERFillAnchored — research-engine candidate (spec 08, 2026-06-21).

Hypothesis: the live-faithful MARKET-fill incumbent ``SessionBreakoutER`` is a ~break-even
loser (in-sample −0.080R; market-at-close −0.024R in [[2026-06-15-resting-stop-and-market-entry]])
in part because its exit geometry is ANCHORED TO THE LEVEL while the fill lands BEYOND the level.
On a long, the market fill is ABOVE ``range_high``; the single 1R target sits at
``level + sl_pips`` (CLOSER to the fill than a full 1R) and the stop at ``level − sl_pips``
(FARTHER). So the realised risk:reward measured FROM THE ACTUAL FILL is skewed sub-1:1 — a high
win rate paying less than 1R per win against a more-than-1R loss per loss. The 06-20
follow-through study ([[2026-06-20-followthrough-time-stop]]) fingered exactly this
fill-vs-anchor offset as the ROOT CAUSE of its anti-selection: "favourable progress is
non-monotonic early whenever the fill is offset from the risk anchor."

This candidate re-anchors the SAME exit machinery (same ``sl_pips`` magnitude, same single 1R
target, same regime/session/entry) to the FILL instead of the LEVEL, so the trade gets an honest
symmetric 1:1 from where it actually enters. Falsifiable claim: if the level-anchored skew is a
net drag (the closer target caps winners more than the high win rate compensates), fill-anchoring
lifts expectancy toward the gates; if the skew is in fact the only thing keeping the entry near
break-even (the reports' assertion), fill-anchoring makes it worse and the question is settled
with DATA rather than a reasoning assertion.

Why this is NOT a repeat of a closed/rejected result (spec 08 §4.3):
  * The "fill-anchoring symmetrises R:R and erases the skew" claim in
    [[2026-06-15-resting-stop-and-market-entry]] and [[2026-06-20-followthrough-time-stop]] was a
    REASONING dismissal, NEVER an A/B. The 06-15 A/B held "same SL/TP levels — only the FILL
    differs"; it varied the ENTRY fill (stop-at-level vs resting-touch vs market-at-close), not the
    exit ANCHOR. Fill-anchored exits have no trial in the ledger. The 06-15 report explicitly lists
    "Re-tune market-entry exits ... to fit the later fill" as candidate direction #1.
  * The exit-model rejections are 0/3 but each kept the LEVEL anchor and changed TARGET SHAPE or
    TIMING: scaled-runner [[2026-06-03-full-exit-model]] and ≥2R [[2026-06-07-tp-2r-sweep]] changed
    where/how much profit is taken; follow-through [[2026-06-20-followthrough-time-stop]] added a
    time/progress loser-exit. NONE changed the risk ANCHOR itself — the one lever the 06-20
    root-cause analysis points at. This tests whether the anchor (not the target tail, not the
    timing) is the defect, so the recorded failure modes (high-R tails don't pay; time-stop cuts
    winners) do not bind it.
  * It does NOT re-open the closed directional-breakout entry verdict — entry selection is the
    incumbent's, byte-for-byte (``evaluate`` inherited verbatim). It asks the narrow exit-geometry
    question only.

Live-fillability (invariant #3, spec 08 §5): entry is the incumbent's MARKET fill at the
confirmed close (live-placeable, no retcode 10015); the stop and 1R target are placed at
fixed pip offsets from that fill — ordinary SL/TP a live order carries. ``manage`` is the
incumbent's (break-even disabled at HEAD's ``move_be_after_r: null``), and already measures R
from the fill, so it is consistent with the fill anchor. ``live == backtest`` holds at both seams.
(If ever promoted, the new exit placement is produced inside ``evaluate`` — the same decision
chain live and backtest run — so no new ``manage`` branch needs mirroring; still subject to the
standard human-approved promotion. Dev backtest needs no mirror.)

Exit geometry (spec 08 §5.8 — pre-registered, with rationale):
  * Stop distance ``sl_pips = max(structural box, 1.2×ATR)`` — UNCHANGED MAGNITUDE from the
    incumbent (1.2×ATR carries no special status here; it is held fixed only so the A/B isolates
    the ONE variable — the anchor — rather than confounding stop width with anchor).
  * Stop PLACEMENT = ``fill − sl_pips`` (long) / ``fill + sl_pips`` (short): the stop sits a true
    1R below/above the actual entry, so a full stop-out is exactly −1R from the fill.
  * Target = single 1.0R from the FILL (``fill + sl_pips`` long), 100% out. R:R = 1:1 from the
    fill. Rationale: the incumbent mechanism is a high-base-rate continuation entry; a symmetric
    1R keeps the win-rate-driven expectancy but measures it honestly from the fill instead of
    granting the level-anchored sub-1R skew. (Reusing the single-1R machinery is justified here,
    not inherited by reflex: the test is precisely whether honest 1R beats skewed sub-1R.)

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses ``SessionBreakoutER`` for ALL shared PURE machinery; the incumbent class is NOT
    modified. Only ``_signal`` is overridden, to place SL/TP relative to the fill; ``evaluate``,
    ``manage``, ``warmup_bars`` and the regime/blackout helpers are inherited verbatim.
  * PURE function of (bars, now, context_bias, calendar): no clock, no network, no state. Every
    degraded path is the incumbent's own fail-safe ``NoSignal``.
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.
"""

from __future__ import annotations

from .strategy import SessionBreakoutER
from .types import Direction, ExitPlan, Signal


class SessionBreakoutERFillAnchored(SessionBreakoutER):
    """SessionBreakoutER with exits anchored to the FILL instead of the breakout level.

    Identical entry selection, regime gate, session and stop *magnitude* as the incumbent; the
    only change is that the initial stop and the 1R target are placed at ``sl_pips`` from the
    actual fill price rather than from the opening-range level. Additive subclass — the incumbent
    class and every shared helper are untouched.
    """

    name = "SessionBreakoutERFillAnchored"

    def _signal(self, direction, level, structure_stop, regime, now, bias,
                entry_price=None, entry_type="market") -> Signal:
        # Same fill as the incumbent (the confirmed close for a market entry).
        entry = level if entry_price is None else entry_price
        # Same stop-distance magnitude as the incumbent (isolate the anchor, not the width).
        struct_sl_pips = abs(level - structure_stop) / self.pip
        atr_sl_pips = self.atr_mult_sl * regime.atr_pips
        sl_pips = max(struct_sl_pips, atr_sl_pips)
        # FILL-ANCHORED placement: a full stop-out is exactly −1R from the fill, and each target
        # is a true r×R from the fill. (Incumbent anchors these to ``level`` instead.)
        if direction is Direction.LONG:
            sl_price = entry - sl_pips * self.pip
            targets = tuple(entry + r * sl_pips * self.pip for r in self.target_r)
        else:
            sl_price = entry + sl_pips * self.pip
            targets = tuple(entry - r * sl_pips * self.pip for r in self.target_r)
        plan = ExitPlan(initial_sl_price=sl_price, initial_sl_pips=sl_pips, targets=targets,
                        target_r_multiples=self.target_r, partial_fractions=self.partials,
                        move_be_after_r=self.move_be_after_r, trail=None)
        reason = ("range_close_break + ER>=thr + ATR_normal (market entry, fill-anchored exits)"
                  if entry_type == "market"
                  else "range_close_break + ER>=thr + ATR_normal (resting stop, fill-anchored exits)")
        return Signal(instrument=self.config.get("instrument", "EURUSD"),
                      ts_decision_utc=now, direction=direction, entry_type=entry_type,
                      entry_price=entry, exit_plan=plan, regime=regime,
                      session="london_ny_overlap", breakout_level=level,
                      entry_reason=reason, context_bias=bias,
                      config_version=self.config_version)
