---
id: 2026-06-19-session-range-false-break-fade
name: SessionRangeFalseBreakFade
family: mean-reversion          # fade a FAILED opening-range breakout (Turtle Soup)
status: idea                    # probe-rejected (no trial spent) — see Verdict
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-08-asian-sweep-fade, 2026-06-10-asian-sweep-fade-rr, 2026-06-16-vwap-stretch-reversion, 2026-06-18-nr7-volatility-breakout]
sources:
  - "https://blueberrymarkets.com/market-analysis/turtle-soup-trading-strategy-identifying-potential-false-breakouts/"   # Turtle Soup / Raschke false-breakout fade
  - "https://www.orbex.com/blog/en/2026/03/turtle-soup-strategy"   # liquidity-grab rationale, entry on close back inside range
  - "https://fxopen.com/blog/en/what-is-ict-turtle-soup-and-how-can-you-use-it-in-trading/"   # ICT turtle soup rules; target = opposite side of range
  - "https://tradethatswing.com/eurusd-opening-range-stats-indicate-high-double-break-precentage-use-to-your-advantage/"   # EURUSD ORB ~65% DOUBLE-break stat
  - "https://www.quantifiedstrategies.com/opening-range-breakout-strategy/"   # ORB backtest mechanics
trials_used: 0                  # PROBE only — no backtest, no trial-ledger entry, no DSR cost
verdict: "probe-rejected (no trial): fading a FAILED opening-range break has ~0 GROSS expectancy on EURUSD M15 — 347 events, win 42.4%, mean +/-R gross -0.017 (ranging -0.031, trending +0.045), -0.249R net of ~2.6p cost, median RR 0.60 (opposite-side target is CLOSER than the breakout-extreme stop). The false break reverts only SHALLOWLY (back inside the range), it does not swing to the opposite edge; EURUSD's ~65% double-break rate means a 'failed' break is usually whipsaw, not reversal. Extends the mean-reversion closure to a 4th anchor (failed-breakout); no trial spent (W25 still 7/10)."
---

# SessionRangeFalseBreakFade — fade the incumbent's own false breakouts (Turtle Soup)

## Hypothesis & market rationale
The library's single most important live-faithful finding is that the incumbent breakout
family is edgeless because **the resting-touch fill takes the false breaks** — i.e. a large
share of opening-range breakouts are *false* and snap back inside the range
([[2026-06-15-resting-stop-and-market-entry]], where the touch fill scored −0.267R / 44% win
precisely by catching those false breaks). The natural inversion: if false breaks of the
session opening range are systematically the losing population for a breakout trader, perhaps
they are the *winning* population for a fader. This is the classic **Turtle Soup** setup
(Linda Raschke; later ICT): price pokes beyond a key level, fails, closes back inside, and you
trade the *opposite* direction back across the range, on the theory that the break was a
liquidity grab / stop-run that now reverses.

Falsifiable claim, market-fillable, EURUSD-M15-specific: *after a post-OR bar closes beyond the
London/NY-overlap opening range and a later post-OR bar closes back inside it, fading at the
confirmation close earns a positive expectancy (net of cost) toward the opposite side of the
range.* If the "false breaks revert" intuition is real and harvestable, this is the direct way
to monetise the exact population that sank the breakout family — and, unlike the incumbent, the
entry is a **market order on the confirmation close**, fully live-fillable (no retcode-10015
level-fill artifact). That combination — exploiting a documented in-house failure mode with a
live-faithful fill — is why it earned a probe.

## Sources
- *Turtle Soup* false-breakout reversal (L. Raschke, *Street Smarts*; popularised by ICT):
  Blueberry Markets, Orbex, FXOpen explainers — entry **when price closes back inside the
  prior range**, standard **target = the opposite side of the range**, rationale = trapped
  liquidity / stop-run reversal. Hypothesis only.
- Trade That Swing — *EURUSD opening-range stats*: on a 30-min OR, **price breaks BOTH the high
  and the low ~65% of the time** intraday. This is the structural counter-evidence (below).
- QuantifiedStrategies — ORB backtest mechanics (session definition, force-flat).

The backtester — here, the parquet probe — is the arbiter, not the sources.

## Relation to prior library work
- **[[2026-06-15-resting-stop-and-market-entry]]** (execution) — the *origin* of the
  hypothesis: it proved false breaks are the breakout family's losers. This candidate asks the
  mirror question. **What is different:** it is the opposite-side bet on the same events. **Why
  the breakout failure mode need not carry:** a directional breakout loses *on* the false
  break; a fader is positioned the other way, so the same events are not assumed to lose — only
  the probe can say. (It did: the reversion is too shallow — see below.)
