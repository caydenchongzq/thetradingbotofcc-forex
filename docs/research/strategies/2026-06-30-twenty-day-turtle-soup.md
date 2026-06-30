---
id: 2026-06-30-twenty-day-turtle-soup
name: TwentyDayTurtleSoup
family: mean-reversion
status: probe-rejected
related: [2026-06-08-asian-sweep-fade, 2026-06-19-session-range-false-break-fade, 2026-06-29-high-er-thrust-fade]
sources:
  - "https://www.quantifiedstrategies.com/turtle-soup-trading-strategy/"
  - "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3362142"
trials_used: 0
verdict: "n=63 (<<200 floor), −0.041R / WR 49.2% / PF 0.60 — 7th MR anchor fails; structural-level sweep does not differentiate from closed intraday-range sweeps"
---

# TwentyDayTurtleSoup — fade a sweep of a 20-session structural high/low

## Hypothesis & market rationale

The "Turtle Soup" trade (Linda Bradford Raschke, from the Turtle Traders reversal) fades a SWEEP
of a longer-term structural high or low: price just clears a rolling N-day extreme high/low
(triggering the breakout stops parked there), then closes back inside → contra-trend players
re-enter and price reverts.  The differentiation from the closed intraday mean-reversion family
is the LEVEL type: a 20-session (≈1-month) structural high/low is widely-watched by participants
(many stops clustered there), unlike a same-day opening-range boundary or an intraday VWAP level.
The theory is that the stop-run liquidity sweep at a multi-week level is a more meaningful
microstructure signal than an intraday range false-break.

## Sources

- QuantifiedStrategies: "Turtle Soup Trading Strategy — Rules, Backtest, Returns, Risks" —
  retail-level backtest on equities/ETFs; cited as mechanism hypothesis only.
  https://www.quantifiedstrategies.com/turtle-soup-trading-strategy/
- Caporale & Plastun (SSRN 3362142, JES 2020) — prior-day overreaction reversal on EURUSD,
  used as a contrast reference for cross-day mean-reversion. [[2026-06-26-prior-day-overreaction-reversal]]
  found this specific paper's 2008–2018 effect did not replicate on 2024–2026 data.

## Relation to prior library work

The mean-reversion family has been tested and closed across **6 anchor types**:

| Anchor | Result |
|---|---|
| Asian intraday range (1R) | [[2026-06-08-asian-sweep-fade]] −0.158R |
| Asian intraday range (2R) | [[2026-06-10-asian-sweep-fade-rr]] −0.212R |
| Session VWAP stretch | [[2026-06-16-vwap-stretch-reversion]] −0.283R |
| Session-OR false break | [[2026-06-19-session-range-false-break-fade]] ~0 gross |
| Cross-day overreaction | [[2026-06-26-prior-day-overreaction-reversal]] gross neg |
| ECB fix institutional | [[2026-06-28-ecb-fix-conditional-reversion]] gross +1.82p |
| High-ER single-bar | [[2026-06-29-high-er-thrust-fade]] t=3.0 but +0.14p gross |

TwentyDayTurtleSoup's stated differentiation: **the swept level is a multi-week structural
extreme** rather than a same-session boundary. Prior closures apply to intraday to single-day
anchors. This probe tests whether the structural level distinction matters.

## Strategy spec

- **Session:** any session (structural high/low is not session-bound)
- **Signal:** a daily bar whose LOW sweeps below the 20-trading-day rolling low (shift 1 day)
  AND whose CLOSE is back above that level (bull sweep, go long), OR a daily bar whose HIGH
  sweeps above the 20-day rolling high AND whose CLOSE is back below (bear sweep, go short).
- **Entry:** market order at open of the next bar (live-fillable — level defined before the
  trigger bar closes, so no retcode 10015 issue; OCO resting-stop could also be used but
  market is simpler and tested here).
- **Exit geometry:**
  - **Stop:** 1.5×ATR14 beyond the swept structural level (wide enough to avoid re-triggering
    on the same sweep; the structural level should hold now that the stop-run is complete).
  - **Target:** 1R (R:R 1:1). Rationale: the mechanism expects price to return to the midpoint
    of the prior range, not necessarily to the opposite extreme; 1R is conservative given the
    uncertain follow-through; 2R would require <50% win rate which structural-reversal proponents
    do not claim at this leverage.
  - **Rationale:** 1.5×ATR stop acknowledges that structural-level sweeps often create larger
    intrabar wicks than intraday range false-breaks; 1R target matches the mean-reversion expectation
    of partial recovery only.

## Implementation notes

No code written. Probe-only run on the parquet via `scripts/` ad-hoc analysis (2026-06-30).
No files touched, no registry entry, no tests added. pytest state unchanged.

## Backtest results

Probe only — no `--walkforward` trial spent.

Script: ad-hoc Python on `state/parquet/eurusd_m15.parquet`, 2026-06-30.

```
Date range: 2024-01-01 to 2026-05-29  (735 trading days)
Bull sweeps: 31
Bear sweeps: 32
Total events: 63

Simulation (n=63):
  Expectancy:     −0.041R
  Win rate:        49.2%
  Profit factor:    0.60
  Sharpe (ann):    −2.42

Gate requirements (R6): exp≥0.10R, PF≥1.3, n≥200
```

Gate failures: expectancy (−0.041R vs +0.10R), PF (0.60 vs 1.30), sample_size (63 vs 200).

**No A/B vs HEAD conducted** (probe-reject threshold: failing 3 gates and n<<200 floor).

## Verdict

**PROBE-REJECTED — no trial spent.** Three hard gate failures; n=63 is 3× below the 200-trade
floor with only 29 months of data (≈2 sweeps/month). Even if the edge were borderline positive,
the sample_size failure alone disqualifies until a much longer history is available.

The structural-level differentiation does NOT rescue mean-reversion on this dataset: the −0.041R
result is consistent with the 6 prior closed anchors. Mean-reversion family now **7/7 closed**
across anchor types.

## Lessons

1. **Level granularity is not the differentiator for mean-reversion failure.** The closed family
   spans intraday (session range), single-day (prior-day overreaction), single-bar microstructure
   (HighER), institutional-clock (ECB fix), and now multi-week structural. In all cases the gross
   expectancy is near zero or negative. The recurring mechanism is that EURUSD extension continues
   or chops more than it mean-reverts, regardless of which level defines the trade.

2. **Rare-event strategies on 2 years of data are double-jeopardy:** they fail both the edge
   test (n too small for reliable estimation) AND the 200-trade floor gate. Any further
   structural-level mean-reversion variant will face the same wall until longer data is available.

3. **The "stop-run → liquidity sweep → reversal" narrative is directionally appealing but not
   supported quantitatively in EURUSD M15 2024–2026.** The ~65% double-break rate (documented in
   [[2026-06-19-session-range-false-break-fade]]) applies at structural levels too — the sweep is
   often the first leg of a continued directional move, not a false breakout.

## Next steps

- Mean-reversion family is fully closed (7/7 anchors). No further MR variants on current data.
- The real lever remains longer data / second instrument: with 5+ years of M15 history,
  rare-event strategies (TwentyDayTurtleSoup, TwentyDayTurtle sweep, etc.) would clear the
  200-trade floor and allow a more reliable estimate. Queue as **blocked-on-data**.
