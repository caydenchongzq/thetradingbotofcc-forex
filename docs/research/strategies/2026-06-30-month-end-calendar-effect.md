---
id: 2026-06-30-month-end-calendar-effect
name: MonthEndCalendarEffect
family: other
status: probe-rejected
related: [2026-06-17-intraday-seasonality-drift, 2026-06-28-ecb-fix-conditional-reversion]
sources:
  - "https://www.bis.org/publ/qtrpdf/r_qt2409d.pdf"
  - "https://www.bis.org/publ/bisbull105.pdf"
  - "https://www.ebc.com/forex/3-reasons-markets-move-at-month-and-quarter-end"
  - "https://www.tickmill.com/blog/institutional-insights-month-end-fx-rebalancing-models"
  - "https://global-view.com/euro-exchange-month-end-fx-rebalancing-flows/"
trials_used: 0
verdict: "Unconditional: all legs t<1.2, peak drift −1.5p vs 2.6p cost gate; conditional (equity return) blocked-on-data; calendar-effect family closed"
---

# MonthEndCalendarEffect — month-end / quarter-end institutional rebalancing drift in EUR/USD

## Hypothesis & market rationale

At the end of each calendar month (and especially each quarter), equity portfolio managers
rebalance their currency hedges based on the prior month's equity performance: if US equities
outperformed, the USD share of a global portfolio has risen → managers SELL USD (buy EUR) to
restore target weights. The effect is well-documented in institutional FX commentary (BIS,
JPMorgan, Barclays month-end models) and is mechanically driven — not speculation — so it
should persist even if widely known.

The differentiation from the CLOSED fixed-time-of-day seasonality family
([[2026-06-17-intraday-seasonality-drift]]): that family tested DAILY clock-based drifts
(07:00–13:00, 13:00–17:00, etc.) that fire every single day. Month-end is a CALENDAR-DATE
effect that fires 1–2 days per month based on the specific month-end date; the mechanism is
institutional portfolio maintenance rather than time-zone invoicing or home-currency bias.

The differentiation from the CLOSED ECB fix ([[2026-06-28-ecb-fix-conditional-reversion]]): that
was a specific 14:15 CET intraday price-fixing mechanism. Month-end is a daily-close-to-close
flow over 1–3 days.

## Sources

1. BIS Quarterly Review Sep 2024 — documents FX hedging rollover and rebalancing flows.
   https://www.bis.org/publ/qtrpdf/r_qt2409d.pdf
2. BIS Bulletin No 105 (2025) — "US dollar's slide in April 2025: the role of FX hedging" —
   direct evidence of institutional USD selling around portfolio rebalancing.
   https://www.bis.org/publ/bisbull105.pdf
3. Tickmill institutional insights — month-end FX rebalancing model commentary, noting the effect
   is conditional on equity performance direction.
   https://www.tickmill.com/blog/institutional-insights-month-end-fx-rebalancing-models
4. Global-View.com — practitioner discussion of EUR-USD month-end rebalancing flows.
   https://global-view.com/euro-exchange-month-end-fx-rebalancing-flows/
5. EBC Financial Group — "3 reasons markets move at month & quarter-end".
   https://www.ebc.com/forex/3-reasons-markets-move-at-month-and-quarter-end

## Relation to prior library work

- **[[2026-06-17-intraday-seasonality-drift]]** (CLOSED): tested daily time-of-day drifts, all
  insignificant (|t|<0.8), gross ≤0.55p. Month-end is a different temporal mechanism (calendar
  date, not daily clock). The probe is legitimate.
- **[[2026-06-28-ecb-fix-conditional-reversion]]** (CLOSED): ECB 14:15 institutional fix — same
  "institutional mechanism" category but different trigger and completely different market dynamic.
  The ECB fix arbitrage is a specific intraday pricing event; month-end is a multi-day flow.
- No prior test of calendar-date (month-end / quarter-end) effects in the library.

## Strategy spec

**Conditional version (the documented mechanism):**
- Signal: prior month's equity return (S&P 500 or global equity index) was positive → USD-selling
  expected (EUR/USD long); negative → USD-buying (EUR/USD short).
