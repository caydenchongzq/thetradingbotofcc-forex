---
id: 2026-06-07-asian-sweep-fade
name: AsianSweepFade
family: mean-reversion
status: idea
related: [2026-06-02-session-breakout-er]
sources: ["https://fxopen.com/blog/en/what-is-ict-turtle-soup-and-how-can-you-use-it-in-trading/", "https://dailypriceaction.com/blog/liquidity-sweep-reversals/", "https://www.forexfactory.com/thread/1349219-eurusd-london-session-manipulation-amd"]
trials_used: 0
verdict: "Queued: fade false breakouts of the Asian range in early London (turtle-soup); practitioner-only evidence, no quantified backtests found — the harness must arbitrate."
---

# AsianSweepFade — fade the failed Asian-range breakout at London open

## Hypothesis & market rationale
London open sweeps the Asian-session high/low to trigger stops, then reverses back into
the range ("liquidity sweep" / ICT turtle soup / AMD). Falsifiable: short after a bar
trades above the Asian high then CLOSES back inside the range (mirror for longs), stop
beyond the sweep extreme, single 1R target (incumbent exit machinery — no live-mirror).
Mean-reversion family — complements the breakout incumbent; opposite session logic, so
no overlap with its 13:00–16:00 window.

## Sources
Practitioner-only (FXOpen, DailyPriceAction, ForexFactory AMD thread). The 2026-06-07
web sweep found NO quantified public backtests — treat the hypothesis as low-prior.

## Relation to prior library work
New family; no library overlap. Entry/exit fits the existing Signal/ManageDecision seam.

## Strategy spec (draft)
Asian range = London 00:00–08:00 H/L (M15). Window 08:00–11:00. Sweep = bar high >
asian_high (+buf) AND close < asian_high ⇒ short at close, SL above sweep high
(max(structure, 1.2×ATR)), TP 1R, one-shot per side, same regime/news gates as incumbent
(ER gate likely INVERTED — chop favors reversion; decide before testing, a priori).
Trade-count headroom looks adequate (sweeps are frequent), but verify with the cheap
probe before the gated run (lesson from [[2026-06-07-pre-session-compression-filter]]).

## Next steps
Strongest queued candidate for a future run with budget: new strategy module via the
registry playbook; 1 trial.
