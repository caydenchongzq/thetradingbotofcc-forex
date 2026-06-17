---
id: 2026-06-17-intraday-seasonality-drift
name: IntradaySeasonalityDrift
family: other                  # time-of-day / seasonality directional bet
status: idea                  # probe-rejected (no trial spent) — see Verdict
related: [2026-06-09-late-session-drift, 2026-06-07-intraday-ts-momentum]
sources:
  - "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2099321"   # Breedon & Ranaldo, Intraday Patterns in FX Returns and Order Flow (JMCB 2013)
  - "https://onlinelibrary.wiley.com/doi/abs/10.1111/jmcb.12032"
  - "https://www.sciencedirect.com/science/article/abs/pii/S1566014119302031"  # Intraday-of-the-week effects (J. Int. Financial Markets 2019)
  - "https://epchan.blogspot.com/2023/03/applying-corrective-ai-to-daily.html"  # Chan: the EURUSD home/away leg "dies a horrible death" after costs
trials_used: 0                # PROBE only — no backtest, no trial-ledger entry, no DSR cost
verdict: "probe-rejected (no trial): the invoice/home-away intraday drift is real but un-harvestable — every directional leg is statistically insignificant (|t| < 0.8) with raw drift ≤ 0.55 pip, far below the ~2.6-pip round-trip cost; day-of-week drift also insignificant (|t| ≤ 1.21). Seasonality directional family closed on current data without spending a trial."
---

# IntradaySeasonalityDrift — trade EURUSD's documented time-of-day directional bias

## Hypothesis & market rationale
Breedon & Ranaldo (2013) document a robust **"home/away" (invoice) effect**: a currency
tends to *depreciate during its home working hours* and *appreciate during the US working
hours*, driven by order flow — local participants are net purchasers of FX in their own
session. For EUR/USD this implies a directional intraday pattern: **short EURUSD in the
European morning, long EURUSD in the US afternoon**. The intraday-of-the-week literature
(Sci., 2019) adds a day-of-week overlay (currencies depreciate vs USD Mon/Tue, appreciate
later in the week) and an ECB-fix reversion (EUR drifts down into the ECB reference fix, then
recovers into the NY close).