- **[[2026-06-08-asian-sweep-fade]] / [[2026-06-10-asian-sweep-fade-rr]]** (mean-reversion,
  CLOSED) — sweep-and-reclaim fades of the **overnight Asian range**. **Differentiated:** a
  *different level* (the active London/NY-overlap OR the incumbent trades, not the Asian range)
  and a *different trigger* (a failed CLOSE-confirmed breakout, not an intrabar wick sweep).
  Legitimately probe-able under §4.3 rather than auto-forbidden — but it ultimately fails for a
  related reason (fading intraday EURUSD structure is adverse).
- **[[2026-06-16-vwap-stretch-reversion]]** (mean-reversion, tested-rejected) — fades a
  *stretch from the mean*; this fades a *failed level break*. Different mechanism, same family
  verdict now.
- **[[2026-06-18-nr7-volatility-breakout]]** (breakout) — established that EURUSD OR breaks are
  two-sided ("volatility expands both ways"). The ~65% double-break stat below is the same coin.

## Strategy spec (as it would have been built, had the probe passed)
- **Session / OR:** identical to HEAD v4 — London tz, window 13:00–16:00, OR = first 30 min
  (13:00–13:30). `range_high/low` from the OR; `buffer = 1.5 pip`.
- **Trigger:** (1) a post-OR bar CLOSES beyond a level (`close > range_high+buf`, or
  `< range_low−buf`) — the breakout; (2) a later post-OR bar CLOSES back inside the range
  (`close < range_high`, or `> range_low`) — the failure. Fade at **market** on bar (2)'s
  close (failed up-break ⇒ SHORT; failed down-break ⇒ LONG). One event per side per day.
- **Regime gate:** would have inverted ER (`ER < threshold` ⇒ ranging) like the fade family,
  with the same NORMAL ATR band — but the probe shows even the ranging slice is negative.
- **Exit geometry (spec 08 §5.8 — pre-registered, NOT inherited):**
  `stop = breakout-excursion extreme ± 0.25×ATR` (you are wrong only if the "failed" break
  resumes and takes out its own extreme — a tight, mechanism-defined invalidation);
  `target = the opposite side of the range` (the Turtle Soup standard — the reversion's natural
  destination). R:R is whatever that geometry implies — and the probe shows it is **< 1**
  (median 0.60), because the opposite range edge is *closer* than the excursion-extreme stop.
  This is itself a red flag the mechanism does not self-justify a ≥1:1 trade.
- Params that would have become levers: `buffer_pips`, stop ATR buffer, ER gate direction,
  target (opposite-edge vs range-mid).

