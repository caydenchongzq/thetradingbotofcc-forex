---
id: 2026-06-07-intraday-ts-momentum
name: IntradayTSMomentum
family: trend
status: idea
related: []
sources: ["https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752", "http://wp.lancs.ac.uk/fofi2020/files/2020/04/FoFI-2020-092-Zeming-Li.pdf", "https://alphaarchitect.com/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/"]
trials_used: 0
verdict: "Queued: first-session return predicts last-session return (Gao/Han/Li/Zhou 2015; international evidence). Evidence is for EQUITY indices; FX analog (London a.m. return → NY p.m. return) unproven — needs a-priori window spec before spending a trial."
---

# IntradayTSMomentum — early-session return predicts late-session return

## Hypothesis & market rationale
Gao, Han, Li & Zhou (2015): first half-hour return predicts the last half-hour
(S&P ETFs; ~15–19% annualized in sorts), strongest on volatile/news days; Li (2020)
extends internationally. Driver: informed-trader positioning + late-day rebalancing.
FX analog (falsifiable): sign of the London 08:00–10:00 EURUSD return predicts the
19:00–21:00 London return. FX evidence is thin (RUB/USD study only) — low prior,
but cheap to specify honestly.

## Relation to prior library work
New family (intraday trend). Distinct from the breakout incumbent (no range logic).
Late-NY window has wide spreads in the cost model — expect costs to eat the edge;
the probe-first lesson from [[2026-06-07-pre-session-compression-filter]] applies.

## Next steps
Before any trial: fix windows a priori from the papers, single config, no sweep.
