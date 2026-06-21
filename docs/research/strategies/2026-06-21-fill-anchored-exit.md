---
id: 2026-06-21-fill-anchored-exit
name: SessionBreakoutERFillAnchored
family: exit-model
status: tested-rejected
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-20-followthrough-time-stop, 2026-06-03-full-exit-model, 2026-06-07-tp-2r-sweep, 2026-06-02-session-breakout-er]
sources: ["https://www.tradinformed.com/backtesting-eurusd-trading-strategy-using-atr-trailing-stop/", "https://strategyquant.com/blog/the-atr-trailing-stops-indicator-when-and-how-to-use-it-for-effective-trading/", "https://www.quantifiedstrategies.com/average-true-range-trading-strategy/", "docs/research/strategies/2026-06-15-resting-stop-and-market-entry.md", "docs/research/strategies/2026-06-20-followthrough-time-stop.md"]
trials_used: 1
verdict: "Anchoring exits to the FILL instead of the breakout LEVEL REGRESSES the market-fill incumbent's expectancy (−0.080R→−0.127R, win 57.6%→51.6%) while improving dispersion (PF 0.56→0.76, Sharpe −2.00→−1.24, maxDD −$679). Symmetrising R:R to a true 1:1 trades away the level-anchored high-win-rate sub-1R skew, and that skew was net-beneficial — so fill-anchoring does NOT rescue the entry: still 6/7 in-sample gates FAIL, 2/7 WF folds, severe fold −0.355R, lockbox −0.221R/PF0.59 FAIL. Settles with DATA the library's prior reasoning-only claim that fill-anchoring 'erases the skew'. Exit-model now 0/4; the anchor is not the defect — the entry has no live edge."
---

# SessionBreakoutERFillAnchored — anchor the exits to the FILL, not the breakout level

## Hypothesis & market rationale
The live-faithful MARKET-fill incumbent `SessionBreakoutER` is a ~break-even loser on the
current data (in-sample −0.080R; market-at-close −0.024R in
[[2026-06-15-resting-stop-and-market-entry]]). Its exit geometry is anchored to the breakout
**level**: on a long, the stop sits at `level − sl_pips` and the single 1R target at
`level + sl_pips`. But the market fill lands ABOVE `level` (the confirmed close beyond the
range edge), so measured **from the actual fill** the target is CLOSER than 1R and the stop
FARTHER — a sub-1:1 skew that produces a high win rate paying less than 1R per win against a
more-than-1R loss per loss.

