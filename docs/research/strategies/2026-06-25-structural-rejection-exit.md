---
id: 2026-06-25-structural-rejection-exit
name: SessionBreakoutERStructuralExit
family: exit-model
status: tested-rejected
related: [2026-06-20-followthrough-time-stop, 2026-06-21-fill-anchored-exit, 2026-06-15-resting-stop-and-market-entry]
sources:
  - "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6709401"
  - "scripts/probe_structural_rejection_exit.py"
  - "scripts/probe_previous_day_range_breakout.py"
trials_used: 1
verdict: "FAIL all gates (−0.149R/PF 0.33/WR 40.9%/0/7 WF folds/lockbox FAIL); scratch at close<OR_high fires at near-full-SL territory, not break-even; probe measured conditional outcomes not scratch price — exit-model 0/5"
---

# SessionBreakoutERStructuralExit — scratch on structural rejection (close back inside OR)

## Hypothesis & market rationale

After an incumbent market-fill entry, a bar that CLOSES back inside the opening range is a
structural rejection signal: price has definitively failed to hold the breakout level and
re-entered the prior auction range. Scratching the trade at market when this occurs should be
**selective** — the probe showed that the 87 trades (38.8%) with at least one close-below-OR_high
had mean R = −0.386R vs +0.114R for the 137 trades without any such bar (delta −0.501R,
well exceeding the pre-registered −0.15R threshold). The hypothesis was that this selection
could be monetised by exiting early when the rejection signal fires, avoiding the eventual
full stop loss.

Differentiation from rejected exit models (§4.3):
- **FollowThrough time-stop** (2026-06-20, 0/3): scratched on "underwater by N bars" — ANTI-selective
  because market fill is above OR_high while 1R target is anchored to OR_high, so genuine winners
  look underwater early. The structural exit is immune to this: a winner that holds above OR_high
  after entry is never scratched.
- **FillAnchored** (2026-06-21, 0/4): changed the anchor (fill vs level). This changes the trigger
  condition (structural price-action event), not the anchor.
- Both prior exit models left "structural rejection" as the explicitly un-excluded lever.

## Sources

- Mesfin (2026), "Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures"
  (SSRN 6709401): systematic falsification study of 14 intraday signal families including
  liquidity grab reversals on futures — motivation for the structural-rejection concept.
- `scripts/probe_structural_rejection_exit.py` — internal probe that computed the selection
  signal on incumbent backtest trades (87/224 had rejection, delta −0.501R).
- `scripts/probe_previous_day_range_breakout.py` — companion probe on PDH/PDL breakout
  (also probed this run, probe-rejected; see §Triage notes below).

## Relation to prior library work

Builds on the exit-model line (2026-06-03, 2026-06-07, 2026-06-20, 2026-06-21) and the
fill-realism finding (2026-06-15). The stated differentiation — price-action structural trigger
immune to fill-offset anti-selection — was genuine; the probe result was also genuine. The failure
mode is new: **the trigger fires at near-full-stop-loss territory**, not break-even (see §Lessons).

## Strategy spec

**Entry:** Unchanged from SessionBreakoutER (market fill above OR_high + 1.5-pip buffer for
longs; market fill below OR_low − buf for shorts). ER/ATR regime gate unchanged.

**Additional management rule (additive):** In `manage()`, for each closed bar during the trade:
- LONG: if `bar.close < max(high of all OR bars)` → `ManageDecision("close_all")`
- SHORT: if `bar.close > min(low of all OR bars)` → `ManageDecision("close_all")`
OR bounds reconstructed from bars history for the current London session date.

**Exit geometry (spec 08 §5.8):** Inherited from incumbent (stop ~1.2×ATR anchored to OR level,
target 1R). The ADDITIVE management change was deliberately isolated: only the management trigger
was changed, not the geometry, so the hypothesis could be tested cleanly.

**Pre-registered decision rule (probe):** WORTH A TRIAL if delta R ≤ −0.15R AND n_rej ≥ 20.
Both met: delta = −0.501R, n_rej = 87. Trial spent: #171.

## Implementation notes

- **New file:** `src/engine/strategy_structural_exit.py` — `SessionBreakoutERStructuralExit(SessionBreakoutER)`
- **Registry:** one `register("SessionBreakoutERStructuralExit", ...)` line added to `src/engine/registry.py`
- **Tests:** `tests/engine/test_structural_exit.py` — 11 tests (registry, evaluate identity, manage scratch/hold/boundary/failsafe/BE-delegation)
- **Pytest:** 396 passed, 2 skipped — green
- No writes to `state/`, no live-path edits
- Live-mirror flag: N/A (failed; no promotion path)
- Also written: `scripts/probe_structural_rejection_exit.py`, `scripts/probe_previous_day_range_breakout.py` (companion probe, see §Triage)

## Backtest results

Command: `python3 scripts/run_backtest.py --strategy SessionBreakoutERStructuralExit --walkforward --trials 171`

