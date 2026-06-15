---
id: 2026-06-15-london-open-breakout-er
name: LondonOpenBreakoutER
family: breakout
status: tested-rejected
related: [2026-06-02-session-breakout-er, 2026-06-15-resting-stop-and-market-entry, 2026-06-14-trend-aligned-orb, 2026-06-13-second-entry-orb]
sources:
  - "https://www.quantifiedstrategies.com/london-breakout-strategy/"
  - "https://www.forex.com/en-uk/trading-academy/courses/advanced-strategies/uk-open-range-breakout/"
  - "https://www.litefinance.org/blog/for-beginners/trading-strategies/opening-range-breakout-strategy/"
  - "https://titanfx.com/education/london-forex-trading-session-trading-strategies"
trials_used: 1
verdict: "Session-transfer FALSIFIED. The ORB+ER/ATR mechanism, filled LIVE-FAITHFULLY (the RESTING_STOP_FIX market entry it inherits), has NO edge at the London open either: in-sample −0.129R / PF 0.57 / 55.6% win (WORSE than the overlap incumbent's live-faithful −0.080R), 0/5 scored WF folds profitable, stitched −0.220R, severe folds; only the 34-trade lockbox is positive (+0.188R) — the same misleading tail as TrendAlignedORB. AND it misses the 200-trade floor on its own base (153). Two independent failures: no live-fillable edge + below floor. Confirms [[2026-06-15-resting-stop-and-market-entry]]: the breakout family's apparent edge was the level-fill artifact, not the session — moving it to a fresh session recovers nothing."
---

# LondonOpenBreakoutER — the validated ORB+ER+ATR mechanism on the London-open session

## Hypothesis & market rationale
The incumbent `SessionBreakoutER` trades exactly one window: the London/NY **overlap**
(13:00–16:00 London), a peak-liquidity *continuation* regime. The **London open** (~08:00
London) is a structurally different and, in the practitioner literature, the single most
consistent breakout window in FX: ~35–40% of daily turnover enters at the London open, and the
session opens against a compressed overnight (Asian) range, so the first directional expansion
is an *initiation* move rather than a mid-trend continuation.

