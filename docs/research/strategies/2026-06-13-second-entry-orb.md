---
id: 2026-06-13-second-entry-orb
name: SecondEntryORB
family: breakout
status: tested-passed
related: [2026-06-02-session-breakout-er, 2026-06-11-breakout-retest, 2026-06-07-tp-2r-sweep, 2026-06-12-trend-pullback-ema]
sources: ["https://forextester.com/blog/opening-range-breakout-trading-strategies/", "https://tradeproacademy.com/intraday-trading-strategy-opening-range/", "https://www.netpicks.com/turtle-soup-fading-new-20-day-high-or-lows/", "https://www.forex.academy/the-turtle-soup-plus-one-system/", "https://www.quantifiedstrategies.com/opening-range-breakout-strategy/"]
trials_used: 1
verdict: "FIRST candidate to clear ALL R6 gates + walk-forward + lockbox (252 trades, +0.266R, PF 1.84, 6/7 folds, lockbox +0.248R PF 1.75) — the additive re-break entries are marginally POSITIVE (~+0.04R each), not noise. BUT dominated by HEAD v4 on every risk-adjusted axis (exp -0.028R, PF -0.15, Sharpe -0.26, maxDD +$731, lockbox -0.076R, 7/7->6/7 folds): a pass is necessary, beating the incumbent is the sufficiency test. DO NOT PROMOTE — proposal filed for human review."
---

# SecondEntryORB — add one re-break ("second attempt") entry per side after a failed first break

## Hypothesis & market rationale
The incumbent `SessionBreakoutER` is **one-shot per side per day**: it enters on the first bar
that closes beyond the London/NY-overlap opening-range level and never re-enters that side, even
if the first break fails and price retakes the level later in the session. Practitioner ORB
literature and the "turtle soup +1" / second-attempt tradition hold that a **re-break** — first
break fails (price closes back inside the range), then the same level is broken again — is itself
a tradeable continuation: the failed first attempt sweeps stops and flushes weak hands, and the
second break runs on cleaner footing with the early faders now offside.

Falsifiable claim: **adding a second re-break entry per side (capped at 2 entries/side/day) on top
of the incumbent's unchanged first-break entry raises the system's gated, risk-adjusted
performance** — i.e. the added re-break trades carry positive, cost-surviving expectancy rather
than merely diluting the incumbent. The arbiter — not the source — decides.

## Sources
Hypothesis-only (mined for mechanism, re-implemented pure; **no community code copied into
`src/`**, spec 08 §5.6):
- ForexTester — *Opening Range Breakout Trading Strategies* (failed first breakout → a second
  entry attempt; "if stopped out twice, stop for the day").
  https://forextester.com/blog/opening-range-breakout-trading-strategies/
- TradeProAcademy — *How to Trade the Opening Range* (a re-break after a failed first push is a
  distinct, defined-risk second entry). https://tradeproacademy.com/intraday-trading-strategy-opening-range/
- NetPicks — *Turtle Soup: fading/​retaking new 20-day highs/lows* (the failed-breakout-then-retake
  structure). https://www.netpicks.com/turtle-soup-fading-new-20-day-high-or-lows/
- Forex Academy — *The Turtle Soup plus One System* (the "+1" second-attempt re-entry rule, two
  bars after the first stop). https://www.forex.academy/the-turtle-soup-plus-one-system/
- QuantifiedStrategies — *Opening Range Breakout Strategy: Backtest* (ORB win-rate baselines and
  the value of a second, confirmed attempt). https://www.quantifiedstrategies.com/opening-range-breakout-strategy/

Evidence tier: retail practitioner blogs (low); no peer-reviewed intraday-FX second-entry study.
Treated strictly as a hypothesis.