| metric | gate | candidate | incumbent HEAD (market-fill base) |
|---|---|---|---|
| expectancy_r | ≥ 0.10R | **−0.149R** ❌ | −0.080R |
| profit_factor | ≥ 1.3 | **0.33** ❌ | 0.56 |
| sharpe | ≥ 1.0 | **−3.08** ❌ | −2.00 |
| sortino | ≥ 1.5 | **−3.24** ❌ | −2.21 |
| sample_size | ≥ 200 | 225 ✅ | 224 |
| deflated_sharpe | ≥ 0.95 | **0.000** ❌ (trials=171) | 0.000 |
| ftmo_no_breach | = 0 breaches | 0 ✅ | 0 |

Walk-forward (7 folds, 3-month test):

| fold | trades | exp(R) | PF |
|---|---|---|---|
| 2024-01-..04 | 22 | −0.374 | 0.26 |
| 2024-04-..07 | 17 | −0.245 | 0.23 |
| 2024-07-..10 | 25 | −0.081 | 0.39 |
| 2024-10-..01 | 18 | −0.195 | 0.36 |
| 2025-01-..04 | 23 | −0.206 | 0.30 |
| 2025-04-..07 | 22 | −0.157 | 0.39 |
| 2025-07-..11 | 38 | −0.087 | 0.62 |

Stitched OOS: −0.178R; 0/7 folds profitable; severe fold −0.374R. Lockbox: −0.070R/PF 0.68, FAIL.

**Win rate:** 40.9% (vs 57.6% base). The structural exit REGRESSED the incumbent on every axis.

## Verdict

**FAIL** — 5/7 gates fail, 0/7 WF folds profitable, lockbox FAIL. Not promotable. No proposal filed.

## Lessons

### 1. The probe measured conditional *ultimate* outcomes, not conditional *scratch prices*

The probe found: "trades with a close-below-OR_high have mean R = −0.386R." This is the
*ultimate* outcome of those trades (final SL/TP/EOD). But the structural exit scratches
**at the bar's close** when the trigger fires — which is also at or below OR_high. Since:
- Entry ≈ OR_high + buffer + costs ≈ OR_high + 1.9 pips
- Scratch fires when close < OR_high
- Scratch fill ≈ bar close, which could be 5–10+ pips below OR_high

The scratch R ≈ (close − entry) / sl_pips ≈ (OR_high − 10p − (OR_high + 1.9p)) / 12p ≈ −0.99R.
The scratch is at **near-full-stop-loss**, not break-even. The selection information (predicts loss)
was real, but monetising it this way is economically equivalent to taking the stop earlier.

**Rule for future probes:** always measure the scratch price distribution, not just the binary
had_rejection flag and ultimate outcome. A probe that doesn't compute E[scratch_R | rejection]
gives an optimistic picture.

### 2. OR_high (max wick) is too close to entry to be a useful scratch trigger

OR_high = max(high) of OR bars. Entry = OR_high + buf + costs ≈ OR_high + 2 pips. So `close < OR_high`
fires when price has pulled back just 2 pips from entry. At that point, the bar's close may be
anywhere from OR_high − 0.1p (trivial) to OR_high − 15p (near stop). The trigger does NOT
distinguish between "barely back inside" and "deeply inside." The signal fires early but the
scratch price is already deep.

### 3. The "no rejection" 67.2% win rate is real — but is self-fulfilling

Trades that never close below OR_high after entry (67.2% WR, +0.114R) are trades that moved
IMMEDIATELY in the right direction. These are the breakout bar's best follow-throughs. Scratching
the "rejection" subset doesn't help those trades — they're already winning. The structural exit
adds no value to the winner segment and scratches the loser segment at near-SL prices.

### 4. Exit-model research on SessionBreakoutER is conclusively closed (0/5)

Every management overlay tested (scaled runner, ≥2R tail, time-stop, fill-anchor, structural
rejection) regressed or failed the incumbent. The common root: the live-fill incumbent has
**no edge** (−0.080R); no exit can manufacture positive expectancy from a negative-EV base.
The selection information exists (this probe proves it) but cannot be captured without changing
the ENTRY mechanism (so that entries only occur when structural rejection risk is low).

### 5. Companion probe: PDH/PDL Breakout — probe-rejected (no trial)

This run also probed **PreviousDayRangeBreakout** (prior-day high/low breakout in the London/NY
session, market fill after bar closes above PDH). Result: n=435 trades, gross −0.96 pip
(−0.100R gross), WR 33.3%, PF 0.86 — probe-rejected. The mechanism (daily structural range break)
showed NEGATIVE gross expectancy even before costs, and short signals lost −2.18 pip/trade on average.
The ~65% within-session double-break rate that closed the intraday breakout family also applies
to prior-day range levels. No trial spent. The breakout family is conclusively closed across all
level definitions tested (intraday OR, London-open OR, NR7, Asian box, PDH/PDL prior-day).

## Next steps

The library's remaining open ideas are:
- **ECBFixConditionalReversion** — probe the conditional post-fix drift before any trial
- **SofterTrendAlignVeto** — probe the trade-count cut size before any trial (floor-bound)
- All others: mean-reversion (4/4 closed), trend (0/3), breakout (conclusively closed), filter (floor-bound on market-fill base)

The most productive unblocking action remains a **longer data export** to revive the TrendAlignedORB
candidate (dominates HEAD on quality but fails the 200-trade floor) and the filter queue.

**Exit-model research on SessionBreakoutER is CLOSED** (0/5 across target, timing, anchor, and
structural triggers — a management overlay cannot manufacture edge the entry lacks).
