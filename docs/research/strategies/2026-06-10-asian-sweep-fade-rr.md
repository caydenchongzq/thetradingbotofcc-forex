---
id: 2026-06-10-asian-sweep-fade-rr
name: AsianSweepFadeRR
family: mean-reversion
status: tested-rejected
related: [2026-06-08-asian-sweep-fade, 2026-06-07-tp-2r-sweep, 2026-06-02-session-breakout-er, 2026-06-03-full-exit-model]
sources: ["https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6592020", "https://fxopen.com/blog/en/what-is-ict-turtle-soup-and-how-can-you-use-it-in-trading/", "https://www.fundedtradingplus.com/propiq/turtle-soup-strategy-fading-failed-breakouts/", "https://nordfx.com/traders-guide/turtle-soup-trading", "https://github.com/paperswithbacktest/awesome-systematic-trading"]
trials_used: 1
verdict: "Asymmetric-R:R does NOT rescue the sweep fade: tight wick stop + single 2R drops win rate 54.7%->35.8% while PF stays ~0.68 — exp -0.212R, 1/7 WF folds, lockbox -0.083R PF 0.84 FAIL. Constant-negative PF under an R:R rotation = no underlying edge; the fade family is closed on EURUSD M15."
---

# AsianSweepFadeRR — the asymmetric-R:R variant of the rejected Asian-range sweep fade

## Hypothesis & market rationale
The rejected [[2026-06-08-asian-sweep-fade]] showed the London-open Asian-range sweep *does*
reverse more often than not (win rate 54.7%) yet was **structurally negative** as a
**symmetric-1R** system: with the stop at `max(structure, 1.2×ATR)` the average loss exceeded
the average win, so every fold + the lockbox went negative. Its own Lessons (§1) and
Next-steps prescribed the precise follow-on tested here, and the wider practitioner lore plus
a fresh academic source agree on the mechanism's *direction*:

> "Practitioner sweep lore survives on asymmetric R:R claims (1:3+) that shift the burden to a
> low win rate — the symmetric version is provably negative here." (asian-sweep-fade Lesson 2)

**Falsifiable, pre-registered prediction:** replacing the symmetric 1R with a **tight stop just
beyond the sweep wick + a single 2.0R target** turns the >50%-but-losing distribution into a
sub-50%-but-winning one, clearing the gates + walk-forward + lockbox. **Null (and the recorded
outcome):** the sweep carries *no* exploitable R-edge on EURUSD M15, so rotating the R:R only
trades win rate for payoff at a constant-negative profit factor.

## Sources
- **Costa, R. — "The Illusion of Breakouts: Empirical Evidence of Institutional Liquidity
  Capture in Major Currency Pairs," SSRN 6592020.** Strongest evidence tier found for this
  family: a decade-long (2016–2026) microstructure study mapping the 20-day institutional range
  over 3,800+ breakout attempts across EURUSD/GBPJPY/USDCAD/USDJPY/AUDUSD + Gold, reporting FX
  markets **invalidate breakouts / sweep liquidity in >75%** of mapped occurrences (Gold the
  directional exception). Motivates the fade's *direction*; the harness, not the paper, is the
  arbiter of whether it is tradeable in *this* expression (it was not).
- FXOpen / FundedTradingPlus / NordFX — ICT "turtle soup" failed-breakout fade; the canonical
  asymmetric target is "the opposite side of the range" (1:3–1:4 R:R), the practitioner basis
  for testing ≥2R. Hypothesis-only; no code copied (spec 08 §5.1).
- paperswithbacktest/awesome-systematic-trading — catalog entry point (intraday seasonality /
  mean-reversion family); no validated public backtest of *this* exact pattern was found.

## Relation to prior library work
This is a **library-sanctioned, differentiated variant**, not a forbidden re-test (spec 08
§4.3). It must clear two recorded rejections, and changes exactly the variable each one points
to:

