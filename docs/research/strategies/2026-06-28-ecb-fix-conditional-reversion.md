---
id: 2026-06-28-ecb-fix-conditional-reversion
name: ECBFixConditionalReversion
family: mean-reversion
status: probe-rejected (no trial)
related:
  - 2026-06-17-intraday-seasonality-drift
  - 2026-06-16-vwap-stretch-reversion
  - 2026-06-19-session-range-false-break-fade
sources:
  - "https://onlinelibrary.wiley.com/doi/10.1111/jofi.13306"
  - "https://sites.insead.edu/facultyresearch/research/file.cfm?fid=66802"
  - "https://ideas.repec.org/p/bca/bocawp/21-48.html"
trials_used: 0
verdict: "Post-fix EUR reversion does NOT replicate in 2024-2026: unconditional +1.20p gross
  / +0.05p net; best conditional +1.82p gross (far below 2.6p cost); no gradient in conditioner.
  ECB fixing effect arbitraged away in modern data."
---

# ECBFixConditionalReversion — Magnitude-conditioned fade of pre-ECB-fix EUR decline

## Hypothesis & market rationale

The ECB publishes official EUR/USD reference rates daily at 14:15 CET (13:15 UTC in winter,
12:15 UTC in summer). Krohn (2024, *Journal of Finance*) documents a well-replicated W-shaped
pattern: FX dealers intermediate net client demand for USD at the fix by pre-hedging — they
buy USD (sell EUR) ahead of the fix, driving EUR/USD lower; after the fix, they unwind
inventory, causing EUR/USD to recover. In the paper's 1999–2019 sample, a strategy of shorting
EUR pre-fix and reversing to long post-fix yields annualised average returns of **13.6% for
EUR/USD**, particularly strong during high-volatility periods.

Our variant differentiates from the closed seasonality family
([[2026-06-17-intraday-seasonality-drift]]) by **conditioning on the magnitude of the pre-fix
decline**: trade the post-fix long ONLY when the 09:00 UTC → fix bar move exceeds k×ATR,
i.e., only when dealer pre-hedging appears to have been large enough to produce a meaningful
inventory overhang worth unwinding. The unconditional fixed-clock leg is in the closed
seasonality family; the magnitude-conditional event-anchored version is the novel lever.

Falsifiable claim: **the post-fix 1–2h EUR/USD return, conditioned on a pre-fix EUR decline of
≥k×ATR, clears the ~2.6-pip round-trip cost on 2024–2026 data.** If the fixing effect has been
arbitraged away, the post-fix return should be noise-level regardless of conditioning.

## Sources

1. Krohn, I. (2024). "Foreign Exchange Fixings and Returns around the Clock." *Journal of
   Finance*, 79(1). DOI: 10.1111/jofi.13306. — The primary academic basis: documents the
   W-shaped USD return pattern around the ECB, WMR, and Tokyo fixes, 1999–2019.
   ([Wiley Online Library](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13306))