## Relation to prior library work
- **The deliberate INVERSE of the rejected [[2026-06-11-breakout-retest]].** That candidate
  *replaced* the incumbent's immediate close-entry with a retest-only entry — **subtractive**: it
  discarded the 73%-win immediate-continuation winners (win 73%→43%, PF 1.99→0.70) AND halved the
  trade count to 113 (< 200 floor) — double-jeopardy. SecondEntryORB is **strictly ADDITIVE**: the
  first-break entry is byte-for-byte the incumbent (a unit test pins this), so it can NEVER remove
  an incumbent winner; it only adds re-break trades on top. This is exactly the "mechanism that
  *adds* trades" the breakout-retest report's family-note prescribed as the only retest-adjacent
  idea worth a trial.
- **Not the rejected ≥2R exit sweep ([[2026-06-07-tp-2r-sweep]]).** That stretched the *target*.
  Here the exit geometry is *unchanged* from the incumbent (single 1R, 1.2×ATR floor) and the
  *entry count* changes. The pre-registered "why 1R fits here" (below) is grounded in the
  library's repeated finding that EURUSD M15 overlap rewards high-win-rate ~1R breakout structures
  — reconfirmed as recently as [[2026-06-12-trend-pullback-ema]].
- **Not a fade.** It trades *with* the breakout, so the closed Asian sweep-fade family's
  "mean-reversion is structurally negative" failure mode does not apply.

## Strategy spec
- **Session / regime / opening range / blackout:** unchanged from the incumbent (London 13:00–16:00,
  30-min OR, ER ≥ 0.30 + ATR-normal band, news blackout). Reuses `super()._regime` / `_blackout` /
  `_or_end` / `_london` / `warmup_bars`.
- **Levels:** `long_level = OR_high + buffer`, `short_level = OR_low − buffer` (buffer 1.5 pip).
- **Entry (the only change):** a pure **episode counter** over the post-OR session closes
  (`second_entry_breakout_trigger`). An *episode* = a maximal run of bars closing beyond the level;
  it *starts* on the first such bar (preceded by a non-beyond bar). The incumbent fires on episode 1
  only; this fires on the first bar of episodes 1…`max_entries_per_side` (=2). A second episode can
  only exist if price closed back **inside** the range between breaks (the first attempt "failed").
  Fires at most once per episode, on its first beyond-close — identical close-entry semantics to the
  incumbent. (`max_entries_per_side = 1` reproduces the incumbent exactly; a unit test pins this.)
- **Params → `ALLOWED_LEVERS` only if promoted:** `second_entry.max_entries_per_side` (1 = incumbent;
  2 = first break + one re-break). None swept here — single a-priori point.

