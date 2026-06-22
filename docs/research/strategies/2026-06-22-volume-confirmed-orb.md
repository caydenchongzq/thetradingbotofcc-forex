---
id: 2026-06-22-volume-confirmed-orb
name: VolumeConfirmedORB
family: filter
status: probe-rejected
related: [2026-06-14-trend-aligned-orb, 2026-06-15-resting-stop-and-market-entry, 2026-06-13-second-entry-orb, 2026-06-11-breakout-retest]
sources:
  - "https://medium.com/@FMZQuant/opening-range-breakout-strategy-with-volume-confirmation-and-exponential-moving-averages-9352aa581357"
  - "https://www.mql5.com/en/articles/18486"
  - "https://www.tradingsim.com/blog/relative-volume-rvol"
  - "https://www.quantifiedstrategies.com/opening-range-breakout-strategy/"
  - "https://github.com/paperswithbacktest/awesome-systematic-trading"
trials_used: 0
verdict: "PROBE-REJECTED (no trial): a break-bar tick-volume (RVOL) veto on the market-fill incumbent gives NO selection edge — every lookback x threshold leaves the surviving subset negative-expectancy (PF <= 0.92), and the only thresholds that hold >=200 trades are the permissive ones (thr<=1.2) where exp is still -0.03 to -0.04R. Tick volume does not separate the incumbent's winners from losers; you cannot filter an edge that the live-fillable base does not have."
---

# VolumeConfirmedORB — gate the incumbent break on a tick-volume (RVOL) spike

## Hypothesis & market rationale
Practitioner ORB literature is near-unanimous that a *genuine* breakout is accompanied by a
volume expansion, while low-volume pokes beyond the range are disproportionately the false
breaks that snap back inside. If that holds on EURUSD M15, the incumbent's losers should be
concentrated in its low-relative-volume breaks, and vetoing them (taking only breaks whose bar
volume exceeds a multiple of its recent average — "relative volume", RVOL) should raise win
rate / PF / risk-adjusted return while staying above the 200-trade floor.

Falsifiable form: **there exists an RVOL lookback L and threshold k such that the subset of the
incumbent's trades whose break-bar RVOL(L) >= k has (a) n >= 200 trades AND (b) expectancy
>= +0.10R with PF >= 1.3.** If no (L, k) satisfies both, the filter has no edge and the idea
dies at the probe (no trial), per spec 08 §4.3 and the INDEX caveat on the incumbent-filter
queue.

## Sources
- FMZQuant, "Opening Range Breakout Strategy with Volume Confirmation and Exponential Moving
  Averages" (Medium) — a concrete community ORB-with-volume implementation; mechanism source
  (re-implemented pure, code never copied — spec 08 §5).
- MQL5 Articles #18486, "Opening Range Breakout Tool" — ORB EA that confirms breaks with a
  volume/expansion check on EURUSD M15.
- TradingSim, "Relative Volume (RVOL): Trading Indicator Guide" — RVOL definition and the
  1.5–2.0 "sweet spot" claim (equities; 58.8% 3-day follow-through in their 1,872-event test).
- QuantifiedStrategies, "Opening Range Breakout Strategy: Backtest" — ORB filter framing.
- paperswithbacktest/awesome-systematic-trading — catalog entry point (SOURCES.md).
- Corroborating skeptic note (web search 2026-06-22): in FX, volume confirmation is "not a
  standalone solution"; fakeouts cluster in low-liquidity windows and **tick** volume is an
  unreliable proxy for real volume given the decentralized 24/5 market. The backtester — not
  any source — is the arbiter; here the probe settled it.

## Relation to prior library work
This is the queued idea **2026-06-14-volume-confirmed-orb**, finally probed. It is a STRICTLY
SUBTRACTIVE directional/quality FILTER on the incumbent break, the same shape as
[[2026-06-14-trend-aligned-orb]] (which dominated HEAD on quality but FAILED the 200-trade
sample_size gate, cutting 224 -> 149). Differentiation required by §4.3:
  * **Different axis** from TrendAlignedORB: a *volume* spike on the break bar, not a
    higher-timeframe trend alignment. Its recorded failure mode (sample_size) is a *risk* here,
    not a foregone conclusion — so it earns a probe, but the probe must show the cut keeps
    >=200 AND lifts the sign, else it dies for free.
  * **Re-based on the MARKET-fill incumbent** (base n=224, raw exp −0.024R, harness
    expectancy_r −0.080R / PF 0.56), NOT the +0.391R level-fill artifact, per
    [[2026-06-15-resting-stop-and-market-entry]] and the INDEX caveat: filtering an artifact
    only yields a higher-quality artifact subset, never a live edge.
  * It is **not** the rejected [[2026-06-11-breakout-retest]] (a break->retest->resume *timing*
    subset) nor the passed-but-dominated [[2026-06-13-second-entry-orb]] (an *additive* re-break
    entry): this is a one-variable veto holding entry/exit/manage byte-for-byte the incumbent's.