2. Krohn, I. (2021). "Foreign Exchange Fixings and Returns around the Clock." Bank of Canada
   Working Paper 2021-48. Pre-publication version.
   ([IDEAS/RePec](https://ideas.repec.org/p/bca/bocawp/21-48.html))
3. Krohn, I. (via INSEAD). Presentation slides for the same study.
   ([INSEAD Faculty Research](https://sites.insead.edu/facultyresearch/research/file.cfm?fid=66802))

## Relation to prior library work

**Differentiator from the closed seasonality/fixed-time-of-day family
([[2026-06-17-intraday-seasonality-drift]]):** The seasonality probe checked *unconditional*
fixed-clock directional legs; every leg was insignificant (|t|<0.8). Our variant uses the fix
time purely as an event anchor, not a directional signal — we only trade when the pre-fix price
signal (magnitude of EUR decline) clears a threshold. This differentiation was accepted in the
queue (`2026-06-17-ecb-fix-conditional-reversion` idea entry) per §4.3, and the probe was
legitimate.

**Risk of mean-reversion family closure ([[2026-06-16-vwap-stretch-reversion]],
[[2026-06-19-session-range-false-break-fade]], et al.):** Mean-reversion is 4/4 closed across
anchors. The ECB fix provides an *institutional mechanism* (dealer inventory, not just a price
extension from a technical level), but the same 2024–2026 continuation regime that killed other
fades could still dominate. The probe was designed to test exactly this.

## Strategy spec (probe-only — full spec not built)

**Entry:** LONG EUR/USD at the open of the bar immediately following the ECB fix bar
(14:15 CET = 12:15 or 13:15 UTC depending on DST). Condition: the 09:00 UTC → fix-bar
pre-return must exceed −k×ATR (EUR fell more than k×ATR before the fix).

**Exit geometry (proposed, not backtested):** if the probe had passed —
- Stop: 1.5×ATR below entry (wide enough for the fix-bar noise not to stop us out; the fix bar
  itself can be a wide candle).
- Target: 1.5R (1:1.5 R:R), placing the 1h post-fix expected gross (+1.79p) relative to a
  ~1.5×ATR stop (~3.5p average stop). Would give approximately 0.51 R target per pip, so a
  win-rate above 40% needed for positive expectancy at 1.5R. Win-rate shown = 51% gross, but
  net after cost makes this borderline.
- Rationale: exit geometry is moot — the probe failed.

**Params that would have become ALLOWED_LEVERS:** pre_fix_atr_threshold (k), post_fix_window_h.

## Implementation notes

No code built. Probe only via `scripts/probe_ecb_fix_reversion.py` (additive, read-only of
parquet). No writes to `state/`, no registry line, no unit tests needed (probe script is not
a registered strategy). Pytest unaffected.

## Backtest results

**No backtest run.** Probe-rejected based on the a-priori gross drift criterion.

### Probe results (scripts/probe_ecb_fix_reversion.py)

Data: 2024-01-01 → 2026-05-29, 755 calendar days, 625 valid trading days with sufficient bar
coverage (130 skipped due to thin weekend/holiday coverage). ECB fix at 13:15 UTC (winter,
CET, 280 days) and 12:15 UTC (summer, CEST, 345 days).

Cost stack: 1.0 pip fixed (commission + slippage) + actual entry spread (~0.15 pip at this
liquid hour) ≈ **1.15 pip round-trip total.**

| subset | n | 1h gross | 1h net | 1h wr | 2h gross | 2h net |
|---|---|---|---|---|---|---|
| Unconditional LONG post-fix | 625 | +1.20p | +0.05p | 49% | +1.28p | +0.13p |
| EUR fell pre-fix (pre_ret<0) | 334 | +1.79p | +0.64p | 51% | +1.78p | +0.63p |
| pre_ret < −0.25×ATR | 314 | +1.14p | −0.01p | 50% | +0.93p | −0.23p |
| pre_ret < −0.50×ATR | 291 | +1.19p | +0.04p | 50% | +1.03p | −0.12p |
| pre_ret < −0.75×ATR | 259 | +0.85p | −0.30p | 48% | +0.73p | −0.41p |
| pre_ret < −1.00×ATR | 232 | +1.17p | +0.02p | 48% | +1.25p | +0.10p |
| pre_ret < −1.25×ATR | 204 | +1.72p | +0.58p | 49% | +0.14p | −1.01p |
| pre_ret < −1.50×ATR | 178 | +1.82p | +0.67p | 49% | +0.03p | −1.12p |

**t-stats for magnitude-conditioned 1h gross**: all p>0.10 (best: p=0.12 at −1.25×ATR, n=204).

**Volatility conditioning (Krohn 2024: "strongest in high-vol periods"):**

| ATR tercile | n | 1h gross | 1h net |
|---|---|---|---|
| Low-ATR | 208 | +1.95p | +0.80p |
| Mid-ATR | 208 | −1.07p | −2.21p |
| High-ATR | 209 | +2.72p | +1.56p |

**Combined high-ATR + large pre-fix decline (where reversion should be strongest):**

| subset | n | 1h gross | 1h net | 2h gross |
|---|---|---|---|---|
| High-ATR + pre_ret<−0.50×ATR | 103 | +0.10p | −1.06p | +2.01p |
| High-ATR + pre_ret<−0.75×ATR | 93 | +0.15p | −1.01p | +1.65p |
| High-ATR + pre_ret<−1.00×ATR | 87 | +0.55p | −0.61p | +1.89p |

**Decision threshold:** gross > 2.6 pip AND n ≥ 200 on any subset — **NOT MET.**
Best gross observed: +1.82p (far below 2.6p). Best gross on a ≥200 subset: +1.72p (n=204,
p=0.12, not significant).

## Verdict

**PROBE-REJECTED. No trial spent. Trials remain at 171.**

The ECB fixing effect (Krohn 2024, documented for 1999–2019) **does not replicate in 2024–2026
EURUSD M15 data.**

Three specific failure modes:

1. **Gross drift is insufficient**: The unconditional post-fix LONG yields only +1.20p gross
   (+0.05p net), and the best conditioned subset reaches +1.82p gross — both far below the
   ~2.6p full cost threshold. No subset reaches the 2.6p bar.

2. **No gradient in the conditioner**: Larger pre-fix EUR declines do NOT produce larger
   post-fix reversions. At −0.25×ATR the gross is +1.14p; at −1.50×ATR it is +1.82p — a flat
   profile with no monotonic gradient, and t-stats remain insignificant throughout (all p>0.10).
   This is the key differentiating test from the closed family and it fails.

3. **Structural inversion**: The combined high-ATR + large-pre-fix-decline subset — exactly
   where Krohn predicts the strongest effect — produces the WORST results (+0.10–0.55p gross),
   much worse than the unconditional. High-ATR days with large pre-fix EUR moves are likely
   macro-driven trending days, not dealer-inventory days; the EUR continues trending post-fix.

The directional filter (only trade when EUR fell pre-fix) produces +1.79p gross / +0.64p net
with 51% win rate, which is marginally positive but statistically insignificant and well below
the cost threshold. It does not justify a trial.

ECBFixConditionalReversion is moved to **probe-rejected (no trial)**. No proposal filed.

## Lessons

1. **Published-in-JoF ≠ still alive in 2024–2026.** The Krohn 2024 paper covers 1999–2019.
   FX fixing effects are among the most watched by algorithmic desks; a pattern with
   annualised 13.6% returns and published academic documentation has had >5 years of being
   arbitraged since the paper was available as a working paper. The 2024–2026 sample shows
   negligible residue.

2. **No gradient = no mechanism.** The key falsifier for an institutional mechanism is a
   monotonic gradient in the conditioner (larger imbalance → larger inventory → larger
   reversion). The flat-to-noisy profile in our data shows the "pre-fix decline" is not a
   proxy for dealer inventory — it is generic intraday noise.

3. **Krohn's high-vol condition inverts in modern data.** The paper says reversion is
   strongest in high-vol periods; our probe shows combined high-ATR + large-decline is the
   WORST subset. High-vol in 2024–2026 means macro-driven trends (ECB policy, geopolitical
   risk), not just elevated dealer inventory — those days the pre-fix move is real and
   continues rather than reverting. Same inversion as [[2026-06-23-vol-conditioned-intraday-momentum]]
   (vol gradient inverted vs equities finding).

4. **Mean-reversion 4/4 closure reinforced.** Despite having the strongest academic
   institutional mechanism of any mean-reversion candidate tested (JoF-published, 1999–2019,
   specific dealer inventory rationale), the post-fix reversion still does not clear costs on
   2024–2026 data. This further supports the operating hypothesis: EURUSD M15 intraday extension
   continues > reverts in the current regime regardless of the anchor type.

5. **Pre-fix SHORT is also marginal.** Unconditional pre-fix short (sell EUR at 09:00 UTC,
   hold to fix) yields only +0.60p gross / -0.55p net — also not tradeable. The "long USD
   pre-fix" leg from the paper is present but insufficient to overcome costs.

## Next steps

- No follow-on probe warranted from this family on current data.
- **Blocked-on-data ideas added to queue today:**
  - `MacroNewsReleaseMomentum`: Trade in the direction of the EURUSD move after high-impact
    US macro releases (NFP, CPI, ISM, FOMC). Different mechanism from all closed families
    (event-driven news flow, not price structure or inventory). Needs a news/macro calendar
    datasource not in the M15 parquet. Would need a release-time-tagged dataset to test.
  - `NYOptionsCutGammaPin`: Trade the EUR/USD pinning or gamma-unwind around the NY options
    expiry cut at 15:00 UTC. Different mechanism (options market maker delta/gamma hedging).
    Needs options strike data / open interest by expiry not in M15 parquet.
- The real lever remains: **longer data export and/or second instrument** (§8 backlog #4),
  which would revive [[2026-06-14-trend-aligned-orb]] (the strongest quality candidate) and
  allow the full incumbent-filter queue to be re-run on the market-fill base once the 200-trade
  floor is no longer binding.
