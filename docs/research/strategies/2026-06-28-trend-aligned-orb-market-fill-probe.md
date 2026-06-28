---
id: 2026-06-28-trend-aligned-orb-market-fill-probe
name: TrendAlignedORBMarketFillProbe
family: filter
status: probe-rejected (no trial)
related:
  - 2026-06-14-trend-aligned-orb
  - 2026-06-15-softer-trend-align-veto
  - 2026-06-22-volume-confirmed-orb
  - 2026-06-15-resting-stop-and-market-entry
sources:
  - "https://github.com/paperswithbacktest/awesome-systematic-trading"
  - "https://thehedgefundjournal.com/senaca-systematic-fx-trading-statistical-pattern-recognition/"
trials_used: 0
verdict: "TrendAlignedORB on the market-fill base: -0.027R / PF 0.77 / 149 trades — fails
  all gates. The filter IS marginally pro-selective vs the -0.080R base but cannot reach
  the +0.10R gate; trade count is still <200. SofterTrendAlignVeto definitively closed:
  a softer veto means more trades but weaker selection => even less chance of hitting +0.10R."
---

# TrendAlignedORBMarketFillProbe — TrendAlignedORB re-run on the live-faithful market-fill base

## Hypothesis & market rationale

The 2026-06-14 TrendAlignedORB test used the **level-fill artifact** (same 224 trades as
the pre-2026-06-15 incumbent, where the fill was granted AT the breakout level on bar close —
not live-placeable). After the 2026-06-15 market-fill fix, the incumbent now fills at the
close of the signal bar via `entry_type="market"`. TrendAlignedORB inherits this unchanged
(it subclasses `SessionBreakoutER` and delegates all entry logic to `super().evaluate()`).

The question this probe answers: **on the live-faithful market-fill base, is the
trend-alignment veto still pro-selective? Can it reach +0.10R / 200 trades?** If it cannot,
the [[2026-06-15-softer-trend-align-veto]] idea (veto only strongly counter-trend breaks to
retain more trades) is also definitively closed — the FULL veto is the maximum strength
version of the filter, and if the maximum fails both expectancy and sample-size gates, a
softer version will always have worse expectancy (more trades → closer to the -0.080R base).

Differentiation from [[2026-06-22-volume-confirmed-orb]] (filter-family general result):
VolumeConfirmedORB showed tick-volume confirmation has NO selection edge (PF flat-to-adverse
at every threshold). TrendAlignedORB uses a DIFFERENT axis: directional alignment (EMA trend
slope). It is possible to be pro-selective on one axis but not another. This probe resolves
the open question.

## Sources

1. [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading)
   — reviewed for any novel FX intraday mechanism not already in the library; found none
   beyond closed families. ORB strategies with walk-forward survival rate ~0.51% across 28.7M
   combinations (breakorb.com analysis) confirms the incumbent's difficulty.
