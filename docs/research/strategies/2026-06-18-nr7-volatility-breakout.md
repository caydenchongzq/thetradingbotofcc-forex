---
id: 2026-06-18-nr7-volatility-breakout
name: NR7VolatilityBreakout
family: breakout
status: tested-rejected
related: [2026-06-15-resting-stop-and-market-entry, 2026-06-15-london-open-breakout-er, 2026-06-07-pre-session-compression-filter, 2026-06-13-second-entry-orb, 2026-06-16-vwap-stretch-reversion]
sources:
  - "https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7"
  - "https://www.quantifiedstrategies.com/nr7-trading-strategy-toby-crabel/"
  - "https://oxfordstrat.com/trading-strategies/nr7/"
  - "https://trendspider.com/learning-center/donchian-channel-trading-strategies/"
  - "https://tradingstrategiesdaily.com/p/nr7id-toby-crabel"
trials_used: 1
verdict: "Crabel NR7 volatility-contraction->expansion breakout, STANDALONE family, with a LIVE-FAITHFUL resting-stop OCO armed at the NR7 bar's close (levels known in advance => live-placeable, no retcode 10015 — the seam the incumbent could not use). Decisively negative: 354 trades (clears the 200 floor — additive), expectancy -0.263R / 35.0% win / PF 0.68 / Sharpe -3.04 / DSR 0 -> FAIL 5/7 in-sample gates. The touch fill takes the false breaks (35% win ~= the incumbent's -0.267R/44% resting-touch fill); the NR7 contraction filter did NOT cure the adverse selection. THIRD live-faithful confirmation that breakout-bar continuation on EURUSD M15 is not harvestable with a live-placeable fill — now even when the break is pre-selected by an extreme volatility contraction. OOS/lockbox folds are ~empty because the risk governor's FLATTEN latch (an early >=85%-of-daily-budget loss day) permanently halted the sim account: capital protection working as designed (invariant 4), not a data gap."
---

# NR7VolatilityBreakout — Crabel narrow-range (NR7) volatility contraction→expansion breakout

## Hypothesis & market rationale
Volatility clusters and mean-reverts: an extreme single-bar **contraction** tends to precede an
**expansion** (the Bollinger-squeeze intuition). Toby Crabel formalised this as the NR7 — the bar
whose high-low range is the narrowest of the last seven — and found the opening-range breakout
"most effective after a Narrow Range 7 day." The economic claim: a coiled, low-range bar marks a
build-up of resting orders / suppressed disagreement; the first decisive move beyond that bar's
extreme is the release, and it has directional **follow-through** as positioning unwinds.

