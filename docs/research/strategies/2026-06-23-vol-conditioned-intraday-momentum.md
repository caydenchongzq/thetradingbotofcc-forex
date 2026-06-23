---
id: 2026-06-23-vol-conditioned-intraday-momentum
name: VolConditionedIntradayMomentum
family: trend
status: probe-rejected
related: [2026-06-07-intraday-ts-momentum, 2026-06-09-late-session-drift, 2026-06-17-intraday-seasonality-drift]
sources: ["https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866", "https://www.sciencedirect.com/science/article/abs/pii/S0304405X18301351", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752", "https://www.diva-portal.org/smash/get/diva2:1878991/FULLTEXT01.pdf", "https://www.quantifiedstrategies.com/day-trading-momentum-strategy/"]
trials_used: 0
verdict: "Probe-rejected, NO trial. Gao-Han-Li-Zhou volatility-conditioned intraday momentum does NOT transfer to EURUSD M15: the vol gradient is INVERTED vs equities — high first-window-vol days mildly REVERSE into the afternoon (corr up to -0.120, gross -2.7p) rather than continue. No conditional subset clears the ~3-pip cost bar with a positive vol gradient; the lone marginal cell (Asia->London top-25%|r1|, net +1.75p) is sub-cost, thin-hour and 1-of-25 (multiple comparisons). Conditioning by volatility does NOT reopen the closed seasonality/intraday-momentum family."
---

# VolConditionedIntradayMomentum — first-window return predicts last-window return, *amplified on high-volatility days*

## Hypothesis & market rationale
Gao, Han, Li & Zhou (*Market Intraday Momentum*, JFE 2018) show that on the S&P 500 the
first half-hour return (since the prior close) positively predicts the last half-hour return,
and — the part this candidate turns on — the predictability is **stronger on high
first-window-volatility days, high-volume days, and macro-news days** (R² rises to ~3.3% when
first-hour volatility is high). The economic story is under-reaction to a volatility/information
shock that concentrates informed trading at the open and resolves at the close; the shock is
larger (more to under-react to) precisely when early volatility is high.

Falsifiable claim for EURUSD M15: **on days where the session-opening window's realized
volatility is high, a position taken at the start of a later liquid window in the direction of
that opening window's return earns a directional drift that exceeds round-trip costs (~2.6 pip).**
If true, the drift should (a) be positive and (b) grow monotonically from the low-vol to the
high-vol tercile.

## Sources
- Gao, Han, Li, Zhou — *Market Intraday Momentum*, SSRN 2440866 / *J. Financial Economics* 129(2) 2018, pp. 394–414. (the conditional-on-volatility amplification is the differentiating claim)
- Gao, Han, Li, Zhou — *Intraday Momentum: The First Half-Hour Return Predicts the Last Half-Hour Return*, SSRN 2552752 (the base predictability result).
- Diva-portal thesis *Intraday Momentum and Return Predictability* (replication; notes predictability concentrates on high-volatility / high-volume days).
- QuantifiedStrategies — *Day Trading Momentum Strategy* (practitioner framing; high-volume/volatility filter).
The backtester — not the source — is the arbiter; community/practitioner pages are mechanism-only.

## Relation to prior library work
Builds directly on the **probe-rejected** [[2026-06-07-intraday-ts-momentum]] (early→late session
return corr **0.026**, mean **+0.25 pip** < cost) — the same Gao mechanism, but measured
**unconditionally**. §4.3 differentiation: the prior probe never conditioned on first-window
volatility, which is the *core* of the published result (the unconditional effect is weak even
in equities; the paper's economic content lives in the high-vol/high-volume subset). This probe
tests exactly that conditional subset, and is also the specific "conditioning mechanism that
lifts per-leg drift above ~3 pip" that the **closed seasonality / fixed-time family**
([[2026-06-17-intraday-seasonality-drift]]) named as its sole reopening condition. Also adjacent
to [[2026-06-09-late-session-drift]] (a directional intraday drift killed by thin-hour spread) —
this candidate deliberately targets **liquid** windows to avoid that failure mode.

Because the differentiation is legitimate, the probe was warranted; the verdict below resolves it.

## Strategy spec (as it *would* have been, had the probe passed)
- **Session day:** UTC. **First (signal) window:** session-opening hour (London open
  07:00–07:59, plus alternates). **Last (trade) window:** a later *liquid* hour (NY open
  13:00–13:59 / NY-AM overlap 14:00–15:59), entry at the start of that window.
- **Entry:** market, in the sign of the first-window return, **only** on days whose first-window
  realized volatility is in the top tercile (the conditioner).
- **Regime gate:** the volatility tercile *is* the gate.
- **Exit geometry (spec 08 §5.8):** would have been **stop 1.5×ATR / target 1.5R (R:R 1:1.0–1:1.5)** —
  a drift-capture trade has no structural level to anchor to, so the stop must give the
  intraday move room (1.5×ATR, wider than the incumbent's 1.2×) and the target matches the
  measured drift horizon (one trade window). NOT inheriting the incumbent's 1.2×ATR/1R.
  *Moot* — the probe rejects the entry before geometry matters.
- Params that would have become `ALLOWED_LEVERS`: first/last window bounds, vol-tercile cutoff.

## Implementation notes
**No strategy registered, no `src/` change, no trial spent.** A-priori probe only:
`scripts/probe_vol_conditioned_intraday_momentum.py` (reads the parquet directly; computes
unconditional vs vol-tercile-conditional directional drift in pips, net of the real
hour-of-day spread + 1.0-pip fixed commission/slippage). pytest unaffected (no `src/`/`tests/`
edit); no writes to `state/` or the live path.

## Backtest results
No backtest — rejected at the a-priori probe (spec 08 stage 5, "validate the entry before
spending a trial"). Probe: `python3 scripts/probe_vol_conditioned_intraday_momentum.py`,
2024-01-01 → 2026-05-29 (755 calendar days, 625 with all windows present).

Directional drift = mean( sign(first-window return) × last-window return ), in pips; net
subtracts 1.0-pip fixed + the actual entry-hour spread (~0.15p in these liquid hours). **The
hypothesis requires the HIGH-vol tercile to be the most positive.** It is the most *negative*:

| pair (first → last, entry) | uncond. corr / net | low-vol gross / net | mid-vol | **HIGH-vol gross / net** |
|---|---|---|---|---|
| 07:00–08 → 13:00–14 (e13:00) | +0.000 / −0.85p | +1.09 / −0.07p | +0.79 / −0.35p | **−0.96 / −2.12p (corr −0.028)** |
| 07:00–08 → 14:00–16 (e14:00) | +0.007 / −1.47p | +0.96 / −0.20p | −0.81 / −1.95p | **−1.10 / −2.26p** |
| 08:00–09 → 13:00–15 (e13:00) | −0.028 / −1.09p | +2.78 / +1.63p | +0.22 / −0.93p | **−2.74 / −3.91p (corr −0.120)** |
| 12:00–13 → 15:00–17 (e15:00) | −0.047 / −2.36p | −1.21 / −2.36p | −1.68 / −2.82p | **−0.75 / −1.91p** |
| 00:00–07 → 07:00–09 (e07:00) | +0.044 / −1.18p | −1.51 / −2.67p | +1.24 / +0.10p | +0.17 / −0.99p |

Plus a top-25%-|r1| magnitude conditioner (alt to the vol tercile): positive net in only **1 of
5** pairs — Asia→London **+1.75p net** (win 50.6%) — still **below the ~3-pip bar**, in the
thin-overnight→London leg the closed seasonality/late-drift family already covers, and 1
favourable cell out of 25 tested (corr/drift combinations) ≈ multiple-comparisons noise.

## Verdict
**Probe-rejected — NO trial spent (W26 budget remains 10/10).** Two independent failures: (1)
the **unconditional** drift reproduces the prior null (corr ≈ 0, net < 0 in every pair); (2) the
**conditional** test fails *in the wrong direction* — the vol gradient is **inverted** vs the
equity result: high-first-window-vol days show negative-to-zero predictive correlation
(−0.12 to −0.03) and the worst net drift, i.e. a mild *reversal*, not amplified momentum. The
only positive cells are in **low-vol** subsets (small moves; opposite of the conditioner the
hypothesis needs) and do not survive as a monotonic gradient. No proposal filed.

## Lessons
- **Market intraday momentum (Gao et al.) does NOT transfer to EURUSD M15 — and the
  conditioning *inverts* it.** The equity effect is driven by an overnight-close information
  concentration / informed-trading-at-the-open mechanism that a 24-hour FX market lacks; on
  EURUSD, a *high*-volatility opening hour is followed by mild mean-reversion in the afternoon,
  not continuation. This is the directional-persistence cousin of the breakout family's finding
  ([[2026-06-15-resting-stop-and-market-entry]]): EURUSD M15 intraday extension reverts/chops
  more than it continues, whether the trigger is a level break or a high-vol opening drift.
- **The seasonality/intraday-momentum family stays CLOSED.** Volatility-conditioning was the
  named reopening lever ("a conditioning mechanism that lifts per-leg drift above ~3 pip");
  tested directly, it does not lift the drift — it *lowers* it. Per §4.3, do not re-test
  fixed-window or first→last directional momentum (conditioned on volatility, volume, or |move|)
  without a *different* conditioner shown a-priori to flip the high-vol sign positive.
- **Process win:** an a-priori probe killed a paper-backed, superficially-strong candidate for
  **zero** trial cost and kept the rising cumulative-DSR bar (trials still 170) intact — the
  triage-quality lever the M5 review identified as the binding constraint, not the cap.

## Next steps
- Family closed on current data. The standing unlock is unchanged: a **longer-history / second-
  instrument export** (spec 08 §8 #4) — the only lever that could change the directional-
  persistence verdict or revive the floor-bound filter queue. M5 review recommends this to Cayden.
- Triaged-and-queued alongside this run (no trial): **ADXTrendStrengthGatedORB** (filter — gate
  the incumbent break on ADX>25; a trend-strength cousin of [[2026-06-14-trend-aligned-orb]] /
  MomentumGatedORB on the *same* subtractive axis → same 24-trade floor-headroom wall on the
  market-fill base; probe cut-size + sign first); **EndOfDayReversal** (Baltussen-Da-Soebhag
  last-hour reversal — blocked: no clean FX daily close, and mean-reversion is 4/4 closed).