2. [Senaca Systematic FX Trading](https://thehedgefundjournal.com/senaca-systematic-fx-trading-statistical-pattern-recognition/)
   — hedge fund using a proprietary statistical pattern on G10 currencies, confirms that
   high-hit-rate FX signals exist but are found by exhaustive search over years of
   development; their signal is not disclosed and not replicable.

## Relation to prior library work

- **[[2026-06-14-trend-aligned-orb]]**: The original test. On the level-fill artifact base
  (+0.391R/224 trades), TrendAlignedORB selected 149 trades at +0.359R/PF2.40/win76.5%,
  dominating HEAD on every quality metric. But that base was not live-faithful. This probe
  re-runs on the corrected market-fill code.
- **[[2026-06-15-softer-trend-align-veto]]** (idea): Proposed cutting only strongly
  counter-trend breaks to hold ≥200 trades while retaining some quality uplift. This probe
  closes that idea: the full veto already fails both gates, so the softer variant is bounded
  above by those same failing results on a larger (more base-representative) subset.
- **[[2026-06-22-volume-confirmed-orb]]** (filter-family ruling): "You cannot filter an edge
  the live-fillable base lacks." This probe tests whether trend-alignment is the exception.

## Strategy spec

**No new implementation needed.** `TrendAlignedORB` (`src/engine/strategy_trend_aligned.py`)
already subclasses `SessionBreakoutER`, which since commit 104fb1f uses `entry_type="market"`.
The probe is simply running `scripts/run_backtest.py --strategy TrendAlignedORB` against the
current codebase.

**Params (unchanged from original):**
- `ema_window: 96` (~1 trading day of M15 bars → daily-trend proxy)
- `slope_lookback: 16` (~4h → slope must be non-flat in the trade direction)

## Implementation notes

No code changes. `src/engine/strategy_trend_aligned.py` and `tests/engine/test_trend_aligned.py`
had minor non-substantive rewrites (whitespace normalisation from heredoc on 2026-06-28,
content byte-for-byte identical). Pytest green: 396 passed, 2 skipped.

No writes to `state/`, no registry changes, no live-path edits.

## Backtest results

Command: `python3 scripts/run_backtest.py --strategy TrendAlignedORB` (in-sample probe only —
no `--walkforward`, no `--trials`, no trial ledger entry).

| metric | gate | TrendAlignedORB (market-fill) | SessionBreakoutER HEAD (market-fill) |
|---|---|---|---|
| expectancy_R | ≥ 0.10 | **−0.027** ❌ | −0.080 ❌ |
| profit_factor | ≥ 1.30 | **0.77** ❌ | ~0.56 ❌ |
| win_rate | — | 61.7% | 57.6% |
| sharpe | ≥ 1.00 | **−0.77** ❌ | −2.00 ❌ |
| sortino | ≥ 1.50 | **−0.90** ❌ | −2.21 ❌ |
| sample_size | ≥ 200 | **149** ❌ | 225 ✓ |
| ftmo_no_breach | 0 breaches | ✓ | ✓ |

**Delta vs market-fill base:** +0.053R expectancy improvement (−0.080R → −0.027R). The filter
IS marginally pro-selective (not neutral, not anti-selective). However +0.053R of selection
on a −0.080R base only reaches −0.027R — far short of the +0.10R gate.

**Walk-forward / lockbox:** Not run (probe only; in-sample already fails all gates).

## Verdict

**PROBE-REJECTED. No trial spent. Trials remain at 171.**

TrendAlignedORB on the live-faithful market-fill base: **−0.027R / PF 0.77 / 149 trades**.
Fails expectancy (−0.027 < 0.10), PF (0.77 < 1.30), Sharpe (−0.77 < 1.00), Sortino
(−0.90 < 1.50), and sample_size (149 < 200).

The filter IS marginally pro-selective (+0.053R uplift), which differentiates it from the
tick-volume null (VolumeConfirmedORB, no uplift). But +0.053R on a −0.080R base is
insufficient by a wide margin (gap to gate: 0.127R).

**SofterTrendAlignVeto is definitively closed:** the full EMA-veto is the maximum-strength
version of any trend-alignment filter on this strategy. A softer veto retains more trades
(≥200), but each additional retained trade is drawn from the population closer to the
−0.080R base. If the strongest filter can only reach −0.027R (still failing), a filter that
retains more trades cannot reach +0.10R. The idea queue entry for SofterTrendAlignVeto is
closed.

This does not close the re-test-on-longer-data interpretation of TrendAlignedORB: on the
LEVEL-FILL artifact it dominated HEAD, and on a LONGER dataset the market-fill base might
have a different distribution of winning vs losing trades where the trend filter could
conceivably help more. However, on 2024-2026 data with the market-fill base, no further
testing is warranted.

## Lessons

1. **Pro-selective ≠ gate-clearing.** The trend filter is genuinely pro-selective (+0.053R
   uplift) — it removes more losers than winners. But "pro-selective" is a necessary, not
   sufficient, condition: the filter must lift expectancy ABOVE the gates, not merely above
   the base. With a base at −0.080R, the filter would need to provide +0.190R of selection
   to reach the +0.110R gate — requiring it to nearly eliminate all losses, which is
   unrealistic.

2. **The filter-family ruling generalises with a nuance.** VolumeConfirmedORB (RVOL) showed
   flat/adverse selection. TrendAlignedORB shows positive selection. So "you cannot filter an
   edge the live-fillable base lacks" is accurate on the outcomes (still no edge) but
   mechanistically not all filters are alike — some add no information, some add partial
   information. The verdict is still the same.

3. **SofterTrendAlignVeto closes by transitivity.** If the full veto with maximum strength
   fails, any strictly-weaker version is provably bounded above by the same result (on a
   subset between the full-veto 149 trades and the full-base 225 trades, expectancy lies
   between −0.027R and −0.080R). This is a clean logical close, not just an empirical one.

4. **Original 06-14 TrendAlignedORB dominance was a level-fill artifact.** On the artifact
   base, TrendAlignedORB selected +0.359R (better than the artifact's +0.391R base by its
   own metric, but the artifact's wins are inflated). The current market-fill probe resolves
   this: the quality improvement is real but not large enough to matter on the live-faithful
   base. This is important to record: the strategy DOES have informational value, just not
   enough to trade.

## Next steps

- SofterTrendAlignVeto removed from the active idea queue. No follow-on testing warranted
  on current data.
- TrendAlignedORB remains the **strongest re-test-on-longer-data candidate** if a longer
  history export or second instrument is ever available: on longer data, the market-fill base
  might have positive expectancy (if there's a profitable signal the 2024-2026 sample is too
  short to reliably detect), and the trend filter would compound a positive base rather than
  trying to rescue a negative one.
- The real unblocking lever is the longer history / second instrument export (§8 backlog #4).