**Exit geometry (spec 08 §5.8 — pre-registered; deliberately the incumbent's, WITH justification):**
- **stop = max(structural OR-edge, 1.2×ATR), target = single 1R, break-even after +1R** — the
  incumbent's validated machinery, reused *because the re-break is the same momentum-continuation
  mechanism as the first break* (same level, direction, session, regime). The library record
  ([[2026-06-07-tp-2r-sweep]], [[2026-06-12-trend-pullback-ema]]) shows this instrument/timeframe
  rewards high-win-rate ~1R breakout geometry and punishes low-win-rate high-R; a re-break shares
  that profile, so 1R is the geometry the mechanism *implies*, not an unexamined inheritance. This
  also makes the A/B isolate a single variable (allow episode 2) instead of confounding entry+exit.
- **Live-mirror needed? No.** `manage()` and the exit plan are byte-for-byte the incumbent's
  (already live-mirrored); only `evaluate` differs. `live == backtest` holds on the exit path.

## Implementation notes
Additive-only, dev-isolated (CLAUDE.md + spec 08 §5):
- `src/engine/indicators.py` — new pure `second_entry_breakout_trigger(closes, level, direction,
  max_entries) -> bool` (episode counter; fail-safe `False` on degenerate input / `max_entries < 1`).
- `src/engine/strategy_second_entry.py` — new `SecondEntryORB(SessionBreakoutER)`; overrides only
  `evaluate` and reuses `self._signal` verbatim. The incumbent class is **not modified**.
- `src/engine/registry.py` — one import + one `register("SecondEntryORB", …)` line.
- `tests/engine/test_second_entry.py` — 16 unit tests (episode counter: first-break-like-incumbent,
  2nd-blocked-at-max1, 2nd-fires-at-max2, mid-run continuation, current-not-beyond, 3rd-blocked,
  short mirror, degenerate; strategy: **first break byte-for-byte == incumbent**, 2nd fires where
  incumbent is silent, geometry == incumbent machinery, 3rd-episode-no-fire, max1-collapses-to-
  incumbent, stand-down, outside-session, registry build).
- **Full `python -m pytest -q`: green (306 passed).** No writes to `state/`, no live-path edits,
  ConfigStore untouched. Pure function of (bars, now, context_bias, calendar); every degraded path
  ⇒ `NoSignal`.

## Backtest results
Command: `py scripts/run_backtest.py --strategy SecondEntryORB --walkforward --trials 164`
(`--trials 164` = cumulative 163 from [[2026-06-12-trend-pullback-ema]] + this candidate).
Same data (`state/parquet/eurusd_m15.parquet`, 59,993 bars, 2024-01 → 2026-05), same governor /
costs / harness. A/B vs the incumbent HEAD v4 on the identical run.

| metric | gate | SecondEntryORB | incumbent HEAD v4 |
|---|---|---|---|
| trades (in-sample) | ≥ 200 | **252** ✓ | 224 ✓ |
| expectancy | ≥ 0.10R | **+0.266R** ✓ | +0.294R ✓ |
| win rate | — | 71.8% | 73.2% |
| profit factor | ≥ 1.3 | **1.84** ✓ | 1.99 ✓ |
| Sharpe (ann.) | ≥ 1.0 | **3.10** ✓ | 3.36 ✓ |
| Sortino | ≥ 1.5 | **4.70** ✓ | 5.36 ✓ |
| deflated Sharpe (trials=164) | ≥ 0.95 | **0.964** ✓ | 0.989 ✓ |
| FTMO breaches | 0 (hard) | 0 ✓ | 0 ✓ |
| max drawdown | — | $2,614 | **$1,883** (better) |
| net P&L | — | +$23,298 | +$22,875 |
| WF folds profitable | ≥ 60% | **6/7** ✓ (1 weak −0.081R) | 7/7 ✓ |
| WF stitched OOS | no collapse | +0.273R ✓ | +0.283R ✓ |
| WF severe fold | none < −0.25R | none ✓ | none ✓ |
| lockbox (2025-11→2026-05) | core gates PASS | **+0.248R, PF 1.75 PASS** ✓ | +0.324R, PF 2.15 PASS ✓ |
| **walk-forward verdict** | PASS | **PASS** ✓ | PASS ✓ |

Walk-forward folds (candidate): −0.081 / +0.266 / +0.433 / +0.339 / +0.384 / +0.470 / +0.177 R.
Walk-forward folds (incumbent): +0.013 / +0.209 / +0.390 / +0.290 / +0.343 / +0.507 / +0.233 R.

**Added-trade arithmetic.** Candidate 252 trades × +0.266R ≈ **+67.0 R** total; incumbent
224 × +0.294R ≈ **+65.9 R**. The 28 added re-break trades therefore contributed ≈ **+1.1 R**, i.e.
**≈ +0.04R each** — positive and above the cost line, but ~7× below the incumbent's +0.294R/trade.
They add gross return (+$423 net) while *raising* max drawdown by +$731 → worse return-per-unit-risk.

## Verdict
**Tested-passed — but DO NOT PROMOTE (dominated by the incumbent).** SecondEntryORB is the **first**
research-engine candidate to clear every R6 gate, the walk-forward, AND the sealed lockbox in
isolation. The additive hypothesis is **confirmed in its weak form**: re-break second entries are
genuinely (marginally) profitable, not noise. **However**, a pass is necessary but not sufficient —
the project bar (CLAUDE.md playbook §4) is that a candidate must also **beat the incumbent**, and
this one is dominated on every risk-adjusted axis (expectancy −0.028R, PF −0.15, Sharpe −0.26,
Sortino −0.66, DSR −0.025, max-DD +$731 worse, lockbox −0.076R / PF −0.40) and converts the
incumbent's clean 7/7 walk-forward into 6/7 with a mildly-negative 2024-Q1 fold.

This mirrors the **2026-06-08 weekly-sweep precedent** ([[weekly-sweep-2026-06-08]]): a clean
gate+lockbox pass that nonetheless trails HEAD OOS → *review, lean against promoting*. **Proposal
filed** (`config/proposals/2026-06-13-second-entry-orb.json`, status `proposed`) + promotion brief,
both flagged **do-not-promote**, for Cayden's human decision. Promotion remains human-only;
nothing was promoted. Trial ledger: +1 (`2026-06-13-second-entry-orb`, status `passed`); cumulative
trials now **164**; W24 budget **7/10** spent.

## Lessons
1. **Additive re-break ("second attempt") entries are a REAL but WEAK edge on EURUSD M15 overlap
   (~+0.04R/trade).** This is the first mechanism in the library to clear the arbiter, and it
   vindicates the *additive* research direction the rejection lessons prescribed: adding
   positive-expectancy trades beats subtracting the incumbent's winners (the [[2026-06-11-breakout-retest]]
   / [[2026-06-12-trend-pullback-ema]] anti-selection trap). "Second attempt after a failed first
   break" is not folk noise — the failed-break stop-flush does leave a small continuation edge.
