---
id: 2026-06-14-trend-aligned-orb
name: TrendAlignedORB
family: filter
status: tested-rejected
related: [2026-06-02-session-breakout-er, 2026-06-07-pre-session-compression-filter, 2026-06-11-breakout-retest, 2026-06-13-second-entry-orb, 2026-06-12-trend-pullback-ema]
sources: ["https://www.litefinance.org/blog/for-beginners/trading-strategies/opening-range-breakout-strategy/", "https://forextester.com/blog/opening-range-breakout-trading-strategies/", "https://fbs.com/fbs-academy/traders-blog/opening-range-breakout-trading-strategy", "https://www.quantifiedstrategies.com/london-breakout-strategy/", "https://capital.com/en-int/learn/trading-strategies/breakout-trading"]
trials_used: 1
verdict: "Trend-alignment veto is GENUINELY pro-selective and OOS-robust — it lifts every quality axis above HEAD (win 73.2%->76.5%, PF 1.99->2.40, exp +0.294R->+0.359R, maxDD $1883->$958 HALVED, lockbox +0.324R/PF2.15->+0.493R/PF3.77, 7/7 WF folds profitable, no collapse) — but cuts the incumbent's 224-trade base by a THIRD to 149, FAILING the 200-trade hard sample_size gate. Single-jeopardy (trade-floor only, NOT anti-selection): the inverse of [[2026-06-11-breakout-retest]]. Un-harvestable on current history; the strongest candidate yet to re-test on a longer export. REJECTED on sample_size."
---

# TrendAlignedORB — veto incumbent breaks that fight the higher-timeframe trend

## Hypothesis & market rationale
The incumbent `SessionBreakoutER` takes the London/NY-overlap opening-range break in **either**
direction whenever its ER/ATR regime gate passes; it never asks whether the break runs *with* or
*against* the prevailing multi-day drift. Practitioner ORB literature is near-unanimous that
breakouts aligned with the higher-timeframe trend follow through more reliably, while
counter-trend breaks are a disproportionate share of the false breaks that snap back into the
range. **Falsifiable claim:** the incumbent's losing trades are disproportionately *counter-trend*
breaks, so vetoing them raises win rate / PF / risk-adjusted return. The economic story: in the
overlap, trend-aligned breaks attract continuation flow (stops + momentum in the same direction
as the standing positioning), whereas counter-trend breaks more often run into resting liquidity
and mean-revert.

## Sources
Hypothesis sources (the backtester, not the source, is the arbiter):
- LiteFinance — ORB rules/indicator/success rate (trend-filter & MA-direction filter section).
- ForexTester — ORB strategy (session-specific ranges, false-break rate in low-vol).
- FBS — open-range breakout (higher-timeframe alignment as the primary filter).
- QuantifiedStrategies — London Breakout backtest (40–60% raw success without filters).
- Capital.com — breakout trading (trend-aligned breaks vs counter-trend false breaks).

All are practitioner/educational; none is a peer-reviewed effect size. They motivate the
*direction* of the test only; the magnitude is what we measured.

## Relation to prior library work
- Builds the filter the incumbent ([[2026-06-02-session-breakout-er]]) deliberately omits.
- **Not a repeat of the trend-family rejections** ([[2026-06-12-trend-pullback-ema]],
  LateSessionDrift, IntradayTSMomentum): those failed because their *entry* was a low-win-rate
  trend mechanism. TrendAlignedORB introduces **no new entry** — it reuses the incumbent's
  73%-win 1R break verbatim and only *vetoes* a subset. The recorded failure mode (a weak entry)
  cannot apply: there is no new entry.
- **Not the compression filter** ([[2026-06-07-pre-session-compression-filter]]): that was a
  *volatility-timing* veto that went degenerate (3 trades). This is a *directional* veto on a
  different axis. But it lands on the **same structural wall** — see Lessons.
- **Inverse of [[2026-06-11-breakout-retest]]:** that subtractive filter was anti-selective
  (discarded the 73%-win immediate-continuation winners) *and* fell below the floor =
  double-jeopardy. This filter is the opposite — it is genuinely *pro*-selective (quality rises
  on every axis) and fails *only* the floor = single-jeopardy.
- **Inverse of [[2026-06-13-second-entry-orb]]:** that candidate passed the gates but was
  *dominated* by HEAD on quality. This one *dominates* HEAD on quality but fails a gate. Together
  they bracket the problem: on this dataset you can have HEAD-beating quality OR a passing trade
  count, not both.