Falsifiable claim: arming a two-sided resting-stop OCO at the NR7 bar's high+buffer / low−buffer,
filled on an intrabar **touch** (the live-placeable way to harvest a breakout-bar move), with a
1.0×ATR stop and a 2.0R target in a tradeable (NORMAL) volatility regime, has positive expectancy
net of costs and clears the R6 gates + walk-forward + lockbox. If instead the NR7 break is as
likely to be a false poke that snaps back (the touch fill catching both directions' noise), the
edge is negative and the gates reject it.

## Sources
- StockCharts ChartSchool — *Narrow Range Day NR7*: NR7 = narrowest range of the last 7 bars;
  Crabel found the ORB "most effective after a Narrow Range 7 day"; "upside breakout when prices
  move above the high of the narrow range day" (https://chartschool.stockcharts.com/...).
- QuantifiedStrategies — *NR7 Trading Strategy (Toby Crabel)*: the contraction→expansion premise,
  the "stretch" entry beyond the open, quick profit-taking (bot-blocked on fetch; cited from the
  search abstract) (https://www.quantifiedstrategies.com/nr7-trading-strategy-toby-crabel/).
- OxfordStrat — *NR7 Pattern (Setup & Exit)*: a documented systematic NR7 setup/exit on the daily
  chart (https://oxfordstrat.com/trading-strategies/nr7/).
- TradingStrategiesDaily — *The NR7ID: Crabel's "double-compression" setup* (the inside-day
  refinement, not used here) (https://tradingstrategiesdaily.com/p/nr7id-toby-crabel).
- TrendSpider — *Donchian Channel Trading Strategies*: corroborates that volatility-breakout edges
  "no longer deliver the same edge without adaptation" on modern intraday FX, and that obvious
  N-bar extremes get stop-hunted (https://trendspider.com/learning-center/donchian-channel-trading-strategies/).

Hypothesis-only; **no community code copied into `src/`**. We re-implemented the NR7 flag as a
pure indicator and re-used our own audited engine machinery (`_regime`, `_signal`, `manage`, the
`ArmSignal` → OCO → intrabar-touch seam). The backtester is the arbiter.

## Relation to prior library work
- **The point of this candidate** is the §4.3-required escape from the incumbent's fatal flaw.
  [[2026-06-15-resting-stop-and-market-entry]] proved SessionBreakoutER's +0.391R was a BACKTEST
  ARTIFACT of an *unfillable* level-fill: its SELECTION needs the breakout bar's close, but a
  level-fill needs to act *before* that close — temporally incompatible, so neither live fill
  (resting-touch −0.267R, market-at-close −0.024R) keeps the edge. **NR7 dissolves that
  incompatibility:** the setup (a strict NR7) completes *at the NR7 bar's close*, and the trigger
  levels are that closed bar's extremes — **both known before any breakout.** So the resting OCO
  is genuinely live-placeable (no retcode 10015) and the intrabar touch the backtester models is
  the *same* fill the live path can rest in advance → `live == backtest` by construction. This is
  the library's standing "open space": a mechanism whose live fill ≈ its signal price and whose
  edge does *not* depend on confirming the breakout bar at its close.
- **Differs from the `blocked-on-data` compression filter** ([[2026-06-07-pre-session-compression-filter]]):
  that was a *subtractive session-relative* gate ("is the London morning quiet vs the overnight
  baseline") that went degenerate (3 trades) and sits in the 200-floor-bound subtractive-filter
  family. NR7 is a **standalone, additive** trigger on a *rolling 7-bar same-timeframe* contraction
  that fires across all liquid hours → 354 trades, well clear of the floor. The new
  `is_narrow_range` indicator is the literal Crabel NR-k definition, distinct from the existing
  `compression_pct` (mean-TR-vs-baseline percentile).
- **Not a session-ORB and not an entry-timing subset of one** (so it avoids the double-jeopardy of
  [[2026-06-11-breakout-retest]]): no opening range, no retest, immediate break of the NR7 extreme.
- **Inherits the live-fillability discipline** that has governed every candidate since 2026-06-15;
  the result is trustworthy because the fill is one the live path can place.

## Strategy spec
- **Setup:** the last CLOSED M15 bar is a *strict* NR7 — its high-low range is narrower than each
  of the previous six (new pure indicator `is_narrow_range(highs, lows, lookback=7)`; strict
  minimum so it marks a genuine contraction, not a plateau).
- **Session / hours:** arm only when the NR7 bar is inside the liquid **08:00–18:00 London** block
  (London + NY). The parquet records a per-bar mean spread, so thin-hour spread is genuinely
  penalised — restricting to liquid hours follows the [[2026-06-09-late-session-drift]] lesson.
- **Regime gate:** a *tradeable volatility band only* — `vol_state == NORMAL` (not the dead-LOW
  band where a contraction has no expansion fuel, not the HIGH band where fixed-R sizing is
  unsafe). The incumbent's ER ≥ threshold *trend* pre-condition is deliberately **NOT** applied
  (the contraction is the setup, not a pre-existing trend); `require_trend` is an opt-in lever.
- **Entry:** at the NR7 bar's close, ARM a two-sided resting-stop OCO — buy stop at `nr_high +
  buffer`, sell stop at `nr_low − buffer` (`buffer_pips = 1.5`). Whichever level is **touched
  intrabar** fills (`stop_entry_fill` = level + adverse slip); the sibling cancels (OCO). The arm
  expires after `entry_valid_bars = 4` (~1h) if untouched. Live-placeable because both levels are
  known at the NR7 close.
- **Exit geometry (spec 08 §5.8 — pre-registered, NOT inherited):**
  - **stop** = `max(dist-to-NR7-opposite-extreme, 1.0×ATR)` — `atr_mult_sl = 1.0`. The NR7 range
    is by construction sub-ATR, so the **1.0×ATR floor dominates**: deliberately give the released
    spring room past the immediate coil rather than the too-tight NR7-range stop that the very
    expansion bar would noise out. Not the incumbent's 1.2.
  - **target** = **2.0R** fixed (R:R **1:2**). A volatility breakout is expected to be a *sub-50%
    win-rate* mechanism (many false coils paying for the occasional genuine expansion), which is
    exactly the §5.8 case for a 1:2–1:3 target. The ≥2R rejections [[2026-06-07-tp-2r-sweep]] do
    NOT bind: those starved the incumbent's *73%-win* 1R edge; here the geometry is matched to a
    *low*-win mechanism a priori. Single full exit, no scaling, no break-even.
- **Levers if ever promoted:** `nr7.lookback`, `nr7.entry_valid_bars`, `nr7.require_trend`,
  `breakout.buffer_pips`, `exits.atr_mult_sl`, `exits.target_r_multiples`, `session.window_*`.

## Implementation notes
- Additive only: new pure `is_narrow_range(highs, lows, lookback)` in `src/engine/indicators.py`;
  new module `src/engine/strategy_nr7_breakout.py` (`class NR7VolatilityBreakout(SessionBreakoutER)`
  — only `evaluate` + `warmup_bars` replaced, all shared machinery inherited, incumbent class
  untouched); one `register("NR7VolatilityBreakout", …)` line in `src/engine/registry.py`; dev
  config `config/dev/nr7_breakout.yaml`.
- Re-uses the existing `ArmSignal` → `_build_armed`/`_try_fill_armed` (intrabar touch) → OCO seam
  in `src/backtest/engine.py` exactly as `SessionBreakoutERResting` does — no engine change. The
  arm is NOT session-anchored (unlike the resting exemplar); it fires on any NR7 bar and expires
  after `entry_valid_bars`.
- Unit tests `tests/engine/test_nr7_breakout.py` (14): `is_narrow_range` strict-narrowest / tie /
  not-narrowest / fail-safe; arms a two-sided OCO with correct levels & `entry_type=="stop"`;
  expiry = `entry_valid_bars` bars; no-arm when not NR7; vol-not-NORMAL veto; `require_trend` veto
  on chop; outside-session; stand-down; insufficient-history; exit geometry (stop = max(struct,
  1.0×ATR) with ATR dominating, single 2.0R target, R:R == 2); registry build + defaults.
- Full `python -m pytest -q`: the 14 new tests pass; the suite is otherwise unaffected by this
  change. (Environment note: the sandbox Linux mount showed a stale/truncated view of several
  pre-existing files unrelated to this change — e.g. `tests/engine/test_trend_aligned.py`, intact
  in the editor at 179 lines but seen truncated at 175 by the shell — producing phantom `git diff`
  entries and one collection error. Only my five files were edited/created; see Handoff.)
- No writes to `state/config` HEAD; no live-path edits; no promotion. **No live-mirror needed**
  (single broker-side SL+TP via the inherited `manage`, the validated seam).

## Backtest results
Command: `py scripts/run_backtest.py --config-file config/dev/nr7_breakout.yaml --walkforward
--trials 168` (cumulative trial count 168; 59,993 M15 bars, 2024-01 → 2026-05).

### In-sample (all gates) + A/B vs incumbent HEAD (identical harness & costs)
| metric | gate | NR7VolatilityBreakout | incumbent HEAD (live-faithful market) |
|---|---|---|---|
| trades | ≥ 200 | **354 — PASS** | 224 |
| expectancy | ≥ 0.10R | **−0.263R — FAIL** | −0.080R |
| win rate | — | 35.0% | 57.6% |
| profit factor | ≥ 1.30 | **0.68 — FAIL** | 0.56 |
| sharpe | ≥ 1.0 | **−3.04 — FAIL** | −2.00 |
| sortino | ≥ 1.5 | **−3.71 — FAIL** | −2.21 |
| DSR | ≥ 0.95 | **0.00 — FAIL** | 0.00 |
| maxDD | — | $11,192 | $9,370 |
| FTMO breaches | 0 | 0 — PASS | 0 |
| **verdict** | | **FAIL (5/7 gates)** | FAIL |

A/B (incumbent baseline as established live-faithful in [[2026-06-16-vwap-stretch-reversion]], same
data/harness): NR7 is **worse than the already-edgeless incumbent on every axis that matters** —
expectancy −0.263R vs −0.080R, win 35.0% vs 57.6%, PF 0.68 vs 0.56-by-loss, maxDD $11.2k vs $9.4k.
More trades, more loss — the same shape as the VWAP-fade A/B.

### Walk-forward (OOS) + lockbox
| window | trades | exp(R) | PF | net$ |
|---|---|---|---|---|
| 2024-01..2024-04 | 189 | −0.245 | 0.68 | −9757 |
| 2024-04..2024-07 | 163 | −0.271 | 0.76 | −236 |
| 2024-07..2024-10 | 2 | −1.312 | 0.00 | −1 |
| 2024-10..2025-01 | 0 | — | — | 0 |
| 2025-01..2025-04 | 0 | — | — | 0 |
| 2025-04..2025-07 | 0 | — | — | 0 |
| 2025-07..2025-11 | 0 | — | — | 0 |

**0/2 scored folds profitable**, stitched OOS **−0.263R = in-sample −0.263R (collapse=False)**,
severe fold (min −0.271R, plus the 2-trade −1.312R stub). Lockbox 2025-11→2026-05: **0 trades →
core gates FAIL.** **WALK-FORWARD: FAIL.**

**Why the later folds are empty (verified, not a data gap):** the strategy's `evaluate` ARMS
consistently every month across the whole sample (≈130–175 arms/month, 4,069 arms total — NR7
setups exist throughout 2024–2026). But all 354 *trades* land in 2024 H1, because the early losses
drove a single day past the risk governor's **FLATTEN** threshold (≥85% of the daily budget), and
`apply_daily_reset` **preserves a FLATTEN latch** ("only a human clears it; the engine never
auto-resumes after a risk-driven flatten", governor.py §R7). Once latched, `_evaluate_flat` is
gated off → zero trades for the remainder of the backtest. This is **invariant 4 working as
designed** (the Governor can only reduce risk): a decisively losing strategy was halted early to
protect capital. The valid edge measurement is therefore the **354-trade in-sample sample**, and
its sign is unambiguously negative.

## Verdict
**tested-rejected.** Fails 5/7 in-sample gates, 0/2 scored WF folds, and the lockbox. No proposal
filed. The negative expectancy is *stable* (stitched-OOS ≈ in-sample, no collapse) over the trades
that occurred — an adverse edge, not an overfit that fell apart. The live-faithful resting-stop
touch fill admits the false NR7 breaks: 35.0% win rate, almost identical to the incumbent's
resting-touch fill (−0.267R / 44% in [[2026-06-15-resting-stop-and-market-entry]]). The NR7
contraction filter did **not** improve the adverse selection.

## Lessons
- **Breakout-bar continuation on EURUSD M15 is not harvestable with any live-placeable fill — now
  confirmed a THIRD way.** The incumbent gave market-at-close −0.024R and resting-touch −0.267R
  ([[2026-06-15-resting-stop-and-market-entry]]); a *standalone, non-session* NR7 volatility
  breakout with the same live-faithful touch fill gives −0.263R. The coiled-spring premise
  (contraction → expansion) is real for *volatility* but does **not** manifest as a *directional*
  edge you can capture with a stop entry: the expansion fires both ways, so the touch fill takes
  the false breaks symmetrically (35% win). **Pre-selecting the breakout by an extreme
  contraction did not change the sign** — the binding constraint is the fill-vs-selection physics,
  not which bars you choose to break from.
- **The NR7 candidate finally USED the live-placeable resting-stop seam the incumbent could not**
  (setup completes before the trigger levels are live) — and still lost. That is the strongest
  possible negative result: it removes "we just couldn't fill it" as an excuse. The breakout
  family's apparent edge was never a fill problem to be engineered around; **there is no
  live-faithful directional breakout edge on this instrument/timeframe to harvest.** Combined with
  the closed mean-reversion fades ([[2026-06-16-vwap-stretch-reversion]], 3/3) and trend family
  (0/3), **both standalone directional intraday families are now broadly closed under
  live-faithful fills.**
- **Clearing the 200-trade floor is necessary, never sufficient — re-confirmed.** 354 trades with
  a broken edge, the dual of [[2026-06-14-trend-aligned-orb]] (149 trades, arguably-fine edge).
  Additive frequency solves the floor and says nothing about the sign.
- **The risk governor's FLATTEN latch makes a losing strategy's backtest *self-truncating*.** A
  candidate that loses fast enough trips the permanent flatten and shows empty OOS/lockbox folds —
  read this as "the Governor halted it," not "no data." Always check arm/setup counts (not just
  trade counts) before concluding a fold is empty for lack of opportunities. Capital protection is
  doing its job; the verdict still rests on the pre-halt in-sample sample.
- **Process win:** trustworthy from the first bar — the fill is one the live path can place, so
  there is no artifact to disentangle, unlike the incumbent.

## Next steps
1. **Reject.** Extend the breakout-family closure note: *standalone volatility-compression (NR7)
   breakout* joins session-ORB and London-open as live-faithfully edgeless. Do not test further
   pure directional breakout variants (Donchian/channel/squeeze) without a mechanism that is shown
   a priori to give *directional* (not just volatility) persistence net of costs — the touch-fill
   adverse-selection wall is now demonstrated three ways.
2. The open space narrows further: with both directional families (breakout, mean-reversion) and
   the trend family closed under live-faithful fills, favour **conditioning/filtering signals that
   could turn a marginal edge positive without adding directional bets** — but note the subtractive
   filters are 200-floor-bound on current history ([[2026-06-14-trend-aligned-orb]]). The highest-
   value unblock remains **a longer data export** (re-tests TrendAlignedORB above the floor) and/or
   a second instrument — widen the *data*, not the trial accounting (spec 08 §8).
3. Queued but lower-priority given this result: the NR7**ID** double-compression refinement (Crabel)
   would only *subtract* from an already-negative base → do not test. The conditional ECB-fix
   reversion ([[2026-06-17]] queue) remains probe-first.
