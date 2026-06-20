---
id: 2026-06-20-followthrough-time-stop
name: SessionBreakoutERFollowThrough
family: exit-model
status: tested-rejected
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-03-full-exit-model, 2026-06-07-tp-2r-sweep, 2026-06-14-trend-aligned-orb, 2026-06-19-session-range-false-break-fade]
sources: ["https://www.tradesim.com/blog/day-trading-breakouts", "https://www.tradingsim.com/blog/day-trading-breakouts", "https://forextester.com/blog/breakout-trading-strategy/", "https://priceactionninja.com/false-breakout-strategy-for-forex-stop-hunts-liquidity-traps/", "https://www.strike.money/technical-analysis/breakout-trading"]
trials_used: 1
verdict: "ANTI-selective exit: a follow-through/time-stop failure exit on the market-fill incumbent REGRESSES it (−0.080R→−0.118R, win 57.6%→43.6%, PF 0.56→0.42, 1/7 WF folds, severe fold −0.313R, lockbox −0.067R/PF0.68 FAIL). The market entry sits ABOVE the level, so eventual winners routinely dip underwater before resuming to the close-anchored 1R target; 'underwater after N bars' scratches those winners, not the whipsaws. Exit-model family now 0/3 (scaled-runner, ≥2R, failure-timing)."
---

# SessionBreakoutERFollowThrough — scratch a breakout that shows no follow-through within ~1h

## Hypothesis & market rationale
The live-faithful MARKET-fill incumbent `SessionBreakoutER` is a near-break-even loser on the
current data (in-sample −0.080R here; the promoted HEAD's +0.391R is a non-live-placeable
level-fill artifact, [[2026-06-15-resting-stop-and-market-entry]]). Its losers are the false
breakouts: EURUSD's opening range breaks BOTH sides ~65% of the time
([[2026-06-19-session-range-false-break-fade]]), so a chunk of confirmed close-breaks are the
first half of a whipsaw that then walks to the far (1.2×ATR) stop for a full −1R.

Practitioner breakout literature is near-unanimous that a *real* breakout follows through
within the first 1–3 bars and that "momentum trades that don't work quickly rarely work at
all"; the standard remedy is a **failure / time stop** that *scratches* a trade with no
forward progress inside a short window, turning a future −1R into a small scratch BEFORE it
reaches the far stop. Falsifiable claim: if the slow-and-underwater breaks are
disproportionately the whipsaws (and the genuine winners have already reached the CLOSE 1R
target by then), scratching them lifts expectancy/PF without touching the winners — recovering
the ~0R market-fill base toward the gates.

**Result: the claim is false on EURUSD M15 — and inverted.** The failure exit made every
quality axis WORSE.

## Sources
Hypothesis-only (the backtester is the arbiter); re-implemented pure, no community code copied.
- TradingSim, *Day Trading Breakouts* — "scratch the trade if no follow-through within 1–2
  bars; momentum trades that don't work quickly rarely work at all"; "~60–70% of intraday
  breakouts fail on the first attempt." (https://www.tradingsim.com/blog/day-trading-breakouts)
- Forex Tester, *Breakout Trading Strategy* — time-based exits and "stand down after three
  whipsaws"; ATR-based stops. (https://forextester.com/blog/breakout-trading-strategy/)