## Probe (the gate this never cleared)
Rather than spend a trial, I measured the realised fade outcome directly on
`state/parquet/eurusd_m15.parquet` (59,993 M15 bars, 2024-01 → 2026-05) with the pre-registered
exit (stop = excursion extreme + 0.25×ATR; target = opposite range side), intrabar
stop-before-target priority (conservative), force-flat at the 16:00 window end. Cost reference
= **2.6 pip round-trip** (commission + slippage + spread; the library's standard). Script:
`scripts/probe_false_break_fade.py`.

| slice | n | win % (net) | mean R **gross** | mean R **net @2.6p** | median R:R |
|---|---|---|---|---|---|
| **ALL** | 347 | 42.4 | **−0.017** | −0.249 | 0.60 |
| ER < 0.32 (ranging) | 284 | 41.5 | −0.031 | −0.255 | 0.55 |
| ER ≥ 0.32 (trending) | 63 | 46.0 | +0.045 | −0.222 | 0.84 |
| up-break → faded SHORT | 177 | 48.0 | +0.026 | −0.204 | 0.67 |
| down-break → faded LONG | 170 | 36.5 | −0.062 | −0.296 | 0.55 |
| ER < 0.32 & risk ≤ 15p | 169 | 40.8 | −0.014 | −0.310 | 0.75 |

347 raw events across 311 days — *frequency is not the problem* (it would clear the 200-trade
floor even after a regime gate). **The sign is the problem.** Mean expectancy is ≈ 0 **before
any cost** (−0.017R all; −0.031R in the ranging regime the mechanism is supposed to like) and
clearly negative after the 2.6-pip cost (−0.249R). No slice clears the +0.10R expectancy gate
even gross. The only mildly positive gross cell — up-breaks faded short, +0.026R — is still
far below the gate and negative net. Median R:R 0.60 confirms the geometry is upside-down: the
opposite-side target sits *closer* than the excursion stop, so the fade needs a high win rate
it does not have (42%).

**Why it fails, mechanistically.** A "failed" break that closes back inside the range is *not*
a reversal to the other side — EURUSD's opening range **breaks both directions ~65% of the
time** (Trade That Swing). So a close back inside is most often the *first half of a whipsaw*:
the price re-enters the range and then breaks the **other** side (continuation of two-sided
chop), rather than swinging cleanly to the opposite edge the fade targets. The reversion is
real but **shallow** (back inside), not **deep** (to the far side). That is exactly the
distribution the probe measured: roughly symmetric forward outcomes, no harvestable drift.

## Implementation notes
**None — no code was written.** Killed at stage-3 triage by the data probe (spec 08 §3; §8
"most ideas die at stage 3 for free"), exactly as [[2026-06-17-intraday-seasonality-drift]].
No indicator, Strategy module, registry line, or test added; `src/`, `state/`, and the live
path are untouched. No trial-ledger entry (no backtest); DSR budget unaffected. Only the probe
script (`scripts/probe_false_break_fade.py`) and this report were added. pytest unaffected (no
`src/`/`tests/` changes).

## Backtest results
None. Probe-rejected before the backtest stage. A `--walkforward` trial on a mechanism with
≈ 0 gross expectancy and median R:R < 1 would burn DSR budget to confirm what the probe shows.

## Verdict
**Probe-rejected (no trial spent).** Fading a failed opening-range breakout (Turtle Soup on the
session OR) is **un-harvestable on EURUSD M15**: ≈ 0 gross expectancy, negative net of cost,
R:R < 1, across all slices. The differentiation from the closed Asian sweep-fade family was
valid (different level + trigger), so the probe was legitimate — but the result lands the same
family verdict. **Mean-reversion fade is now 4/4 across distinct anchors** (Asian-range 1R,
Asian-range 2R, session-VWAP stretch, and now session-OR failed-break). W25 trial budget
**unchanged: 3 spent of 10 → 7 remaining**; cumulative trials still **168**.

## Lessons
1. **"False breaks revert" ≠ "false breaks reverse to the opposite side."** The resting-touch
   finding ([[2026-06-15-resting-stop-and-market-entry]]) showed false breaks are the
   *breakout* trader's losers; it does **not** follow that they are the *fader's* winners. The
   reversion is shallow — back inside the range — which only confirms the break failed, not
   that price will travel to the far edge. The two populations are not mirror images.
2. **The ~65% double-break rate is the structural killer of BOTH directional breakout AND
   failed-break fade on EURUSD M15.** Two-sided opening ranges mean a re-entry into the range
   is usually the start of a whipsaw to the *other* side, not a clean reversal. This single
   fact now explains the closure of the breakout family *and* this fade in one mechanism: the
   OR is a chop generator, not a directional-edge generator, on this instrument/timeframe.
3. **R:R < 1 from a mechanism's own natural geometry is a pre-test red flag.** When the
   pre-registered target (opposite range edge) is structurally closer than the
   mechanism-defined stop (excursion extreme), the trade needs a win rate the mechanism does
   not supply. Worth checking the implied R:R in the probe *before* even the sign test.
4. **Gross-expectancy probing is a free DSR saver (reinforced).** A ~0 GROSS mean across 347
   events is decisive without spending a trial — costs only make a zero-edge mechanism worse;
   no exit-geometry retune can rescue a mechanism with no raw drift (cf. the ≥2R rejection
   precedent [[2026-06-07-tp-2r-sweep]]).

## Next steps
- **Mean-reversion fade family: closed across 4 anchors.** Do not test further fade variants
  (range-mid target, deeper-penetration filter, sweep-magnitude) on EURUSD M15 without an
  a-priori probe showing a *gross* conditional drift above the +0.10R gate — the family's
  problem is the sign of the drift, which no exit geometry or level choice has flipped.
- **Triage caveat recorded for the incumbent-filter queue** (SofterTrendAlignVeto,
  VolumeConfirmedORB, MomentumGatedORB, QualityGatedSecondEntry, and the passed-but-dominated
  [[2026-06-13-second-entry-orb]]): all of these were/are measured as filters on the incumbent
  break whose +0.391R is a **level-fill artifact** ([[2026-06-15-resting-stop-and-market-entry]]).
  Filtering an artifact edge yields a higher-quality *artifact* subset, not a live edge. Any of
  these is only worth a trial if **re-based on the MARKET-fill incumbent** (base −0.024R) and
  shown to lift it above the gates while holding ≥ 200 trades. Added to the idea queue as a
  binding pre-condition.
- **The real lever remains data, not ideas (spec 08 §8).** With breakout, trend (0/3), and
  mean-reversion (0/4) all broadly closed under live-faithful fills on this single 18-month
  EURUSD-M15 export, the highest-value next action is a **longer history export and/or a second
  instrument** — to widen the data, not the trial accounting. Recommend raising this at the
  **M5 review (2026-06-21)**.