- **vs [[2026-06-08-asian-sweep-fade]]** (tested-rejected, *symmetric 1R*). Entry, session-range
  definition and the inverted-ER regime gate are held **identical** (inherited unchanged) so the
  **exit geometry is the cleanly-isolated variable**. Its failure mode was "win rate > 50% but
  avg loss ≫ avg win" with a stop floored at 1.2×ATR against a 1R target — addressed head-on
  here by a tight wick stop (1.0×ATR floor) + a single 2R target. This is verbatim its own
  Next-steps experiment. *Result: the change did not rescue it — see Lessons.*
- **vs [[2026-06-07-tp-2r-sweep]]** (tested-rejected, ≥2R targets on the *incumbent*). That
  rejected 2R on a **breakout/continuation** (spent-momentum follow-through rarely reaches 2R).
  The differentiation argument pre-registered before testing: a **fade enters at the reversion
  extreme** with the whole range to travel back through, so per Costa's >75% mean-reversion its
  2R-hit-rate should be structurally higher than a breakout's — a different R-distribution.
  *The harness refuted this for EURUSD M15: the fade's 2R hit rate (35.8%) was too low to
  profit, so the rejection's spirit (≥2R is not reachable often enough here) extends to the
  fade too.*
- Exits reuse the validated single-target ExitPlan machinery from [[2026-06-03-full-exit-model]]
  (broker-side SL + one TP) → **no live-mirror needed**.

## Strategy spec
- **Universe / data:** EURUSD M15 only (`state/parquet/eurusd_m15.parquet`, 2024-01..2026-05).
- **Asian range:** London 00:00–08:00 M15 high/low; require ≥16 Asian bars else `NoSignal`.
- **Entry (inherited from AsianSweepFade, unchanged):** in the fade window, a closed bar whose
  high exceeds `asian_high + 1.5 pip` AND closes back **inside** the range ⇒ market SHORT at
  that close (mirror long at the low). Double-sided sweep ⇒ `NoSignal` (ambiguous). One-shot
  per side, close-based.
- **Fade window:** London **08:00–12:00** — widened from the rejected version's 08:00–11:00
  **a-priori, solely to clear the 200-trade `sample_size` floor** (the 3h window gave 179
  trades; +1h of still-liquid pre-overlap London restores headroom). Not tuned on results.
  No overlap with the incumbent's 13:00–16:00 window.
- **Regime gate (inherited, unchanged):** incumbent measurement, **ER gate INVERTED**
  (ER < 0.30, the exact complement of the trend gate — no new free parameter) + same NORMAL
  ATR band [4, 22] pips, percentile (0.20, 0.90); same news blackout.
- **Params** (a-priori, deliberately **not** swept): `fade.window_end=12:00`,
  `fade.wick_buffer_pips=0.5`, `exits.atr_mult_sl=1.0`, `exits.target_r_multiples=[2.0]`,
  `exits.move_be_after_r=null`. Would become `ALLOWED_LEVERS` only if it had passed.

**Exit geometry (spec 08 §5.8 — chosen per mechanism, the differentiated variable):**
- **Stop = max(distance-to-sweep-extreme + 0.5 pip, 1.0×ATR).** Rationale: a failed breakout is
  invalidated the moment price reclaims the swept extreme, so the stop belongs **just beyond the
  wick** — *not* floored at the incumbent's 1.2×ATR (which made the rejected version's stop
  structurally wider than its 1R target). The 1.0×ATR floor (bottom of the §5.8 range) only
  guards a degenerate near-zero stop when the bar closes adjacent to its extreme.
- **Target = single 2.0R (R:R = 1:2).** Rationale: the reversion target lies back through the
  range; per Costa, structural sweeps mean-revert >75% of the time, so the snap-back should
  routinely travel ≥2× a tight wick-stop. A single asymmetric target with **no partials and no
  BE move** is the cleanest possible test of the payoff hypothesis the symmetric-1R version
  failed (a BE move would just convert near-winners to scratches and muddy the test).

