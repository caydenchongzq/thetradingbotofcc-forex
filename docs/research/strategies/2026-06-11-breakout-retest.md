---
id: 2026-06-11-breakout-retest
name: BreakoutRetestER
family: breakout
status: tested-rejected
related: [2026-06-02-session-breakout-er, 2026-06-07-tp-2r-sweep, 2026-06-07-pre-session-compression-filter]
sources: ["https://forextester.com/blog/opening-range-breakout-trading-strategies/", "https://fxopen.com/blog/en/how-can-you-use-a-break-and-retest-strategy-in-trading/", "https://www.ebc.com/forex/break-and-retest-in-trading-step-by-step-strategy", "https://medium.com/@FMZQuant/advanced-multi-timeframe-breakout-retest-trading-strategy-eb1e669b6ed4", "https://tradeproacademy.com/intraday-trading-strategy-opening-range/"]
trials_used: 1
verdict: "Break-and-retest filter is ANTI-selective on this ORB: it discards the immediate-continuation winners and keeps the choppy whipsaws -> 113 trades (< 200 floor), -0.181R, PF 0.70, 2/7 WF folds, lockbox -0.102R PF 0.75 FAIL"
---

# BreakoutRetestER — enter the opening-range breakout only after a break → retest → resume

## Hypothesis & market rationale
The incumbent `SessionBreakoutER` enters on the bar that **closes** beyond the London/NY-overlap
opening-range level. A large body of practitioner literature claims that requiring a **retest**
of the broken level before entering filters out *false breakouts* and yields a higher-quality,
higher-win-rate entry on the same structure. The economic story: a genuine breakout sweeps stops
beyond the range, price often revisits the level as initiating flow is absorbed by fading
liquidity, and if the level then **holds** as new support/resistance the move is real and
trend-followers re-load. A false break closes back inside and is skipped.

Falsifiable claim tested here: *on EURUSD M15, restricting the incumbent's ORB to only those
breakouts that break → retest the level → resume in the breakout direction raises gated,
risk-adjusted performance (does not merely change the trade mix).*

## Sources
Hypothesis-only (the backtester is the arbiter); mined for mechanism, re-implemented pure, no
community code copied into `src/`:
- ForexTester — *Opening Range Breakout Trading Strategies* (retest as a second/conservative
  entry on the broken level). https://forextester.com/blog/opening-range-breakout-trading-strategies/
- FXOpen — *How can you use a break-and-retest strategy in trading?*
  https://fxopen.com/blog/en/how-can-you-use-a-break-and-retest-strategy-in-trading/
- EBC Financial Group — *Break and Retest in Trading: step-by-step* (EUR/USD cited as a clean
  break-retest instrument during high-liquidity sessions).
  https://www.ebc.com/forex/break-and-retest-in-trading-step-by-step-strategy
- FMZQuant (Medium) — *Advanced Multi-Timeframe Breakout-Retest Trading Strategy* (state-machine
  framing: break, retest, confirm). https://medium.com/@FMZQuant/advanced-multi-timeframe-breakout-retest-trading-strategy-eb1e669b6ed4
- TradeProAcademy — *How to Trade the Opening Range* (retest gives a second, defined-risk entry).
  https://tradeproacademy.com/intraday-trading-strategy-opening-range/

No peer-reviewed study quantifies break-retest edge in intraday FX; evidence tier is retail
practitioner blogs (low). Treated strictly as a hypothesis.

## Relation to prior library work
- Builds on the incumbent breakout family ([[2026-06-02-session-breakout-er]]): identical regime
  gate (ER ≥ thr + ATR-normal), session, and 30-min opening range. ONLY the entry trigger and
  exit geometry differ.
- It trades **with** the breakout, so it is NOT a fade — the **closed** Asian sweep-fade family
  ([[2026-06-08-asian-sweep-fade]], [[2026-06-10-asian-sweep-fade-rr]]) and its "mean-reversion is
  structurally negative" failure mode do not apply.
- It is NOT the rejected ≥2R exit sweep ([[2026-06-07-tp-2r-sweep]]): that kept the incumbent's
  close-entry and only stretched the **target** on a wide 1.2×ATR stop. Here the **entry** changes
  (post-retest) and the **stop** is tighter (1.0×ATR), so 1.5R is a smaller absolute move than the
  rejected ≥2R-on-1.2×ATR geometry — the R-multiples are not comparable and that failure mode is
  not inherited.
