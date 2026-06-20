"""SessionBreakoutERFollowThrough — research-engine candidate (spec 08, 2026-06-20).

Hypothesis: the live-faithful MARKET-fill incumbent ``SessionBreakoutER`` is ~break-even
(market-at-close base −0.024R, [[2026-06-15-resting-stop-and-market-entry]]) because it pays
for the opening range's whipsaws — EURUSD's OR breaks BOTH sides ~65% of the time
([[2026-06-19-session-range-false-break-fade]]), so a chunk of confirmed close-breaks are the
first half of a whipsaw that then reverses to the FAR (1.2×ATR) stop for a full −1R. The
practitioner breakout literature is near-unanimous that a *real* breakout follows through
within the first 1–3 bars, and "momentum trades that don't work quickly rarely work at all":
the standard remedy is a FAILURE / TIME stop that *scratches* a trade which has not made
forward progress inside a short window, converting a future −1R into a small scratch — BEFORE
it walks to the far stop. If the slow-and-underwater breaks are disproportionately the
whipsaws (and the fast winners have already hit the CLOSE 1R target by then), scratching them
should lift expectancy/PF without touching the winners.

This candidate is therefore a pure EXIT/management overlay. It changes NOTHING about entry
(byte-for-byte the incumbent's market-fill, close-confirmation break), the initial stop, or the
target. It only adds ONE deterministic close hook in ``manage``: once a position has been held
``time_stop_bars`` closed bars and its *current* favourable progress is below
``min_progress_r``, close at market on that bar's close. It can only ever exit an
already-open incumbent trade EARLIER than its stop would — it can never open a trade, move a
target, or change a fill. The A/B vs HEAD therefore isolates exactly one variable: the
follow-through failure exit.

Why this is NOT a repeat of a closed/rejected entry or exit (spec 08 §4.3):
  * It is NOT the exit-model rejections. [[2026-06-03-full-exit-model]] (scaled 1R + ATR
    runner) and [[2026-06-07-tp-2r-sweep]] (pure ≥2R targets) both changed TARGET GEOMETRY
    (where/how much to take profit) and were judged on the winners' tail. This changes neither
    target nor stop; it adds a TIME/PROGRESS failure exit on the LOSER side — an orthogonal
    lever the library has never tested. The recorded failure mode there (high-R tails don't pay
    on EURUSD M15) cannot apply: the target stays a single close-anchored 1R.
  * It is NOT a directional/volatility FILTER ([[2026-06-14-trend-aligned-orb]],
    compression). Those were SUBTRACTIVE on ENTRIES and died on the 200-trade floor (cutting
    the 224 base below 200). This cuts ZERO entries — every incumbent break is still taken — so
    the trade count is held at the incumbent's ~224 and the sample_size gate is structurally
    safe. The only thing it changes is when a loser is closed.
  * It does NOT re-open the closed directional-breakout family verdict
    ([[2026-06-15-resting-stop-and-market-entry]], [[2026-06-18-nr7-volatility-breakout]]).
    Those proved the breakout ENTRY has no live edge standalone; this does not claim a new
    entry edge — it asks the narrower, untested question of whether *managing the known
    incumbent's losers* recovers the ~0R market-fill base toward the gates.

Live-fillability (invariant #3, spec 08 §5): the only added action is a MARKET close at a
closed-bar's close price (modelled exactly like the incumbent's other exits, with spread). A
market exit is always live-placeable — there is no resting order, no level fill, no
look-ahead. ``manage`` runs at bar close on the same closed bar the live loop would, so
``live == backtest`` holds at the exit seam. (If promoted this still needs the standard
live-mirror confirmation of the new ``manage`` branch in ``decide_manage`` + ``run._manage``;
flagged in the report. Dev backtest needs no mirror.)

Exit geometry (spec 08 §5.8 — pre-registered, deliberately the incumbent's, with rationale):
  * Stop = ``max(structural box, 1.2×ATR)`` — UNCHANGED. The overlay measures the failure exit
    in units of THIS stop (R = |entry − initial SL|); altering the stop would confound the test.
  * Target = single 1.0R (close-anchored), 100% out — UNCHANGED, same reason; the whole point
    is that the fast winners reach this close target before the time window elapses.
  * Failure exit (the ONE new param set, chosen a priori, NOT swept — a sweep would count every
    combo into DSR): ``time_stop_bars = 4`` (≈1 hour of M15 — a touch more lenient than the
    literature's 1–3 candles, since EURUSD M15 is noisier and we don't want to scratch a winner
    still building) and ``min_progress_r = 0.0`` (scratch only trades that are NOT in profit
    after the window — the cleanest "no follow-through" definition; a winner is by then already
    out at TP). If promoted these two become ``ALLOWED_LEVERS`` (``follow_through.*``).

Structural properties (dev-isolation, CLAUDE.md + spec 08 §5):
  * Subclasses ``SessionBreakoutER`` for ALL shared PURE machinery; the incumbent class is NOT
    modified. Only ``manage`` is overridden, and it DELEGATES to ``super().manage`` for the
    unchanged break-even logic — the failure exit is a strict pre-check that can only add a
    close. ``evaluate``/``warmup_bars`` are inherited verbatim.
  * PURE function of (open_trade view, bars, now): no clock, no network, no state. Every
    degraded path is fail-safe — a missing ``bars_held``/zero risk/empty bars yields the
    incumbent's own decision (never a spurious close).
  * Reaches live ONLY via a human-approved ConfigStore promotion of a config naming it.

Config (under ``follow_through:``):
    time_stop_bars: 4     # closed bars held before the progress check arms (0 disables)
    min_progress_r: 0.0   # scratch if current favourable R is below this at/after the window
"""

from __future__ import annotations

from .strategy import ManageDecision, SessionBreakoutER


class SessionBreakoutERFollowThrough(SessionBreakoutER):
    """SessionBreakoutER + a follow-through failure (time/progress) exit (additive subclass)."""

    name = "SessionBreakoutERFollowThrough"

    def __init__(self, config: dict):
        super().__init__(config)
        ft = (self.config.get("follow_through") or {})
        self.ft_time_stop_bars = int(ft.get("time_stop_bars", 4))
        self.ft_min_progress_r = float(ft.get("min_progress_r", 0.0))

    def manage(self, open_trade, bars, now_utc) -> ManageDecision:
        # Follow-through failure exit (additive close hook). Only ever fires on a position that
        # the incumbent would otherwise still be holding; can never open/alter a trade.
        if self.ft_time_stop_bars > 0 and bars:
            bars_held = getattr(open_trade, "bars_held", None)
            if bars_held is not None and bars_held >= self.ft_time_stop_bars:
                entry = open_trade.entry_price
                sl = open_trade.sl_price
                risk = abs(entry - sl)
                if risk > 0:
                    price = bars[-1].close
                    if open_trade.direction == "long":
                        cur_r = (price - entry) / risk
                    else:
                        cur_r = (entry - price) / risk
                    if cur_r < self.ft_min_progress_r:
                        return ManageDecision("close_all")
        # Otherwise defer to the incumbent's unchanged break-even management.
        return super().manage(open_trade, bars, now_utc)
