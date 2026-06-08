---
id: 2026-06-08-london-fix-reversal
name: LondonFixReversal
family: mean-reversion
status: idea
related: [2026-06-08-asian-sweep-fade]
sources: ["https://arxiv.org/pdf/1501.07778", "https://www.researchgate.net/publication/228692589_Foreign_exchange_reversals_in_New_York_time", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6087107"]
trials_used: 0
verdict: "Queued: fade the pre-fix drift after the 16:00 London WM/R fix; paper-backed (fix-window price pressure reverts post-fix, strongest month-end). M15 data sufficient."
---

# LondonFixReversal — post-4pm-fix mean reversion

## Hypothesis & market rationale
Dealer hedging of benchmark-tracking client flow concentrates in the minutes around the
16:00 London WM/R fix; documented effect (Evans, arXiv:1501.07778) is a pre-fix price
drift that partially REVERTS after the fix — strongest on month-end days when index
rebalancing flow is largest. This is one of the few *paper-backed* intraday FX anomalies,
unlike the practitioner-only sweep lore just rejected in [[2026-06-08-asian-sweep-fade]].
Falsifiable M15 spec (to be frozen a priori before any trial): measure the 15:00–16:00
London drift; if |drift| exceeds a volatility-scaled threshold, enter AGAINST it on the
16:00 close, single 1R target, stop 1.2×ATR, flat by 18:00 London.

## Relation to prior library work
Mean-reversion family like the rejected sweep fade, but the failure mode there
(win > 50%, avg loss ≫ avg win from structure-wide stops) does not transfer: this entry
uses a pure ATR stop (no structural-extreme stop), a different driver (benchmark flow,
not stop-runs), and a time-boxed exit. Differentiation recorded per spec 08 §4.3.
Caution: trade count — only ~1 setup/day max, threshold-gated; run the cheap probe first
(compression-filter lesson) to verify ≥ 200-trade headroom before the gated run.

## Next steps
Freeze drift threshold + windows a priori from the paper; single config, no sweep;
verify trade-count headroom by probe; then one trial.