- It is NOT a subtractive *filter* layered on the incumbent's signals (the gate-blocked
  compression family, [[2026-06-07-pre-session-compression-filter]]): it is a different entry
  **mechanism**. But it shares that family's **risk** — its own trade count is its own, and the
  retest requirement could push below the 200-trade floor. (It did — see results.)

## Strategy spec
- **Session / regime / opening range:** unchanged from the incumbent (London 13:00–16:00, 30-min
  OR, ER ≥ 0.30 + ATR-normal band, news blackout). Reuses `super()._regime` / `_blackout` /
  `_or_end` / `_london`.
- **Levels:** `long_level = OR_high + buffer`, `short_level = OR_low − buffer` (buffer 1.5 pip,
  as incumbent).
- **Entry (the change):** a pure three-state machine over the post-OR session bars
  (`breakout_retest_trigger`): (1) a bar **closes** beyond the level (break); (2) a later bar's
  **low** (long) / **high** (short) returns to/through the level (retest); (3) a bar **closes**
  back beyond the level (resume) → enter at that bar's **close** (honest market fill, spread +
  slippage applied by the cost model). One-shot per side; the break bar can never be the entry
  bar; a single wick-retest that closes back beyond the level is a valid immediate entry.
- **Params** (would become `ALLOWED_LEVERS` only if promoted; none swept here — single a-priori
  point): `retest.atr_mult_sl = 1.0`, `retest.target_r = 1.5`.

**Exit geometry (spec 08 §5.8 — chosen per mechanism, NOT inherited):**
- **stop = 1.0×ATR.** A retest that holds defines the line in the sand; if price travels ~1 ATR
  against a confirmed retest entry the thesis is void. Tighter than the incumbent's 1.2×ATR
  because the confirmed retest is supposed to be a lower-risk entry.
- **target = 1.5R (R:R = 1:1.5).** Breakouts have a sub-50% win rate, so reward must exceed risk;
  1.5R sits above the 1:1 floor and below the rejected ≥2R territory, and on the tighter stop it
  is a modest, reachable follow-through, not a home-run TP.
- **Single target, no partials, NO break-even move** (`move_be_after_r = None`) → pure broker
  stop / take-profit. Deliberately introduces **no new `manage()` semantic** vs the incumbent, so
  the candidate needs **no live-mirror session** (cf. [[2026-06-09-late-session-drift]]):
  `live == backtest` already holds.

## Implementation notes
Additive-only, dev-isolated (CLAUDE.md + spec 08 §5):
- `src/engine/indicators.py` — new pure `breakout_retest_trigger(highs, lows, closes, level,
  direction) -> bool` (state machine; fail-safe `False` on degenerate input).
- `src/engine/strategy_breakout_retest.py` — new `BreakoutRetestER(SessionBreakoutER)`; replaces
  `evaluate`, reuses the incumbent's pure machinery; the incumbent class is untouched.
- `src/engine/registry.py` — one import + one `register("BreakoutRetestER", …)` line.
- `tests/engine/test_breakout_retest.py` — 13 unit tests (trigger state machine: long/short,
  one-shot, no-retest, false-break, break-bar-never-entry, degenerate; strategy: geometry,
  not-1.2×ATR, no-retest→NoSignal, outside-session, stand-down, registry build).
- Full `python -m pytest -q`: **green** (282 passed). No writes to `state/` or the live path
  (`run.py`, `decide.py`, execution, risk) during the build. Live-mirror needed? **No.**

## Backtest results
Command: `py scripts/run_backtest.py --strategy BreakoutRetestER --walkforward --trials 162`
(`--trials 162` = cumulative 161 from [[2026-06-10-asian-sweep-fade-rr]] + this candidate).
Same data (`state/parquet/eurusd_m15.parquet`, 59,993 bars, 2024-01 → 2026-05), same governor /
costs / harness. A/B vs the incumbent HEAD (v4) on the identical run.