2. **But marginal-positive additions DILUTE a high-quality incumbent — trade COUNT was never the
   binding constraint here.** The incumbent already cleared the 200-trade floor by 24; blending
   +0.04R trades into a +0.294R book lowers expectancy, PF, and Sharpe and raises drawdown. The
   trade-floor framing from prior rejections was a *necessary* lens but not the *operative* one once
   the floor is met: **per-trade quality, not quantity, is what beats HEAD.** Pad a great book with
   merely-okay trades and you get a slightly-worse book.
3. **"Passes-but-dominated" is a distinct verdict from the prior six "fails-the-arbiter" rejections.**
   The correct artifact is `tested-passed` + a proposal/brief flagged DO-NOT-PROMOTE, not a rejection
   — the strategy is *valid*, just not *better*. The sufficiency test is beating the incumbent, and
   the harness's PASS is necessary-only (CLAUDE.md invariant 2; [[weekly-sweep-2026-06-08]]).
4. **The edge could seed a SELECTIVE second-entry variant** — isolate only the *higher-quality*
   re-breaks (e.g. re-break only after a *shallow* first failure, or only in the top-ER regime). But
   any such filter is subtractive on the second-entry subset and re-enters the anti-selection trap;
   estimate the sub-subset frequency a priori before spending a trial (the recurring discipline).

## Next steps
- **Do not promote.** Proposal + promotion brief filed for Cayden; he decides. If he wants it:
  `py scripts/process_proposal.py config/proposals/2026-06-13-second-entry-orb.json --approve`
  (note: this is a *strategy-name* swap, not a lever diff — promote via `ConfigStore.promote` after
  review, not the auto-validator, since `name` is not an `ALLOWED_LEVER`).
- Possible follow-on (queued as `idea`, not yet tested): **QualityGatedSecondEntry** — the additive
  second entry restricted to its higher-quality subset. Frequency-estimate first (subtractive risk).
- The additive principle is now an explicit research heuristic: prefer ideas that *add*
  positive-expectancy trades; the bar to clear is **beating HEAD v4**, not merely passing the gates.