Falsifiable claim, market-fillable, EURUSD-specific, and easily ≥200 trades (one per day per
leg) — which is exactly why it was queued (2026-06-16) as a fresh, non-breakout, non-fade
direction worth a look. **But the same literature flags the raw per-leg edge as "very small"
(Chan: "the average profit per round trip is tiny, so if you add costs, this dies a horrible
death — a real effect that you can't trade directly").** Per the queue's own instruction, this
was probed against the actual cost stack *before* spending a trial.

## Sources
- Breedon, F. & Ranaldo, A., *Intraday Patterns in FX Returns and Order Flow*, J. Money,
  Credit & Banking (2013) — SSRN 2099321 / Wiley 10.1111/jmcb.12032. The primary evidence for
  the home/away (invoice) effect and the EUR→ECB-fix→NY-recovery shape.
- *Intraday-of-the-week effects: what do the exchange-rate data tell us?*, J. International
  Financial Markets (2019) — the W-shaped intraday pattern and day-of-week sign overlay.
- E. Chan, *Applying Corrective AI to Daily Seasonal Forex Trading* (2023) — the EURUSD
  London-short / NY-long leg is "a real effect you can't trade directly"; net of cost it dies.

Sources are hypothesis only; the data below is the arbiter.

## Relation to prior library work
- **[[2026-06-09-late-session-drift]]** (trend, tested-rejected): the closest precedent — a
  real raw drift (+2.3 pip/night) killed by the 1.24-pip thin-hour spread. The queue noted
  this candidate differs by trading only the *liquid* London/US hours (spread ≈ 0.15 pip
  here, not 1.24). That differentiation is valid — thin-hour cost is NOT the killer here — but
  the *raw-pip ≠ R-edge* lesson still bites: the liquid-hour drift is simply too small.
- **[[2026-06-07-intraday-ts-momentum]]** (probe-rejected): early→late session return
  correlation 0.026, mean +0.25 pip < cost. This candidate is the *seasonal/directional*
  cousin (fixed time-of-day sign, not a momentum carry); it fails for the same arithmetic
  reason — sub-cost drift — confirming the pattern from a different angle.
- Distinct from all breakout/fade/trend families: it is a fixed time-of-day directional bet,
  not conditioned on price structure.

## Strategy spec (as it would have been built, had the probe passed)
- **Entry:** market order at the leg open. EUR-leg: short at 07:00 UTC. US-leg: long at
  13:00 UTC. (Live-fillable by construction — market entries, liquid hours.)
- **Exit:** market order at the leg close (EUR-leg 13:00 UTC; US-leg 17:00 UTC) — a
  *time-based* exit, since the edge is a calendar drift, not a price level.
- **Regime/session:** London + NY liquid hours only (avoid the 21:00-UTC rollover spread
  spike, which the hourly scan shows at 2.31 pip).
- **Exit geometry (spec 08 §5.8):** a time-exit drift trade has **no natural ATR stop/target**
  — the position is held for a fixed clock window. A protective stop would be set at
  **~1.5×ATR** (wide, because the edge is a slow drift that must not be noised out — the
  late-session-drift lesson) with **no fixed target** (exit on the clock). R:R is defined by
  realized drift vs the 1.5×ATR stop. This geometry is dictated by the mechanism (calendar,
  not structure); it deliberately does **not** inherit the incumbent's 1.2×ATR / 1R.
- Params that would become levers: leg open/close UTC hours, protective-stop ATR multiple.

## Probe (the gate this never cleared)
Rather than spend a trial, I measured the realized directional drift of each leg directly on
`state/parquet/eurusd_m15.parquet` (59,993 M15 bars, 2024-01 → 2026-05) and compared it to the
backtest's own round-trip cost.

**Cost reference.** CostModel + `config/default.yaml`: half-spread (median spread 0.15 pip in
liquid hours → ~0.15 pip round-trip), slippage 1.0 pip/side (2.0 pip round-trip), commission
$3/lot/side ≈ 0.6 pip round-trip ⇒ **≈ 2.6 pip per single directional leg** (entry + exit).
The two-leg London-short/NY-long programme pays this **twice** per day.

| leg (UTC) | direction | n (days) | mean drift | std | t-stat | net @ 2.6p cost | win rate |
|---|---|---|---|---|---|---|---|
| 07→13 | short (EUR home) | 625 | −0.443 p | 29.0 | −0.38 | −3.04 p | 50.7% |
| 13→17 | long (US hours) | 625 | −0.092 p | 25.0 | −0.09 | −2.69 p | 49.9% |
| 08→12 | short (EUR home) | 625 | +0.539 p | 18.1 | +0.75 | −2.06 p | 53.6% |
| 14→20 | long (US hours) | 625 | −0.403 p | 26.3 | −0.38 | −3.00 p | 49.0% |
| 09→14 | short (pre-ECB-fix) | 624 | −0.289 p | 26.1 | −0.28 | −2.89 p | 49.0% |

Day-of-week full-day drift (00:00→20:45 UTC close): Mon +4.98 p (t +1.21), Tue +1.11 (t +0.27),
Wed −3.61 (t −0.86), Thu +0.11 (t +0.02), Fri −0.19 (t −0.05). **No day is significant** and
each would be a single high-variance round trip.

**Reading.** Not one leg is statistically distinguishable from zero (|t| ≤ 0.75); the
best-signed leg (+0.539 pip, 08→12 short) is both insignificant *and* ≈ −2.1 pip after cost.
The directional drift the literature describes is present only as an un-harvestable
sub-cost wisp on this sample. The effect is **real but not tradeable** — exactly the
documented outcome.

## Implementation notes
**None — no code was written.** The candidate was killed at triage by the data probe, so no
indicator, Strategy module, registry line, or test was added. `src/`, `state/`, and the live
path are untouched. No trial-ledger entry (no backtest run); DSR budget unaffected. The probe
script was run ad-hoc against the parquet and not committed (read-only analysis).

## Backtest results
None. Probe-rejected before the backtest stage (spec 08 §3 stage-3 triage; §8 "most ideas die
at stage 3 for free"). Spending a `--walkforward` trial on a leg with |t| < 0.8 and a negative
net-of-cost mean would have burned DSR budget to confirm what the probe already shows.

## Verdict
**Probe-rejected (no trial spent).** The invoice/home-away intraday directional effect is real
in sign-structure but un-harvestable on EURUSD M15 after costs: every leg insignificant,
raw drift ≤ 0.55 pip vs ~2.6 pip cost, day-of-week insignificant. The earlier differentiation
from [[2026-06-09-late-session-drift]] (liquid hours, not thin) was correct but did not save
it — the binding constraint was never the spread, it was the *size of the drift*. **The
seasonality / fixed-time-of-day directional family is closed on the current data** unless a
materially larger conditional drift is found. Trial budget remaining this week unchanged
(2026-W25: 2 spent of 10 → **8 remaining**).

## Lessons
1. **Liquid-hour seasonality fails on drift size, not spread.** We already knew thin-hour
   drift dies to spread ([[2026-06-09-late-session-drift]]). This probe isolates the other
   failure mode: even in the tightest-spread hours (0.15 pip), the home/away drift (≤ 0.5 pip)
   is an order of magnitude below the *all-in* round-trip cost (commission + slippage ≈ 2.6
   pip). Cheap spread does not rescue a sub-pip edge — the floor is the full cost stack.
2. **t-stat triage is a free DSR saver.** A 30-second per-leg t-test (|t| < 0.8 across five
   leg definitions) is decisive evidence to *not* spend a trial. Codify this: any new
   fixed-time directional idea must clear a per-leg `mean/cost > 1` and `|t| > 2` probe before
   it earns a backtest.
3. **Two-leg programmes pay cost twice.** A London-short + NY-long day incurs ~5.2 pip of
   round-trip cost against a combined raw drift well under 1 pip — structurally hopeless. Any
   future seasonal idea should be single-leg and condition the entry on something that lifts
   the conditional drift far above cost.
4. Reinforces the standing **raw-pip ≠ R-edge** principle now from a third angle
   (drift-magnitude, after thin-spread and serial-correlation angles).

## Next steps
- Seasonality directional family marked closed on current data; do not re-test a plain
  time-of-day leg without a new conditioning mechanism that demonstrably lifts the per-leg
  drift above ~3 pip.
- Queued differentiated variants (see INDEX idea queue) that condition the *direction* on
  state rather than the clock alone, each requiring its own pre-test probe:
  - **ECB-fix conditional reversion** — only fade the pre-fix EUR move on days where the
    build-up exceeds k×ATR (a magnitude condition, not a fixed clock). Probe the conditional
    post-fix drift first.
  - **Event-window momentum** — the hourly scan shows the only large, liquid-hour signals
    cluster at the US-data window (11→15 UTC: +0.25/bar at 12:00, −0.21/bar at 15:00). A
    volatility-expansion entry there is a *breakout* mechanism, not seasonality — already at
    risk from the level-fill artifact ([[2026-06-15-resting-stop-and-market-entry]]); only
    worth it with a genuinely live-fillable market trigger.
- A longer history export would tighten these t-stats but cannot change the cost arithmetic;
  this is a magnitude problem, not a sample-size one.