## Strategy spec
Identical to the incumbent in every respect (session 13:00–16:00 London, 30-min opening range,
stop-order entry at range ± 1.5-pip buffer, ER(14) ≥ 0.32 + ATR-normal regime gate, news
blackout, one-shot per side), with **one added veto** applied *after* the incumbent produces a
signal:

- Compute a higher-timeframe trend sign from the M15 closes: `trend = sign( EMA(ema_window)[-1] −
  EMA(ema_window)[-1 − slope_lookback] )`.
- If the incumbent fires **long** and `trend ≤ 0`, or fires **short** and `trend ≥ 0`, veto →
  `NoSignal` (`trend_misaligned`, or `trend_unconfirmed` when the slope is exactly flat /
  history is short). Otherwise pass the incumbent signal through **byte-for-byte**.

Params (chosen a priori, deliberately **not** swept — sweeping would burn trials and p-hack the
floor): `trend_filter.ema_window = 96` (~1 trading day of M15 bars → a daily-trend proxy),
`trend_filter.slope_lookback = 16` (~4 h → slope must be non-flat in the trade direction). If
ever promoted these two would become `ALLOWED_LEVERS`.

**Exit geometry (spec 08 §5.8 — pre-registered):** stop `max(structural box, 1.2×ATR)`, target
single 1.0R 100%-out (R:R 1:1), break-even per incumbent — all **unchanged**. Rationale: this is
a pure entry *filter*; to measure a filter you hold geometry fixed. The surviving trades *are* the
incumbent's own high-win-rate ~1R breaks, so the incumbent's validated single-1R machinery is
exactly right, and reusing it makes the A/B a clean one-variable test. Changing R here would
confound the filter's effect with an exit change (and the library twice rejected ≥2R on this
mechanism: [[2026-06-07-tp-2r-sweep]]).

## Implementation notes
Additive only. New pure indicator `ema_slope_sign(values, window, lookback)` in
`src/engine/indicators.py`; new strategy `src/engine/strategy_trend_aligned.py`
(`class TrendAlignedORB(SessionBreakoutER)` — subclass, overrides only `__init__` /
`warmup_bars` / `evaluate`, delegating the entire entry decision to `super().evaluate` so no
incumbent logic is duplicated and it cannot drift); one `register("TrendAlignedORB", …)` line in
`src/engine/registry.py`. Unit tests `tests/engine/test_trend_aligned.py` (14: indicator
up/down/flat/short-history/degenerate; strategy aligned-passthrough = byte-identical to incumbent,
misaligned-veto both directions, subset invariant across all four warmup×break combos, extended
warmup, stand-down, outside-session, registry build). **Full `python -m pytest -q` green (320
tests).** No writes to `state/config/`, no live-path edits. **Live-mirror needed? NO** — `manage`
and the exit plan are byte-for-byte the incumbent's; only `evaluate` adds a veto, so
`live == backtest` already holds.

## Backtest results
Command: `py scripts/run_backtest.py --strategy TrendAlignedORB --walkforward --trials 165`
(`--trials 165` = cumulative 164 from [[2026-06-13-second-entry-orb]] + this candidate).
A/B: `py scripts/run_backtest.py --strategy SessionBreakoutER --walkforward --trials 165`.

| metric | gate | TrendAlignedORB | incumbent HEAD v4 |
|---|---|---|---|
| trades (in-sample) | ≥ 200 | **149** ✗ | 224 ✓ |
| expectancy (R) | ≥ 0.10 | +0.359 ✓ | +0.294 ✓ |
| profit factor | ≥ 1.30 | 2.40 ✓ | 1.99 ✓ |
| win rate | — | 76.5% | 73.2% |
| Sharpe (ann.) | ≥ 1.0 | 3.32 ✓ | 3.36 ✓ |
| Sortino | ≥ 1.5 | 5.49 ✓ | 5.36 ✓ |
| maxDD ($) | — | **958** | 1883 |
| net ($) | — | 18,161 | 22,875 |
| deflated Sharpe (trials=165) | ≥ 0.95 | 0.988 ✓ | — |
| FTMO breaches | 0 | 0 ✓ | 0 ✓ |
| **in-sample verdict** | all gates | **FAIL (sample_size)** | PASS |
| WF folds profitable | ≥ 60% | 7/7 ✓ | 7/7 ✓ |
| stitched OOS exp (R) | no collapse | +0.304 (no collapse) ✓ | +0.283 ✓ |
| min fold (R) | ≥ −0.25 | +0.138 ✓ | +0.013 ✓ |
| lockbox trades | — | 43 | 60 |
| lockbox exp / PF | core-gates PASS | +0.493R / 3.77 ✓ | +0.324R / 2.15 ✓ |
| **walk-forward verdict** | — | **FAIL (in-sample sample_size)** | PASS |

