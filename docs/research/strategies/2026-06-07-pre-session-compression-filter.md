---
id: 2026-06-07-pre-session-compression-filter
name: SessionBreakoutERCompression
family: filter
status: blocked-on-data
related: [2026-06-02-session-breakout-er, 2026-06-07-tp-2r-sweep]
sources: ["https://www.quantifiedstrategies.com/nr7-trading-strategy-toby-crabel/", "https://tradingstrategiesdaily.com/p/nr7id-toby-crabel", "https://tradersmastermind.com/trading-strategy-opening-range-breakout/", "https://www.quantifiedstrategies.com/opening-range-breakout-strategy/"]
trials_used: 1
verdict: "Degenerate on real data (3 trades vs 224): London morning is ALWAYS louder than the overnight baseline (median pct 0.90, never <=0.6). Any seasonality-correct variant is gate-blocked: incumbent has 224 trades vs the >=200 gate, so no selective filter (<~90% keep) can pass. Needs longer history."
---

# SessionBreakoutERCompression — Crabel-style pre-session compression entry filter

## Hypothesis & market rationale
Crabel's ORB research: volatility contraction precedes expansion — opening-range
breakouts after narrow-range periods (NR4/NR7, reported win rates 60–76% in his pre-1990
futures backtests) are more reliable. Falsifiable form here: *SessionBreakoutER signals
taken only when the London morning (the 20 M15 bars before the 13:00 window) was quiet —
mean true range at or below the median of the 60 preceding single-bar TRs — outperform
the unconditional incumbent on the R6 gates.* Filter chosen a priori (median cut, no
sweep) to spend exactly one trial.

## Sources
- QuantifiedStrategies — NR7/Crabel backtests: https://www.quantifiedstrategies.com/nr7-trading-strategy-toby-crabel/
- TradingStrategiesDaily — NR7ID double-compression: https://tradingstrategiesdaily.com/p/nr7id-toby-crabel
- TradersMastermind — ORB filters: https://tradersmastermind.com/trading-strategy-opening-range-breakout/
- QuantifiedStrategies — ORB backtest: https://www.quantifiedstrategies.com/opening-range-breakout-strategy/

The backtester, not the sources, is the arbiter — and it spoke clearly.

## Relation to prior library work
Builds on [[2026-06-02-session-breakout-er]] (incumbent, HEAD v4). Distinct from the
rejected exit-model family ([[2026-06-03-full-exit-model]], [[2026-06-07-tp-2r-sweep]]):
this is ENTRY-side only — exits/manage inherited unchanged, so the recorded
"exit extensions trade away the win-rate edge" failure mode does not apply.

## Strategy spec
`SessionBreakoutERCompression(SessionBreakoutER)` — identical to incumbent except
`evaluate()` additionally requires `compression_pct(pre-session bars, recent=20,
baseline=60) <= 0.50`, where compression_pct = percentile of the morning's mean TR within
the 60 preceding single-bar TRs. Fail-safe: insufficient history → 1.0 → blocked.
Config block `compression: {recent_bars, baseline_bars, max_pct}` (would join
ALLOWED_LEVERS only if ever promoted).

## Implementation notes
Additive only, dev-isolated, NOT promoted; live path untouched; no state/ writes
(except the sanctioned trial-ledger append). Kept in-tree as the template for future
filter candidates:
- `src/engine/indicators.py` → `compression_pct()` (pure)
- `src/engine/strategy_compression.py` → strategy subclass (entry filter only;
  `manage` inherited ⇒ no live-mirror needed)
- `src/engine/registry.py` → one `register()` line
- `tests/engine/test_compression.py` (11) + `tests/backtest/test_compression_harness.py` (2) — full suite green
- `config/dev/compression.yaml`, `scripts/compare_compression.py` (A/B template)

## Backtest results
Command: `py scripts/run_backtest.py --config-file config/dev/compression.yaml --trials 41`
(full 2024-01→2026-05, $100k).

| metric | gate | candidate | incumbent HEAD v4 |
|---|---|---|---|
| trades | ≥ 200 | **3** | 224 |
| expectancy | ≥ 0.10R | +0.187R (meaningless, n=3) | +0.391R |
| verdict | all gates | **FAIL (degenerate)** | promoted |

Diagnostic (155 probe sessions, Jan–May 2024): the filter's percentile had
median 0.90, minimum 0.633, never ≤ 0.6 — the London morning (08:00–13:00) is
*systematically* louder than its preceding 15h baseline (Asia + prior evening), so a
median cut never fires. Intraday volatility seasonality (the documented FX U-shape)
swamps any day-to-day compression signal measured against an unmatched baseline.
Walk-forward and A/B were not run — pointless at n=3; no further information extracted.

## Verdict
REJECT as built (degenerate). The seasonality-correct reformulation — compare today's
morning only against PRIOR DAYS' SAME morning window (true NR4/NR7 analog) — is
**blocked on data + the trade-count gate**: the incumbent produces only 224 trades on
the 29-month dataset vs the ≥200 gate, so any filter keeping less than ~90% of signal
days mechanically fails R6 regardless of edge quality (NR2-style ≈50% keep → ~112
trades; NR4-style ≈75% keep → ~168). One trial consumed (ledger
`2026-06-07-compression-filter`, cumulative now 41). No proposal filed.

## Lessons
- **Intraday seasonality breaks naive baselines.** Any "X is quiet/loud" intraday
  feature must be measured against the SAME time-of-day window on prior days, never
  against the preceding hours. The London morning is always louder than the night.
- **The ≥200-trade gate structurally caps subtractive entry filters.** With the
  incumbent at 224 trades / 29 months, the entire entry-filter family (compression,
  day-of-week, NR-style, any selective gate) is untestable-to-pass until the history
  export grows (~2× data) or the gate is consciously revisited. Check the trade-count
  headroom BEFORE building any filter idea.
- 400-bar `history_window` permits at most ~3 prior same-window mornings — percentile
  baselines over prior days need a longer engine window (O(N·W) cost rises).
- Process: a cheap engine probe (15k bars, ~2s) before the full gated run caught the
  degeneracy early; do this for every future candidate.

## Next steps
- Re-queue as morning-vs-prior-mornings NR variant ONLY after a longer MT5 export
  (backlog: extend `scripts/mt5_export.py` history; also widens DSR headroom).
- Filter ideas should be reframed as *additive* regime levers on existing gates (e.g.
  tightening `atr_high_pct`) which the weekly optimizer can sweep within ALLOWED_LEVERS
  without new code.