## Strategy spec
Planned (had the probe cleared): subclass `SessionBreakoutER`; in `evaluate`, after the
incumbent returns a `Signal`, compute `rvol = volume[break_bar] / mean(volume[prev L bars])`
and veto (return `NoSignal("low_relative_volume")`) when `rvol < k`. Strictly subtractive — it
can only turn a `Signal` into `NoSignal`, never the reverse (fail safe preserved). Levers, had
it been built: `volume_filter.rvol_lookback` (L), `volume_filter.rvol_min` (k).

**Exit geometry (spec 08 §5.8):** UNCHANGED from the incumbent — stop `max(structural box,
1.2xATR)`, single 1.0R target, 100% out (R:R 1:1). Rationale: to measure a *filter* you must
hold geometry fixed, and the surviving trades ARE the incumbent's own breaks (the library has
twice reconfirmed EURUSD M15 overlap rewards high-win-rate ~1R structures —
[[2026-06-07-tp-2r-sweep]]). Changing R would confound the filter with an exit change. No new
manage semantic ⇒ no live-mirror needed.

## Implementation notes
**No strategy/indicator/test code was added** — the idea was killed at the a-priori probe
(spec 08 §3 stage 3 / §8: "most ideas die at triage for free"), exactly as
[[2026-06-17-intraday-seasonality-drift]] and [[2026-06-19-session-range-false-break-fade]]
were. The probe is reproducible: `scripts/probe_volume_confirmed_orb.py`. It runs the
*real* market-fill HEAD incumbent through the harness (so the break semantics are exact),
maps each `SimTrade.entry_ts` to its break bar (market entry on the confirmed close), computes
break-bar RVOL at L ∈ {20, 48, 96}, and tabulates surviving trade count + expectancy + PF at
k ∈ {1.0, 1.1, 1.2, 1.3, 1.5}. No writes to `state/`, no live-path edits, no ConfigStore call,
no trial-ledger append. `python -m pytest -q` green (393 passed, 2 skipped) — unchanged, since
only a standalone script + docs were added.

## Backtest results
Probe command: `py scripts/probe_volume_confirmed_orb.py` (no `--walkforward`, no trial). The
incumbent base is the market-fill HEAD v4 (live-faithful). "exp" below is the raw per-trade
mean R of the surviving subset; the harness's equity-weighted `expectancy_r` for the full base
is −0.080R (PF 0.56) — both negative, the point of the probe.

Base (market-fill incumbent): **n=224, exp −0.024R, win 59.4%, PF 0.92.**
Floor headroom: only **24 trades** above the 200 hard sample_size gate.

| lookback | thr | n (need ≥200) | exp (need ≥+0.10R) | win | PF (need ≥1.3) |
|---|---|---|---|---|---|
| 20 | 1.0 | 205 | −0.071 | 56.6% | 0.78 |
| 20 | 1.2 | 179 | −0.071 | 56.4% | 0.78 |
| 20 | 1.5 | 125 | −0.030 | 57.6% | 0.88 |
| 48 | 1.0 | 220 | −0.030 | 59.1% | 0.90 |
| 48 | 1.2 | 203 | −0.043 | 58.1% | 0.86 |
| 48 | 1.5 | 172 | −0.078 | 55.8% | 0.76 |
| 96 | 1.0 | 221 | −0.031 | 58.8% | 0.90 |
| 96 | 1.2 | 209 | −0.043 | 57.9% | 0.86 |
| 96 | 1.3 | 201 | −0.071 | 56.2% | 0.79 |
| 96 | 1.5 | 174 | −0.059 | 56.9% | 0.81 |

Two facts kill it before a walk-forward is warranted:
1. **No sign flip anywhere.** Every (L, k) cell is negative-expectancy with PF ≤ 0.92 (≤ the
   base). RVOL does not isolate a positive subset — the gap to the +0.10R / PF 1.3 gate is
   never even approached.