Falsifiable claim: **the same opening-range-breakout edge the incumbent harvests at the overlap
also exists at the London open**, on an **independent** trade stream (a different time of day,
not a subset of the incumbent's ~224 trades). If true, a gated London-open ORB clears the R6
gates on its own base; if the open is efficient re-pricing of the Asian range, the ER/ATR gate
rejects most of it and the candidate fails honestly on edge.

## Sources
- QuantifiedStrategies — *London Breakout Strategy*: a *naive* "buy above / sell below the Asian
  range" on EUR/USD "often result[s] in losses" — the ER/ATR gate was meant to be the
  differentiator (https://www.quantifiedstrategies.com/london-breakout-strategy/).
- FOREX.com — *European/UK Open Range Breakout*; EUR/USD is the canonical pair
  (https://www.forex.com/en-uk/trading-academy/courses/advanced-strategies/uk-open-range-breakout/).
- LiteFinance — *ORB success rate 40–60%, filter-dependent*
  (https://www.litefinance.org/blog/.../opening-range-breakout-strategy/).
- TitanFX — London session ≈ highest-volume session, ~35% of turnover
  (https://titanfx.com/education/london-forex-trading-session-trading-strategies).

Hypothesis-only; no community code copied. The implementation re-uses our own audited
`SessionBreakoutER` machinery. The backtester is the arbiter.

## Relation to prior library work
- **Builds on [[2026-06-02-session-breakout-er]]:** identical mechanism (ORB break, ER≥thr +
  ATR-normal gate, `max(structural, 1.2×ATR)` stop, single-1R target, break-even `manage()`);
  the ONLY change is the session window. Critically, it inherits the *post-fix*
  `evaluate` — the RESTING_STOP_FIX **market** entry (fill ≈ the confirmed close) — so unlike
  the pre-fix family it is tested **live-faithfully from day one** (no level-fill artifact
  possible). This is what makes the result trustworthy where the old +0.391R was not.
- **Intended to escape the 200-trade-floor trap** that killed the subtractive-filter family
  ([[2026-06-14-trend-aligned-orb]]): it is additive (a new session), not subtractive. *In the
  event the escape failed anyway* — the London-open base is only **153 trades**, itself below
  the floor (see Verdict). A fresh base is only useful if the session actually produces ≥200
  gated trades; this one does not.
- **Differs from [[2026-06-13-second-entry-orb]]:** that added *same-session* re-break entries
  (dilution); this is a stand-alone *different-session* base.

## Strategy spec
- **Session:** London open, window `08:00–11:00` Europe/London (3-hour span mirroring the
  incumbent's 3-hour overlap), opening range `08:00–08:30`, one-shot per side.
- **Entry:** inherited `SessionBreakoutER.evaluate` verbatim — close-confirmed break, **market**
  fill at the confirmed close (live-faithful). The ER is read on the bars into 08:00 (the Asian
  session) — the correct "is the overnight range coiled or already trending" read.
- **Exit geometry (spec 08 §5.8 — pre-registered):** stop `max(structural, 1.2×ATR)` and single
  **1R** (R:R 1:1), inherited by mechanism-equivalence (same momentum break ⇒ same geometry; the
  ≥2R rejections [[2026-06-07-tp-2r-sweep]] bind any 2R variant). No new manage semantics ⇒ no
  live-mirror session required.

## Implementation notes (built this run — dev-isolated)
- `src/engine/strategy_london_open.py`: thin `class LondonOpenBreakoutER(SessionBreakoutER)`
  that forces the London-open window in `__init__` (tunable via a dedicated `london_open` config
  block) and inherits `evaluate`/`manage` verbatim. One `register("LondonOpenBreakoutER", …)`
  line in `src/engine/registry.py` (additive).
- Unit tests `tests/engine/test_london_open.py` (8): forces the window; fires at the London open;
  silent in the overlap; disjoint base from the incumbent; inherits the market fill (entry_price
  == close, not the level); exit geometry; degraded paths; registry build. Full
  `pytest tests/engine tests/backtest` green.
- No writes to `state/config` HEAD; no live-path edits; no promotion.

## Backtest results (real data, 59,993 M15 bars, 2024-01 → 2026-05; `--trials 166`)

### In-sample (all gates)
| metric | gate | LondonOpenBreakoutER | incumbent HEAD (live-faithful) |
|---|---|---|---|
| trades | ≥ 200 | **153 — FAIL** | 224 |
| expectancy | ≥ 0.10R | **−0.129R — FAIL** | −0.080R |
| win rate | — | 55.6% | 57.6% |
| profit factor | ≥ 1.3 | **0.57 — FAIL** | 0.56 |
| sharpe | ≥ 1.0 | **−1.83 — FAIL** | −2.00 |
| sortino | ≥ 1.5 | **−2.04 — FAIL** | −2.21 |
| DSR | ≥ 0.95 | **0.00 — FAIL** | 0.00 |
| FTMO breaches | 0 | 0 — PASS | 0 |
| **verdict** | | **FAIL (6/7 gates)** | FAIL |

### Walk-forward (OOS)
| window | trades | exp(R) | PF | net$ |
|---|---|---|---|---|
| 2024 Q1 | 15 | −0.210 | 0.55 | −1103 |
| 2024 Q2 | 9 | −0.404 | 0.33 | −1320 |
| 2024 Q3 | 8 | −0.163 | 0.59 | −525 |
| 2024 Q4 | 15 | −0.121 | 0.68 | −803 |
| 2025 Q1 | 19 | −0.314 | 0.42 | −2317 |
| 2025 Q2 | 22 | −0.265 | 0.42 | −1705 |
| 2025 Q3–Q4 | 31 | −0.142 | 0.59 | −940 |

**0/5 scored folds profitable**, stitched OOS −0.220R vs in-sample −0.129R, **severe fold**
(min −0.314R). Lockbox 2025-11→2026-05: 34 trades, **+0.188R, PF 1.38 — PASS** (its core gates),
but a 34-trade tail that contradicts all seven prior quarters. **WALK-FORWARD: FAIL.**

## A/B vs incumbent HEAD
On the same live-faithful fill, LondonOpenBreakoutER is **worse than the overlap incumbent on
both axes**: −0.129R vs −0.080R expectancy, and 153 vs 224 trades. There is no dimension on
which the London-open session improves the mechanism. (Both are losers; the comparison only
confirms the session transfer did not help.)

## Verdict
**tested-rejected — two independent failures.** (1) No live-fillable edge: the mechanism is
structurally negative at the London open (−0.129R, PF 0.57, 0/5 WF folds), slightly *worse* than
the already-edgeless overlap. (2) Below the 200-trade floor on its own base (153). The lockbox
being the lone green window is the same artifact pattern flagged on [[2026-06-14-trend-aligned-orb]]
— not an edge.

## Lessons
- **The edge was the fill, not the session.** [[2026-06-15-resting-stop-and-market-entry]] showed
  the incumbent's apparent edge was the unfillable level-fill. This run is the corollary: transfer
  the *same mechanism* to a fresh session under a live-faithful fill and there is still no edge.
  The ORB+ER/ATR breakout on EURUSD M15 does not have a live-realizable edge in EITHER session.
- **"A new independent base escapes the floor" is necessary but not sufficient.** The reasoning was
  structurally right (additive, not subtractive) but presupposed the new session produces ≥200
  gated trades AND carries an edge. The London open delivered neither (153 trades, negative). A
  fresh base of a no-edge mechanism is still no-edge.
- **The lockbox-positive / everything-else-negative pattern has now recurred twice** (TrendAlignedORB,
  here). A single favorable 30–40 trade tail window is noise, not signal — it reinforces judging on
  the full gate + WF stack, never the lockbox in isolation.
- **Research-program implication:** the ORB-breakout family is now 0-for-everything under
  live-faithful fills (overlap incumbent, second-entry, trend-filtered, London-open). Future
  candidates should pivot to a *genuinely different mechanism*, or to an entry whose edge
  demonstrably survives a market/stop fill — not another ORB-mechanism variant.

## Next steps
1. **Reject**; do not pursue further ORB-session variants (NY-open would be inside the overlap;
   Asian-open is low-vol). The session axis is exhausted for this mechanism.
2. Pivot research toward mechanisms whose edge does not depend on the breakout-bar continuation
   fill (the thing the level-fill was faking). Mean-reversion families are mostly closed; the open
   space is a *different* entry whose live fill ≈ its signal price.
3. INDEX: flip the London-open queue line from `idea` to `tested-rejected` (pending Cayden's
   in-progress INDEX reformat — see this run's summary).