The 06-20 follow-through study ([[2026-06-20-followthrough-time-stop]]) identified exactly this
fill-vs-anchor offset as the ROOT CAUSE of its anti-selection ("favourable progress is
non-monotonic early whenever the fill is offset from the risk anchor"). Both that report and
[[2026-06-15-resting-stop-and-market-entry]] then *asserted* — without ever backtesting it —
that anchoring exits to the fill "symmetrises R:R and erases the skew" and is therefore a
losing direction. **Falsifiable claim tested here:** if the level-anchored skew is a net drag
(the closer target caps winners more than the high win rate compensates), re-anchoring the same
exit machinery to the fill lifts expectancy toward the gates; if instead the skew is what keeps
the entry near break-even, fill-anchoring makes it worse and the open question is settled with
data rather than an assertion.

**Result: the assertion was right — and now it is measured.** Fill-anchoring lowers expectancy.

## Sources
Hypothesis-only (the backtester is the arbiter); re-implemented pure, no community code copied.
- Tradinformed, *Backtesting a EUR/USD Trading Strategy Using an ATR Trailing Stop* — exit
  placement (fixed vs ATR-relative-to-fill) materially changes the win-rate/payoff trade-off.
  (https://www.tradinformed.com/backtesting-eurusd-trading-strategy-using-atr-trailing-stop/)
- StrategyQuant, *The ATR Trailing Stops Indicator* — stop/target distance measured from the
  entry vs from a structural level changes realised R:R.
  (https://strategyquant.com/blog/the-atr-trailing-stops-indicator-when-and-how-to-use-it-for-effective-trading/)
- QuantifiedStrategies, *Average True Range Trading Strategy* — ATR-multiple exits anchored to
  the fill; backtest evidence that anchor/multiple choice flips win-rate vs payoff.
  (https://www.quantifiedstrategies.com/average-true-range-trading-strategy/)
- In-house: [[2026-06-15-resting-stop-and-market-entry]] (the −0.080R/−0.024R market-fill base
  and the un-tested "erases the skew" claim) and [[2026-06-20-followthrough-time-stop]] (the
  root-cause diagnosis of the fill-vs-anchor offset).

## Relation to prior library work
- **Settles an explicitly-untested claim, so it is NOT a forbidden re-test (spec 08 §4.3).**
  The "fill-anchoring erases the skew → losing" conclusion in
  [[2026-06-15-resting-stop-and-market-entry]] and [[2026-06-20-followthrough-time-stop]] was a
  REASONING dismissal, never an A/B. The 06-15 A/B held "same SL/TP levels — only the FILL
  differs"; it varied the ENTRY fill (stop-at-level vs resting-touch vs market-at-close), not
  the exit ANCHOR. Fill-anchored exits had no trial in the ledger. The 06-15 report itself lists
  "Re-tune market-entry exits … to fit the later fill" as candidate direction #1.
- **NOT the closed exit-model rejections' failure mode.** Scaled-runner
  [[2026-06-03-full-exit-model]] and ≥2R [[2026-06-07-tp-2r-sweep]] changed the TARGET TAIL
  (high-R targets don't pay on EURUSD M15); follow-through [[2026-06-20-followthrough-time-stop]]
  added a TIME/PROGRESS loser-exit. NONE changed the risk ANCHOR — the lever the 06-20 root
  cause points at. This isolates the anchor (stop-distance magnitude and the single 1R target
  held identical), so those failure modes cannot bind it a priori.
- **Does NOT re-open the closed directional-breakout entry verdict.** Entry selection is the
  incumbent's, byte-for-byte (`evaluate` inherited; unit-tested identical). Narrow exit-geometry
  question only.
- **Correctly A/B'd against the live-fillable market-fill incumbent** (−0.080R), per the INDEX
  re-basing caveat — not the level-fill +0.391R artifact ([[2026-06-02-session-breakout-er]]).

## Strategy spec
- **Entry / regime / session — UNCHANGED from the incumbent** (`evaluate` inherited verbatim):
  London/NY-overlap 30-min opening range, close-confirmation break, MARKET fill at the confirmed
  close; ER≥0.32 + ATR-normal regime gate (HEAD v4 params).
- **Exit geometry (spec 08 §5.8 — pre-registered):**
  - Stop distance `sl_pips = max(structural box, 1.2×ATR)` — UNCHANGED MAGNITUDE (held fixed only
    so the A/B isolates the anchor, not the stop width; 1.2×ATR carries no special status).
  - Stop PLACEMENT = `fill − sl_pips` (long) / `fill + sl_pips` (short): a full stop-out is
    exactly −1R from the actual fill.
  - Target = single 1.0R from the FILL, 100% out → R:R = 1:1 from the fill. Rationale: the
    incumbent mechanism is a high-base-rate continuation entry; a symmetric 1R measures its
    win-rate-driven expectancy HONESTLY from the fill instead of granting the level-anchored
    sub-1R skew. (Reusing the single-1R machinery is justified, not reflexive: the test is
    precisely whether honest 1R beats skewed sub-1R.)
- If ever promoted, the anchor choice would be a fixed property of the class (not a lever).

## Implementation notes
Additive only; incumbent class untouched.
- `src/engine/strategy_fill_anchored.py` — `SessionBreakoutERFillAnchored(SessionBreakoutER)`,
  overrides only `_signal` to place SL/TP at `sl_pips` from the fill; `evaluate`, `manage`,
  `warmup_bars` and the regime/blackout helpers inherited verbatim. Pure; every degraded path is
  the incumbent's own fail-safe `NoSignal`.
- `src/engine/registry.py` — one `register("SessionBreakoutERFillAnchored", …)` line.
- `tests/engine/test_fill_anchored.py` (8 tests: registry/build; entry selection byte-identical
  to the incumbent incl. equal `sl_pips`; long & short stop/target anchor to the fill; symmetric
  1:1 from the fill; explicit contrast that the incumbent anchors to the level with a sub-1:1
  realised reward). Full `python -m pytest -q` green (387 passed, 2 skipped). No writes to
  `state/`, no live-path edits.
- **Live-mirror:** not required for a dev backtest. The new exit placement is produced inside
  `evaluate` (the single decision chain live and backtest both run), so there is no new `manage`
  branch to mirror; a future promotion would still go through the standard human-approved path.

## Backtest results
Command: `python3 scripts/run_backtest.py --strategy SessionBreakoutERFillAnchored --walkforward
--trials 170` (cumulative trial count 170; 59,993 M15 bars, 2024-01 → 2026-05).
A/B: `python3 scripts/run_backtest.py --strategy SessionBreakoutER --trials 170` (market-fill HEAD).

| metric | gate | candidate (fill-anchored) | incumbent HEAD (level-anchored, market-fill) |
|---|---|---|---|
| expectancy_r | ≥ 0.10 | **−0.127** FAIL | −0.080 |
| profit_factor | ≥ 1.3 | **0.76** FAIL | 0.56 |
| sharpe (ann.) | ≥ 1.0 | **−1.24** FAIL | −2.00 |
| sortino | ≥ 1.5 | **−1.52** FAIL | −2.21 |
| sample_size | ≥ 200 | 225 PASS | 224 |
| deflated_sharpe | ≥ 0.95 | **0.000** FAIL | 0.000 |
| ftmo_no_breach | 0 | 0 PASS (hard) | 0 |
| win_rate | — | 51.6% | 57.6% |
| maxDD | — | $8,691 | $9,370 |

Walk-forward: **2/7** folds profitable (weak=5), min fold **−0.355R** (severe), stitched OOS
−0.093R vs in-sample −0.127R (no collapse, but a stably adverse edge). **Lockbox**
2025-11→2026-05: 60 trades, −0.221R, PF 0.59, Sharpe −2.41 → **FAIL**. WALK-FORWARD VERDICT: FAIL.

## Verdict
**tested-rejected — fails 6/7 in-sample gates and the full walk-forward + lockbox.** Against the
incumbent it is a mixed A/B: fill-anchoring IMPROVES dispersion (PF +0.20, Sharpe +0.76, Sortino
+0.69, maxDD −$679) but WORSENS the primary expectancy gate (−0.047R) and win rate (−6.0pp).
Bigger, fewer wins do not compensate for the lost high-win-rate skew. No proposal filed
(promotion requires ALL gates to pass). Trial #170 consumed.

## Lessons
1. **The level-anchored skew is net-BENEFICIAL, not a defect — settled with data.** The library
   had twice asserted (without testing) that anchoring exits to the fill "erases the skew" and
   loses. It does erase the skew, and it does lose: symmetrising to a true 1:1 drops win rate
   57.6%→51.6% and expectancy −0.080→−0.127R. The closer level-anchored target was *harvesting*
   the breakout-bar's small immediate continuation as a cheap high-probability sub-1R win; making
   each win a full 1R asks the entry for follow-through it does not have (cf. the closed
   directional-breakout family — continuation past ~1R net of cost is un-harvestable on EURUSD
   M15). The reasoning dismissal is now a measured verdict.
2. **Dispersion improved while central tendency worsened — a useful decomposition.** PF/Sharpe/
   Sortino/maxDD all got BETTER under fill-anchoring (fewer, larger, more symmetric trades reduce
   tail dispersion) even as expectancy got WORSE. Risk-adjusted ratios and expectancy can move in
   OPPOSITE directions when you reshape R:R; judging on the gate stack (which requires BOTH
   expectancy ≥0.10R AND PF ≥1.3) correctly catches this — neither anchor produces an edge.
3. **Exit-model family now 0/4** (scaled-runner, ≥2R target, follow-through time-stop, exit
   ANCHOR). Every exit lever — target tail, loser-timing, and now the risk anchor itself — has
   been tested and failed on this entry. The 06-20 lesson stands and is reinforced: *a
   management/exit overlay cannot manufacture an edge the entry lacks*. The anchor was the last
   plausible "the entry's edge is being mismeasured" hypothesis; it is not mismeasured, it is
   absent. Exit research on `SessionBreakoutER` is closed.
4. **Process:** isolating exactly one variable (same `sl_pips`, same target multiple, same entry
   selection — only the anchor moved) made the A/B clean and the −0.047R attributable solely to
   the anchor. Worth repeating: when a report *asserts* a direction is dead without a trial, a
   single-variable A/B is a cheap, high-value way to convert the assertion into a citable verdict.

## Next steps
- **Do not test further exit/management variants on `SessionBreakoutER`** (family 0/4; the
  entry has no live edge to manage). This includes ATR-trailing-stop exits — a trailing stop is a
  continuous relaxation of the already-rejected ≥2R target and shares its "continuation past ~1R
  doesn't pay" failure mode; queue only with an a-priori probe showing post-1R MFE pays net of
  cost, which the closed breakout family argues against.
- The standing lever is unchanged and now near-exhaustive: **longer history / a second
  instrument** (spec 08 §8). With breakout, mean-reversion (0/4), trend (0/3) and exit-model
  (0/4) all closed under live-faithful fills on EURUSD M15, structural R&D on this dataset has
  very little headroom left.
- **M5 review (today, 2026-06-21):** this run is strong evidence to (a) reduce research cadence
  from daily, and (b) prioritise a longer EURUSD export and/or a second instrument before
  spending more trials — the DSR bar (now 170 cumulative) keeps rising while the testable idea
  space on the current data is essentially closed. Flagged for Cayden.