- PriceActionNinja, *False Breakout Strategy* — false breaks as liquidity grabs that trap
  before the real move. (https://priceactionninja.com/false-breakout-strategy-for-forex-stop-hunts-liquidity-traps/)
- Strike.money, *Breakout Trading* — continuation/failure base rates.
  (https://www.strike.money/technical-analysis/breakout-trading)

## Relation to prior library work
- **NOT the exit-model rejections.** [[2026-06-03-full-exit-model]] (scaled 1R + ATR runner)
  and [[2026-06-07-tp-2r-sweep]] (pure ≥2R targets) changed TARGET GEOMETRY and were judged on
  the winners' tail. This changed neither target nor stop; it added a TIME/PROGRESS failure
  exit on the LOSER side — an orthogonal lever the library had not tested. (It is now tested,
  and also rejected — the exit-model family is 0/3.)
- **NOT a directional/volatility FILTER** ([[2026-06-14-trend-aligned-orb]], compression). Those
  were subtractive on ENTRIES and died on the 200-trade floor. This cuts ZERO entries (sample
  stayed at 225 ≈ incumbent 224 — sample_size PASS), changing only when a loser is closed.
- **Does NOT re-open the closed directional-breakout verdict.** It claims no new entry edge; it
  asks the narrower question of whether *managing the incumbent's losers* recovers the base.
- **Builds on [[2026-06-15-resting-stop-and-market-entry]]:** correctly A/B'd against the
  MARKET-fill incumbent (−0.080R here), not the level-fill artifact — the re-basing the INDEX
  caveat demands. The overlay is measured against a real live-fillable base.

## Strategy spec
- **Entry / stop / target — UNCHANGED from the incumbent** (inherited `evaluate` byte-for-byte):
  London/NY-overlap 30-min opening range, close-confirmation break, MARKET fill at the confirmed
  close; ER≥0.30 + ATR-normal regime gate; stop = `max(structural box, 1.2×ATR)`; single
  close-anchored 1.0R target. Geometry held fixed so the A/B isolates one variable.
- **Failure exit (the ONE new mechanism, in `manage`):** once a position has been held
  `time_stop_bars` closed bars AND its current favourable progress is below `min_progress_r`,
  close at MARKET on that bar's close; otherwise defer to the incumbent's unchanged break-even
  logic. Pre-registered, NOT swept: `time_stop_bars = 4` (≈1h of M15, a touch more lenient than
  the literature's 1–3 candles given M15 noise) and `min_progress_r = 0.0` (scratch only trades
  not in profit after the window). If promoted, `follow_through.time_stop_bars` /
  `follow_through.min_progress_r` become `ALLOWED_LEVERS`.
- **Live-fillability (invariant #3):** the only added action is a market close at a closed
  bar's close (modelled with spread like every other exit) — always live-placeable, no resting
  order, no look-ahead. `live == backtest` holds at the exit seam.

## Implementation notes
Additive only; incumbent class untouched.
- `src/engine/strategy_followthrough.py` — `SessionBreakoutERFollowThrough(SessionBreakoutER)`,
  overrides only `manage` (delegates to `super().manage` when not scratching).
- `src/engine/registry.py` — one `register("SessionBreakoutERFollowThrough", …)` line.
- `tests/engine/test_followthrough.py` (10 tests: evaluate-identity vs incumbent; scratch
  fires underwater long/short after the window; no scratch before the window or when in
  profit; disabled at `time_stop_bars=0`; fail-safe on missing `bars_held` / zero risk;
  `min_progress_r` threshold semantics) and `tests/backtest/test_followthrough_harness.py`
  (2 tests: the overlay scratches a stalled break via `manage_close` through the real harness;
  the incumbent holds the identical fixture). Full `pytest` green (no writes to `state/`, no
  live-path edits). Live-mirror needed before any (non-existent) promotion — flagged, moot on
  rejection.

## Backtest results
Command: `python3 scripts/run_backtest.py --strategy SessionBreakoutERFollowThrough
--walkforward --trials 169` (cumulative trial count 169; 59,993 M15 bars, 2024-01 → 2026-05).
A/B: `python3 scripts/run_backtest.py --strategy SessionBreakoutER --trials 169`.

| metric | gate | candidate | incumbent HEAD (market-fill) |
|---|---|---|---|
| expectancy_r | ≥ 0.10 | **−0.118** FAIL | −0.080 |
| profit_factor | ≥ 1.3 | **0.42** FAIL | 0.56 |
| sharpe (ann.) | ≥ 1.0 | **−2.67** FAIL | −2.00 |
| sortino | ≥ 1.5 | **−2.87** FAIL | −2.21 |
| sample_size | ≥ 200 | 225 PASS | 224 |
| deflated_sharpe | ≥ 0.95 | **0.000** FAIL | 0.000 |
| ftmo_no_breach | 0 | 0 PASS (hard) | 0 |
| win_rate | — | 43.6% | 57.6% |
| maxDD | — | $9,496 | $9,370 |

Walk-forward: **1/7** folds profitable (weak=6), min fold **−0.313R** (severe), stitched OOS
−0.136R ≈ in-sample (no collapse, but a stably adverse edge). **Lockbox** 2025-11→2026-05:
60 trades, −0.067R, PF 0.68, Sharpe −1.49 → **FAIL**. WALK-FORWARD VERDICT: FAIL.

## Verdict
**tested-rejected — fails 6/7 in-sample gates and the full walk-forward + lockbox, and REGRESSES
the incumbent on every quality axis** (expectancy −0.038R, win rate −14.0pp, PF −0.14, Sharpe
−0.67, Sortino −0.66, maxDD +$126). The failure exit does not cut whipsaws; it cuts winners.
No proposal filed (promotion requires ALL gates to pass). Trial #169 consumed.

## Lessons
1. **The follow-through/time-stop exit is ANTI-selective on this entry — and the cause is the
   fill offset.** The market entry fills at the confirmed close, which is ABOVE the long level
   / BELOW the short level, while the 1R target is anchored to the LEVEL (closer) and the stop
   to `1.2×ATR` from the level (farther). So a genuine winner frequently pulls back THROUGH the
   fill toward the level before resuming to the close target — it is *underwater relative to the
   fill* for the first several bars by construction. "Underwater after N bars" therefore selects
   against the normal pullback-then-resume winners (win rate collapses 57.6%→43.6%), not against
   the whipsaws. Favourable progress is **non-monotonic early whenever the fill is offset from
   the risk anchor** — a progress/time filter that assumes "good trades show profit fast" is
   mis-specified for exactly this geometry.
2. **Exit-model family now 0/3.** Target-geometry (scaled-runner [[2026-06-03-full-exit-model]],
   ≥2R [[2026-06-07-tp-2r-sweep]]) and now failure-timing all fail on EURUSD M15. A management
   overlay cannot manufacture an edge the ENTRY does not have: the incumbent's market-fill base
   is a −0.08R loser, and reshaping when its losers close only moves loss around (here, onto the
   winners). This is the EXIT-side analogue of the entry-side "double-jeopardy" of breakout
   timing subsets ([[2026-06-11-breakout-retest]]).
3. **Re-basing on the market-fill incumbent was done correctly and matters.** The A/B used the
   live-fillable −0.080R base (per the INDEX caveat), so the −0.038R regression is a real
   live-faithful result, not an artifact subset. It also confirms the incumbent itself remains
   an in-sample loser under live fills — reinforcing that the open lever is wider data, not more
   management tweaks on this entry.
4. **Process:** an overlay's a-priori case should be stress-tested against the strategy's own
   fill geometry, not just generic breakout lore. A cheap pre-check here would have been "is the
   incumbent's MFE-before-MAE ordering consistent with 'winners show profit fast'?" — it is not,
   because of the offset fill. Worth a parquet probe before the next progress/time-based exit.

## Next steps
- **Do not test further progress/time-based failure exits on SessionBreakoutER** without first
  changing the fill/anchor relationship (e.g. anchoring exits to the FILL, which
  [[2026-06-15-resting-stop-and-market-entry]] showed symmetrises R:R and erases the skew — a
  separate rejected direction). The two are coupled: you cannot keep the favourable skew AND
  use early progress as a signal.
- Exit-model family is effectively closed on this entry (0/3). Management/exit research should
  pause until there is a base entry with a genuine live edge.
- The standing lever is unchanged: **longer history / a second instrument** (spec 08 §8). The
  M5 frequency review (~2026-06-21) is the moment to weigh cutting cadence vs widening data.
- Queue note: a "scratch only on a confirmed structural rejection" (e.g. a bar that CLOSES back
  inside the opening range) is a *structure* signal, not a *time/progress* signal, so it is not
  excluded by this lesson — but it overlaps the rejected failed-break fade
  ([[2026-06-19-session-range-false-break-fade]]) read from the long side; probe the
  close-back-inside conditional outcome before spending a trial.