- Entry: London open on the last 1–2 trading days of the month.
- Exit: close at end of last trading day.
- **STATUS: BLOCKED-ON-DATA** — no equity return data available in the M15 parquet.

**Unconditional version (tested here):**
- Signal: go LONG EUR/USD on the last N trading days of each month (or short — both directions
  tested since direction is undefined without equity conditioning).
- Entry/exit: daily close-to-close.
- This is a null hypothesis test: does month-end show ANY unconditional drift?

**Exit geometry (moot — probe only):** daily close-to-close measurement; no ATR stops applied
in the probe since this is a directional calendar signal measured at close.

## Implementation notes

No code written. Probe-only via ad-hoc Python on the parquet (2026-06-30). No files touched.

## Backtest results

Probe only — no trial spent.

```
Data: 2024-01-01 to 2026-05-29 (29 months)

Cross-month (last trading day → first of next month, n=28):
  Mean drift: −1.54p, t=−0.16

Last 2 days intra-month (n=29 day-pairs):
  Mean drift (long direction): −5.47p, t=−0.74

Last 3 days intra-month (n=58 day-pairs):
  Mean drift (long direction): −6.16p, t=−1.12

First→Second day of month (n=29):
  Mean drift: +1.74p, t=+0.15

Cost standard: 2.6p round-trip (from closed probes)
All legs: |drift| << 2.6p cost gate, all t < 1.2
```

All t-statistics are well below significance. The directional drift is noise-level; the largest
t is −1.12 (last 3 days) — statistically insignificant and pointing the wrong direction for the
institutional rebalancing narrative (if USD-selling dominates at month-end, we'd expect POSITIVE
EUR/USD drift in the last 2–3 days, but the mean is negative).

## Verdict

**PROBE-REJECTED — no trial spent.**

- **Unconditional version**: all legs fail the cost gate by >1.5×; t-statistics uniformly below
  significance; directional inconsistency with the rebalancing narrative. No signal.
- **Conditional version**: BLOCKED-ON-DATA (requires equity return data to compute
  USD-selling/buying direction). Could be revisited if equity index data is added to the pipeline.

The calendar-effect / month-end family is now **closed on OHLCV-only data**. The unconditional
effect does not exist in 2024–2026. The conditional version is a legitimate blocked hypothesis.

## Lessons

1. **Unconditional calendar effects do not survive in 2024–2026 EURUSD M15.** The drift sign
   is not stable (sometimes positive, sometimes negative at month-end) because the rebalancing
   DIRECTION depends on equity returns — it is inherently a CONDITIONAL signal. Testing the
   unconditional version was the right null-check: t<1.2 means there is nothing to condition on.

2. **The documented institutional effect (BIS, bank desks) is conditional on equity performance
   and requires external data.** This is a qualitatively different situation from the closed ECB
   fix ([[2026-06-28-ecb-fix-conditional-reversion]]) where the effect exists but has been
   arbitraged away — here the effect may still exist but is simply inaccessible without an
   equity return feed.

3. **29 months is a short sample for 1-per-month events.** Even if the effect were present,
   ~29 observations is too few to detect it reliably (similar to the TwentyDayTurtleSoup
   [[2026-06-30-twenty-day-turtle-soup]] rare-event problem). The conditional probe with equity
   data would need at least 5+ years of history.

4. **Quarter-end is a subset of month-end** (only 3 of 29 observations are quarter-ends) — too
   rare to test separately on this data. Blocked-on-both (equity data + longer history).

## Next steps

- Queue **conditional month-end** as blocked-on-data: needs equity index (S&P 500 or MSCI World)
  daily returns to compute hedge-rebalancing direction. If equity data is ever added to the
  pipeline, this is a high-priority revisit given the strong institutional backing.
- Blocked-on-data queue: [[2026-06-28-macro-news-release-momentum]],
  [[2026-06-28-ny-options-cut-gamma-pin]], [[2026-06-14-cross-instrument-confirmation]].