| metric | gate | BreakoutRetestER | incumbent HEAD v4 |
|---|---|---|---|
| trades (in-sample) | ≥ 200 | **113** ✗ | 224 ✓ |
| expectancy | ≥ 0.10R | **−0.181R** ✗ | +0.294R ✓ |
| win rate | — | 43.4% | 73.2% |
| profit factor | ≥ 1.3 | **0.70** ✗ | 1.99 ✓ |
| Sharpe (ann.) | ≥ 1.0 | **−1.26** ✗ | 3.36 ✓ |
| Sortino | ≥ 1.5 | **−1.60** ✗ | 5.36 ✓ |
| deflated Sharpe (trials=162) | ≥ 0.95 | **0.000** ✗ | 0.989 ✓ |
| FTMO breaches | 0 (hard) | 0 ✓ | 0 ✓ |
| net P&L | — | −$7,076 | +$22,875 |
| WF folds profitable | ≥ 60% | **2/7** ✗ | 7/7 ✓ |
| WF stitched OOS | no collapse | −0.209R | +0.283R |
| lockbox (2025-11→2026-05) | core gates PASS | **−0.102R, PF 0.75 FAIL** ✗ | PASS |

Walk-forward folds (candidate): −0.294, −0.100, −0.770, +0.172, +0.168, −0.611, −0.159 R — only
the two calmer late-2024/early-2025 folds are positive; the trending 2025 folds (where the
incumbent earns +0.34…+0.51R) are sharply **negative** for the retest variant.

## Verdict
**Tested-rejected.** Fails 6 of 7 R6 gates in-sample, fails the walk-forward (2/7 folds,
stitched −0.209R), and fails the sealed lockbox (−0.102R, PF 0.75). Strictly dominated by the
incumbent on every axis. **No proposal filed** (`config/proposals/` untouched; promotion is
human-only and there is nothing to promote). Trial ledger: +1 (`2026-06-11-breakout-retest`,
status `failed`); cumulative trials now 162; W24 budget 5/10 spent.

## Lessons
The break-and-retest "quality filter" is **anti-selective** for this ORB on EURUSD M15: it throws
away the trades that carry the edge.

1. **The incumbent's edge lives in immediate continuation, not in the retest subset.** The
   incumbent wins **73%** of breakouts at +0.29R — that profile is dominated by breakouts that
   *run away without looking back*. Requiring a retest **excludes exactly those winners** and
   keeps the slower, choppier breakouts that stall and revisit the level. What survives the
   filter (win rate collapses 73% → 43%, PF 1.99 → 0.70) is the **whipsaw residue**. "Wait for
   the retest" is folk wisdom that inverts the selection on a strategy whose alpha is momentum
   follow-through.
2. **It also halves the sample (224 → 113), failing the 200-floor on its own** — the same
   trade-count headroom problem the compression-filter family hit
   ([[2026-06-07-pre-session-compression-filter]]). Any mechanism that *removes* incumbent
   breakouts starts ~24 trades over the floor and rarely survives.
3. **A tighter stop did not help a thesis with no edge.** The 1.0×ATR stop was justified a-priori
   for a "confirmed, lower-risk" entry, but on the choppy survivors it noise-outs — geometry can't
   rescue a negative-expectancy entry subset (the recurring lesson, cf. the exit-model and ≥2R
   rejections; judge on gates+lockbox, never raw expectancy).
4. **Process win:** the candidate needed no live-mirror flag (pure stop/TP exit, no new `manage()`
   semantic) — a cleaner shape than [[2026-06-09-late-session-drift]]. The rejection is about the
   entry edge, not execution mechanics.

Family note for triage: **breakout *entry-timing* variants that subset the incumbent's breakouts
are double-jeopardy** (trade-count floor + anti-selection of the momentum winners). Do not re-test
retest/pullback entry timing on this ORB without a mechanism that *adds* trades or selects a
*different, positive* breakout subset — not one that filters the incumbent's down.

## Next steps
- Queued (untested) ideas from this run's research, recorded in INDEX as `idea`:
  - **TrendPullbackEMA** (trend family) — enter a *fresh* shallow pullback to a fast EMA in an
    ER-confirmed trend (a NEW signal source, not a subset of incumbent breakouts → sidesteps the
    anti-selection + trade-floor trap above). Distinct from the rejected trend probes
    ([[2026-06-07-intraday-ts-momentum]] = serial-corr momentum; [[2026-06-09-late-session-drift]]
    = time-of-day drift): this is a structural retracement pattern.
  - **VWAPStretchReversion** (mean-reversion) — fade a large session-VWAP stretch (no sweep);
    different mechanism from the closed sweep-fade family. Risk: mean-reversion family scrutiny +
    trade count; estimate frequency before testing.
  - **SecondEntryORB** (breakout, *additive*) — keep the incumbent's close-entry AND add a
    re-break second entry after a first stop-out, to *raise* trade count rather than cut it (the
    inverse of this candidate). The only retest-adjacent idea worth testing, because it is additive.
- No data needs (all EURUSD M15).
