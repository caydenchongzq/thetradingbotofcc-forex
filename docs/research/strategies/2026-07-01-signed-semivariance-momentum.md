---
id: 2026-07-01-signed-semivariance-momentum
name: SignedSemivarianceMomentum
family: trend
status: probe-rejected
related: [2026-06-07-intraday-ts-momentum, 2026-06-23-vol-conditioned-intraday-momentum, 2026-06-29-asian-session-drift-signal, 2026-06-15-resting-stop-and-market-entry]
sources: ["https://www.sciencedirect.com/science/article/abs/pii/S0927539823000245", "https://ideas.repec.org/a/eee/empfin/v72y2023icp54-77.html", "https://public.econ.duke.edu/~boller/Papers/SemiVar.pdf"]
trials_used: 0
verdict: "Signed-semivariance (good/bad variance) imbalance carries NO directional information on EURUSD M15: |corr(signal,fwd)| <= 0.03 across all L/H/thr, best gross 0.49p vs 2.6p cost, win 48-52%. Variance decomposition adds nothing over raw drift; extends the closed trend/momentum family. No trial."
---

# SignedSemivarianceMomentum — does the good/bad-variance imbalance predict the next move?

## Hypothesis & market rationale
Realized variance over a window decomposes into an upside (RS+, "good") and a downside
(RS−, "bad") semivariance; their normalized imbalance `s = (RS+ − RS−)/(RS+ + RS−)` is the
signed-jump variation. The literature (below) reports that on equity indices and commodity
futures `s` carries *directional* information beyond raw momentum — the composition of past
variance, not just its magnitude or the raw return sign, separates continuation from
reversal. **Falsifiable claim:** on EURUSD M15, the sign of `s` over a lookback L predicts the
sign of the forward H-bar return with an edge that clears the ~2.6p round-trip cost. If the
signal is a coin-flip (|corr| ≈ 0, gross << cost), the claim is false.

## Sources
- Journal of Empirical Finance v72 (2023) "Time series momentum and reversal: intraday
  information from realized semivariance" — https://www.sciencedirect.com/science/article/abs/pii/S0927539823000245 · https://ideas.repec.org/a/eee/empfin/v72y2023icp54-77.html
- Bollerslev, Li, Zhao "Good and bad volatility / realized semi(co)variances" —
  https://public.econ.duke.edu/~boller/Papers/SemiVar.pdf
- Discovered via the SOURCES.md academic tier (SSRN/ScienceDirect q-fin) crawl 2026-07-01.
  Community code NOT used; mechanism re-implemented pure in the probe script.

## Relation to prior library work
Directly extends the **closed trend/momentum family**: [[2026-06-07-intraday-ts-momentum]]
(early→late session return corr 0.026), [[2026-06-23-vol-conditioned-intraday-momentum]]
(vol-conditioning inverts, corr −0.12 to −0.03), [[2026-06-29-asian-session-drift-signal]]
(cross-session corr 0.046). **What is different (required by §4.3):** every prior probe used
the RAW signed close-to-close drift as the predictor. This one uses a genuinely new
construction — the *variance decomposition* (upside vs downside semivariance), which is
orthogonal to raw drift in principle and is the specific signal the 2023 paper credits with
directional content. So the probe was legitimate: a new predictor, not a re-run of a rejected
one. The verdict, however, joins the same family. Also relevant: the breakout finding
[[2026-06-15-resting-stop-and-market-entry]] — EURUSD M15 intraday extension chops/reverts
more than it continues, so a persistence signal has no raw edge to harvest.

## Strategy spec (as probed)
Signal at close of bar i: `s_i = (RS+ − RS−)/(RS+ + RS−)` over the last L M15 bars, using
per-bar close-to-close pip returns. Enter in the sign of `s_i` (continuation) or against it
(reversal) when `|s_i| >= thr`, restricted to liquid hours (07:00–20:00 UTC). Forward return
measured over H bars. Grid: L ∈ {8,16,32}, H ∈ {1,4,8,16}, thr ∈ {0.0,0.3,0.5}, both modes.
Cost 2.6p round-trip. No exit geometry was specced because the a-priori predictability probe
failed first (per §5 the entry must clear an a-priori edge before a trial is spent).

## Implementation notes
Probe only: `scripts/probe_signed_semivariance_momentum.py` (pure pandas/numpy, reads the
parquet read-only). No indicator added to `src/`, no Strategy class, no registry entry, no
trial. pytest untouched (no `src/` change). No writes to `state/` or the live path.

## Backtest results
No backtest run — the a-priori probe (below) is decisive, so no trial was spent (§4.3).

`python3 scripts/probe_signed_semivariance_momentum.py` (2024-01-01..2026-05-29, 32,498
liquid-hour entries at thr=0):

| L | H | thr | mode | corr(s,fwd) | gross (p) | net (p) | win% |
|---|---|---|---|---|---|---|---|
| 8 | 8 | 0.5 | rev | −0.032 | **+0.489** (best gross) | −2.11 | 51.9 |
| 8 | 1 | 0.0 | cont | −0.009 | −0.030 | −2.63 | 48.4 |
| 16 | 16 | 0.3 | cont | +0.003 | +0.121 | −2.48 | 49.3 |
| 32 | 8 | 0.3 | cont | +0.013 | +0.254 | −2.35 | 49.0 |
| all cells | — | — | — | **|corr| ≤ 0.03** | **|gross| ≤ 0.49** | **≤ −2.1** | **48–52** |

Every one of the 72 (L×H×thr×mode) cells: |correlation| ≤ 0.03, win rate 48–52% (coin flip),
gross expectancy a fraction of a pip and always < 20% of the 2.6p cost, net deeply negative.
The lone positive-gross cells sit at data-mined threshold/horizon corners with no monotonic
gradient and t-stats that flip sign between adjacent cells — noise, not signal.

## Verdict
**PROBE-REJECTED, no trial spent.** The signed-semivariance imbalance has no directional
predictive content on EURUSD M15. Fails the a-priori edge test by ~5× on gross vs cost before
any exit geometry or gate is even relevant. W27 trial budget untouched (10/10); cumulative
trials remain 171.

## Lessons
The variance *decomposition* (good vs bad volatility) adds no directional information over the
raw drift the trend/momentum family already found null — on 24h EURUSD M15, `corr(s, fwd) ≈ 0`
just as `corr(raw drift, fwd) ≈ 0`. The equity/commodity result does not transfer: those
markets have an overnight-close information-concentration and a leverage/asymmetric-vol channel
that a continuously-traded major FX pair lacks. **Generalizable:** re-parameterizing a null
directional signal (raw return → semivariance imbalance → …) keeps returning null because the
binding fact is that EURUSD M15 has no exploitable directional serial dependence at these
horizons, not that we picked the wrong statistic. Directional-persistence constructions on
OHLCV are exhausted; the trend/momentum family stays closed. Future directional ideas need a
genuinely exogenous conditioner (news release, cross-asset, order flow) — all blocked-on-data.

## Next steps
Trend/momentum family remains CLOSED across raw drift, vol-conditioning, cross-session, and now
variance-decomposition. Do not re-test another OHLCV-derived directional statistic without a
mechanism that is not a function of past price/return alone. The live levers are the standing
blocked-on-data items: news-release momentum, cross-currency/volume reversal, order-flow signals
(see idea queue).