Every per-trade and risk-adjusted axis improves over HEAD — and OOS robustness is *stronger*
(min fold +0.138R vs +0.013R; lockbox +0.493R/PF 3.77 vs +0.324R/PF 2.15; maxDD halved). The
filter removed 75 of the incumbent's 224 trades (≈ one third) and what remains is cleaner on every
dimension. The sole failure is the **200-trade hard floor** (149 in-sample; WF folds 11–27 trades
each).

## Verdict
**REJECTED — fails `sample_size` (149 < 200), a hard gate.** No proposal filed (a proposal
requires ALL gates to pass). This is *not* a quality rejection: on quality the candidate dominates
HEAD. It is a **trade-count** rejection, and on this dataset it is structural, not tunable: the
incumbent's in-sample base is exactly 224 — only 24 trades above the floor — so any directional
filter (which inherently cuts ≈ the counter-trend share, here ~33%) cannot clear 200. Tuning
`ema_window`/`slope_lookback` to scrape back to 200 would be p-hacking the floor and burning DSR
budget; declined.

## Lessons
1. **The trend-alignment edge is REAL and ROBUST on EURUSD M15.** Vetoing counter-trend overlap
   breaks lifted win rate 73.2%→76.5%, PF 1.99→2.40, expectancy +0.294R→+0.359R, **halved maxDD**
   ($1883→$958), and held in *every* walk-forward fold and the sealed lockbox (+0.493R, PF 3.77).
   The hypothesis "the incumbent's losers are disproportionately counter-trend" is **confirmed**.
   This is the first candidate to beat HEAD on risk-adjusted quality (contrast
   [[2026-06-13-second-entry-orb]], which passed but was dominated).
2. **The 200-trade hard floor is now the binding constraint on the whole subtractive-filter
   family — confirmed by a SECOND, independent mechanism.** The compression filter
   ([[2026-06-07-pre-session-compression-filter]]) flagged "subtractive-filter family gate-blocked
   at 224-trade headroom" from a *volatility-timing* angle; TrendAlignedORB reaches the same wall
   from a *directional* angle. The incumbent's 224-trade base leaves only 24 trades of slack, so a
   filter that meaningfully cuts trades **cannot** satisfy `sample_size` no matter how selective.
   **Selectivity is not the problem here; the data length is.** This is the *single-jeopardy*
   case (floor only), the clean inverse of [[2026-06-11-breakout-retest]]'s double-jeopardy
   (anti-selection *and* floor).
3. **Process:** quality and trade-count are now demonstrably separable verdicts. SecondEntryORB
   (additive: +trades, −quality, passes-but-dominated) and TrendAlignedORB (subtractive: −trades,
   +quality, dominates-but-fails-floor) bracket the design space. The path to actually *beating*
   HEAD on one dataset is squeezed from both sides; the realistic unlock is **more data**, not a
   cleverer filter.

## Next steps
- **Re-test on a longer export (highest-value follow-up).** This is the strongest re-test
  candidate in the library: a 2–3× longer M15 history would lift the trade base above the floor
  while (on this evidence) preserving the quality edge. Queue as `blocked-on-data` until history
  is extended; it materially strengthens the case for backlog item "longer history export"
  (spec 08 §8). Re-test verbatim — params already pre-registered, so the re-test is not a new
  hypothesis (no extra triage).
- **Do NOT** sweep `ema_window`/`slope_lookback` on the current data to chase 200 trades (floor
  p-hacking; burns DSR).
- Possible variant once data allows: a *softer* trend gate (e.g. veto only when the slope exceeds
  a magnitude threshold, leaving near-flat days to the incumbent) to cut fewer trades — but this
  is a trade-count lever, only worth it if the longer-history re-test still grazes the floor.