2. **The directional gradient is flat-to-adverse.** Raising the RVOL threshold does *not*
   monotonically raise expectancy; at L=20 the higher-volume breaks are if anything slightly
   *worse* (exp −0.071R at thr 1.0 vs the −0.024R base), and the only cells where exp drifts
   toward 0 are the high thresholds that have already fallen far below the 200-trade floor
   (e.g. L=20/k=1.5 → n=125). The “volume sweet spot” improvement seen in equities does not
   reproduce on EURUSD M15 tick volume.

## A/B vs incumbent HEAD
Not run as a full backtest (the probe pre-empts it). The implicit A/B is in the table: every
candidate subset is dominated by — or indistinguishable from — the market-fill HEAD base on
expectancy and PF, while losing trades toward (or through) the floor. There is no version of
this filter that both clears sample_size and beats HEAD; spending a walk-forward trial would
only burn DSR budget to reconfirm a negative already visible in-sample (cf. the do-not-promote
logic of [[2026-06-13-second-entry-orb]], where a *pass* still wasn't enough).

## Verdict
**PROBE-REJECTED — no trial spent** (W26 trial budget remains 10/10; cumulative trials stay
170). No proposal filed. No code added to `src/` or `tests/`. The filter has no selection edge
on tick volume, and even if it did the 24-trade floor headroom on the market-fill base leaves
no room for a subtractive filter to operate.

## Lessons
- **You cannot filter an edge the base does not have.** The market-fill incumbent break is
  net-negative (PF 0.56 on the harness metric); a subtractive filter can at best concentrate a
  smaller negative-expectancy subset. This is the general consequence of
  [[2026-06-15-resting-stop-and-market-entry]] for the *entire* incumbent-FILTER queue
  (VolumeConfirmedORB, MomentumGatedORB, SofterTrendAlignVeto, QualityGatedSecondEntry): each
  was conceived as quality-additive on the +0.391R *level-fill* number, but on the live-faithful
  base there is essentially nothing positive to keep. TrendAlignedORB looked like the exception
  only because it was measured against the artifact; re-based here, the family's ceiling is a
  smaller negative.
- **Tick volume ≠ real volume on FX.** The equities RVOL “sweet spot” (1.5–2.0) did not transfer;
  the highest-RVOL EURUSD M15 breaks were not the best ones. Decentralized 24/5 tick counts are
  a weak proxy, as the literature warns — consistent with this null result. Do not re-test a
  plain tick-volume confirmation on any incumbent break without a mechanism that first restores
  a positive live-fillable base.
- **The 200-trade floor is now the binding wall for ALL subtractive work on current history.**
  The market-fill base has only 24 trades of headroom; any veto that bites at all risks the
  floor. This re-confirms the M5 review and the standing conclusion: the real unlock is a
  **longer-history / second-instrument export** (spec 08 §8 backlog #4), not another filter.
- **Process:** the probe cost zero trials and settled a queued idea definitively — the §4.3 +
  §8 triage discipline working as designed (3rd probe-rejection in the library after 06-17,
  06-19). Reproducible probe scripts are the right artifact for filter ideas: they read the
  real harness trades and answer cut-size + sign in one pass.

## Next steps
- Mark the queue idea **2026-06-14-volume-confirmed-orb** as probe-rejected (done in INDEX).
- **Filter family is effectively closed on current data** until the base entry has a genuine
  live edge OR the data widens. Do not spend trials on the remaining incumbent-filter queue
  (MomentumGatedORB, SofterTrendAlignVeto, QualityGatedSecondEntry) on this history — each
  inherits the same "filtering a negative base + 24-trade floor headroom" wall; re-base each on
  the market-fill incumbent and probe cut-size BEFORE any trial, and expect the same null.
- Newly queued from today's research (not tested): a **regime-conditioned statistical
  mean-reversion** frame (SSRN 6087107) and a **Markov-switching GARCH volatility-regime** gate
  (arXiv 2606.06190) — both are subtractive/conditioning overlays that hit the same floor wall
  and, for the MR one, the closed 4/4 mean-reversion family; queued with mandatory probe-first
  caveats (see INDEX). The multi-timeframe **M5-trigger ORB** remains blocked-on-data.
- Highest-leverage action for Cayden: prioritise the longer-history / second-instrument export.
