---
id: 2026-06-29-asian-session-drift-signal
name: AsianSessionDriftSignal
family: trend
status: probe-rejected (no trial)
related: [2026-06-09-late-session-drift, 2026-06-23-vol-conditioned-intraday-momentum, 2026-06-17-intraday-seasonality-drift]
sources:
  - "https://arxiv.org/abs/2409.04471 (Guyard & Deriaz 2024, EUR/USD directional ML — cited for cross-session temporal structure)"
  - "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3584014 (Liu et al. 2023, TS momentum & realized semivariance, commodity futures)"
trials_used: 0
verdict: "Asian session direction (00:00–07:00 UTC) has zero predictive power over London session direction: corr=0.046, gross=0.25p vs 2.6p cost. PROBE REJECT."
---

## Hypothesis & Market Rationale

Asian-session (00:00–07:00 UTC) EURUSD drift as a directional conditioning signal for the
London session (07:00–16:00 UTC): if EURUSD drifted UP in Asia, enter LONG at the London
open (continuation), OR fade the Asia direction (reversal). The mechanism for **continuation**:
Asian buyers hold into London, creating positive serial correlation across sessions. The
mechanism for **reversal**: London participants see the Asian drift as an overshoot and trade
against it (the "London clears the overnight order book" narrative).

This idea is genuinely distinct from prior library work:
- [[2026-06-09-late-session-drift]]: tested INTRA-session late drift (PM USD), rejected on spread
- [[2026-06-23-vol-conditioned-intraday-momentum]]: tested vol-conditioned INTRADAY momentum,
  rejected on signal inversion
- [[2026-06-17-intraday-seasonality-drift]]: tested fixed-time-of-day invoice-effect direction

AsianSessionDriftSignal is a **cross-session** conditioning signal (not intraday, not fixed clock).
It uses the actual signed return of the Asian session as a daily predictor of London direction.

## Sources (cited)

- Guyard & Deriaz (2024, arXiv 2409.04471): EUR/USD directional forecasting — cited for the
  temporal structure of EURUSD daily/session returns; no cross-session signal is documented.
- Liu, Lu, Li & Wang (2023, JEF): "Time series momentum and reversal: intraday information from
  realized semivariance" — commodity futures; motivates using intraday signed return information
  as a conditioning signal. Does NOT transfer claim to FX M15.

## Relation to Prior Library Work

No prior library entry tested the Asian-session DIRECTION (signed drift) as a London-open signal.
The [[2026-06-24-asian-range-london-breakout]] tested a LEVEL breakout of the Asian range (not
the directional drift). The seasonality family used FIXED-TIME directional legs, not a
drift-conditioned signal. The differentiation passes §4.3: the mechanism (cross-session drift
as signed predictor) has not been probed before.

## Strategy Spec

- **Entry**: Market LONG at London open (07:00 UTC) if Asian session return > 0 (continuation
  variant), or SHORT if Asian return > 0 (reversal variant).
- **Asian return**: Close of 06:45 UTC bar minus Open of 00:00 UTC bar.
- **Stop**: ~1.5×ATR below/above entry (not designed in detail — probe first).
- **Target**: Not specified (probe only — no geometry decision reached).
- **Exit geometry decision**: Not reached (probe rejected before design stage).

## Probe Results

**Data**: 59,993 M15 bars, 2024-01-01 to 2026-05-29 (625 complete trading days with both
Asian and London sessions fully populated).

| Metric | Value |
|--------|-------|
| Asian UP days | 309 |
| Asian DOWN days | 314 |
| Pearson correlation (Asian→London session return) | **0.0465** |
| Continuation gross (trade London in Asian direction) | **+0.25p** |
| Continuation net (after 2.6p cost) | **−2.35p** |
| Continuation t-stat / p | 0.17 / 0.863 |
| Reversal gross (fade Asian direction) | **−0.25p** |
| Reversal net | **−2.85p** |
| Reversal t-stat / p | −0.17 / 0.863 |
| Cost gate (minimum for trial) | 2.6p gross |

**Verdict: PROBE REJECT — NO TRIAL.**

The Asian session direction is entirely uncorrelated with London session direction (r = 0.046,
p = 0.86). Both the continuation and reversal signals produce gross of ≤ 0.25p vs the 2.6p
cost stack — a 10× shortfall. The signal is indistinguishable from noise.

## A/B vs Incumbent HEAD

Not applicable — probe rejected before building.

## Verdict

**PROBE REJECTED (no trial).** The cross-session directional persistence between the Asian
session and the London session is zero on 2024–2026 EURUSD M15. This is fully consistent with
the closed seasonality/drift/trend families:

- Intraday momentum within sessions: null (corr≈0.026, [[2026-06-23-vol-conditioned-intraday-momentum]])
- Time-of-day directional drift: null (|t|<0.8, [[2026-06-17-intraday-seasonality-drift]])
- Cross-session drift: null (corr=0.046, this probe)

EURUSD M15 2024–2026 shows no directional serial correlation on any temporal horizon —
intrabar, intraday, or cross-session. 0 trials spent (W27 budget 10/10 remaining).

## Lessons

1. **Cross-session serial correlation is zero**: EURUSD M15 does not trend across session
   boundaries any more than it does within sessions. The "London fades Asia" and "London
   follows Asia" narratives are equally false on this data; the London session direction is
   essentially a coin-flip relative to Asian drift.
2. **The signal trinity is closed**: Continuation (n=625, gross 0.25p), reversal (gross −0.25p),
   and neutrality all fail the cost gate — there is no directional information in Asian drift.
3. **Implication for all session-signal ideas**: Any strategy that uses the DIRECTION of one
   FX session to position for the next (carry-forward, overnight gap, Asia-to-London bias) is
   probe-rejected a-priori on this data. Needs a conditioning mechanism that lifts per-leg
   drift above 3p — none found so far.

## Next Steps

None — idea closed. Broader context: the directional signal space on 2024-2026 EURUSD M15 is
exhausted (see INDEX "Closed families"). Real unblocking lever remains a longer data export
and/or second instrument.