## Implementation notes
- Additive only: `src/engine/strategy_asian_sweep_rr.py` (`AsianSweepFadeRR(AsianSweepFade)`).
  Reuses the parent's `evaluate` (sweep detection), `_fade_regime` (inverted-ER), `_already_fired`,
  `_blackout`, `manage`, tz; overrides only `__init__` (one new param `wick_buffer_pips`) and
  `_fade_signal` (the exit geometry). Incumbent **and** `AsianSweepFade` classes unmodified.
  One `register("AsianSweepFadeRR", …)` line in `src/engine/registry.py` (additive).
- Dev config `config/dev/asian_sweep_fade_rr.yaml` (single pre-registered configuration).
- Tests: `tests/engine/test_asian_sweep_rr.py` (9, incl. a check the 2R target is strictly
  further than the parent's 1R, and that the widened window admits an 11:30 sweep) +
  `tests/backtest/test_asian_sweep_rr_harness.py` (2). **Full `python -m pytest` green (265
  passed).** No writes to `state/` (other than the sanctioned trial-ledger append); no
  live-path edits. **Live-mirror NOT needed** (standard broker-side SL/TP seam).

## Backtest results
Command: `py scripts/run_backtest.py --config-file config/dev/asian_sweep_fade_rr.yaml
--walkforward --trials 161` (`--trials 161` = cumulative 160 from [[2026-06-09-late-session-drift]]
+ this candidate; the ledger file undercounts, so the count is reconstructed from reports per
the standing note). Data: 59,993 M15 bars 2024-01-01 → 2026-05-29.

**In-sample R6 gates (full sample):**

| Gate | Threshold | Value | Pass |
|---|---|---|---|
| expectancy_r | ≥ 0.10 | **−0.212** | ✗ |
| profit_factor | ≥ 1.30 | **0.68** | ✗ |
| sharpe | ≥ 1.0 | **−1.51** | ✗ |
| sortino | ≥ 1.5 | **−2.05** | ✗ |
| sample_size | ≥ 200 | 212 | ✓ |
| deflated_sharpe (trials=161) | ≥ 0.95 | **0.000** | ✗ |
| ftmo_no_breach | 0 | 0 | ✓ |

Win rate **35.8%** (vs the symmetric version's 54.7%) — the R:R rotation moved win rate exactly
as predicted, but PF barely changed (0.65 → 0.68), the signature of **no underlying edge**.

**Walk-forward (OOS):** 1/7 folds profitable (only 2024-Q3: +0.108R); stitched OOS −0.249R;
**severe fold** −0.489R (2025-Q2); 6 weak folds. Verdict FAIL.

| window | trades | exp(R) | PF |
|---|---|---|---|
| 2024-01..04 | 25 | −0.267 | 0.65 |
| 2024-04..07 | 17 | −0.421 | 0.51 |
| 2024-07..10 | 21 | +0.108 | 1.14 |
| 2024-10..2025-01 | 20 | −0.382 | 0.54 |
| 2025-01..04 | 23 | −0.081 | 0.76 |
| 2025-04..07 | 26 | −0.489 | 0.51 |
| 2025-07..11 | 32 | −0.221 | 0.60 |

**Lockbox (held out 2025-11-01..2026-05-29, never tuned on):** trades=48, exp **−0.083R**,
PF **0.84**, sharpe −0.75 → **FAIL**.

## A/B vs incumbent HEAD
Same data, same harness, trials=161. (The candidate shares no window/mechanism with the
incumbent, so this is a reference baseline, not a head-to-head; HEAD was re-run untouched and
still clears every gate, confirming the dev run did not disturb live.)

| | in-sample exp | PF | Sharpe | win rate | DSR | verdict |
|---|---|---|---|---|---|---|
| **HEAD SessionBreakoutER v4** | **+0.294R** | 1.99 | 3.36 | 73.2% | 0.989 | PASS all gates |
| AsianSweepFadeRR | −0.212R | 0.68 | −1.51 | 35.8% | 0.000 | FAIL all but 2 |
| AsianSweepFade (1R, ref) | −0.158R | 0.65 | −1.68 | 54.7% | 0.000 | FAIL all but 2 |

## Verdict
**REJECT.** Fails in-sample (5/7 gates), walk-forward (1/7 folds, severe fold −0.489R, stitched
collapse), and the lockbox. No proposal filed. Code + tests retained (dev-registered,
unpromoted) as the worked example that **closes the sweep-fade family** on EURUSD M15.

## Lessons
1. **The Asian-range sweep fade has no R-edge on EURUSD M15 2024–2026 — confirmed under BOTH
   exit geometries.** Symmetric 1R (54.7% win, PF 0.65) and asymmetric tight-stop/2R (35.8% win,
   PF 0.68) give **the same negative PF**. Rotating R:R slid the win rate along the breakeven
   curve (2R needs >33% to win gross; got 35.8%, costs push it under) **without changing the
   profit factor** — the textbook signature that there is no edge to harvest, only a payoff
   ratio being re-sliced. This is the cleanest possible refutation of the "asymmetric R:R
   rescues the fade" hypothesis the [[2026-06-08-asian-sweep-fade]] Next-steps raised. **Do not
   re-test the Asian sweep-fade family in any exit geometry** — both ends of the R:R axis are now
   recorded failures; a future attempt needs a *different entry mechanism*, not new exits.
2. **A >75% mean-reversion statistic at the 20-day level does NOT transfer to an intraday
   8-hour-range fade.** Costa's evidence is for the *20-day institutional range*; the Asian
   overnight range is a minor intraday level where the reversion is too small (and too
   cost-laden at market-entry) to clear a 2R target reliably. Level significance is part of the
   mechanism — re-using a paper's edge at a different level is a new hypothesis, not a citation.
3. **The ≥2R rejection generalises from breakout to fade — for the same reason but a different
   cause.** [[2026-06-07-tp-2r-sweep]] failed because a spent breakout rarely *continues* 2R;
   the fade failed because the intraday reversion rarely *travels* 2R. Both say: on EURUSD M15,
   a 2R target is reached too seldom to carry a strategy unless the entry has a genuinely large
   edge to begin with. The bar for any ≥2R candidate is now: show the 2R hit rate a priori.
4. **The window-widen-for-sample-size tactic works and is honest** when pre-registered and
   non-tuned: 179 → 212 trades cleared the floor with no cherry-picking. Keep using it to put
   borderline-frequency candidates *on trial* rather than auto-failing them at sample_size — but
   it cannot manufacture an edge (here it just gave a larger, equally-negative sample).

## Next steps
- **Mark the sweep-fade family closed.** Both [[2026-06-08-asian-sweep-fade]] (1R) and this
  (2R) are tested-rejected; no further exit-geometry variants (per Lesson 1).
- **Queue (idea):** *20-day institutional-range turtle soup* — fade a sweep of a **multi-day**
  (≥20-session) structural high/low, the actual level in Costa's >75% statistic, NOT the
  overnight range. Distinct *level* (not a re-test of this entry). Risk: 20-day extremes are
  swept rarely → likely **<200 trades** (sample_size), so record as **idea / candidate-blocked
  on trade-count** until a longer history export exists; do not spend a trial until the frequency
  is estimated to clear the floor.
- **Queue (idea):** *sweep-magnitude conditioned fade* — only fade sweeps whose penetration
  beyond the level exceeds e.g. 0.5×ATR (the lore's "deep liquidity grab"); a *different entry
  mechanism* (selectivity on sweep depth), the one lever Lesson 1 leaves open — but note it is
  subtractive on an already-borderline trade count ([[2026-06-07-pre-session-compression-filter]]
  headroom lesson), so estimate frequency before testing.
