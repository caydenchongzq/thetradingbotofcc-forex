---
id: 2026-06-15-resting-stop-and-market-entry
name: SessionBreakoutER entry-fill realism (resting-stop + market)
family: execution
status: tested-rejected
related: [2026-06-02-session-breakout-er, 2026-06-11-breakout-retest, 2026-06-13-second-entry-orb]
sources: ["docs/RESTING_STOP_FIX.md", "live retcode-10015 incident 2026-06-14"]
trials_used: 0
verdict: "SessionBreakoutER has NO live-realizable edge. Its promoted +0.391R/73%-win is a BACKTEST ARTIFACT of filling a stop AT THE LEVEL during the breakout bar — a fill the live path cannot place (stop-after-close = retcode 10015). The two live-faithful fills both fail: resting-stop touch-fill -0.267R/44%-win (admits the false breakouts close-confirmation screens out); market-at-the-confirmed-close -0.024R/59%-win (gives up the breakout bar's continuation). A tight-overshoot filter on market entry tops out at +0.008R/99 trades (fails gate + 200-floor). SELECTION (needs the close) and the LEVEL-FILL (needs to act before the close) are temporally incompatible. Incumbent CODE switched to market entry (live-safe, NOT promotable); resting-stop kept as dev strategy SessionBreakoutERResting + `entry.mode` lever. Needs a strategy rethink, not an entry patch."
---

# SessionBreakoutER entry-fill realism — the edge is an unfillable artifact

## Hypothesis & origin
Not a new strategy: a forced re-validation of the **incumbent's entry seam** after the live
`SessionBreakoutER` was rejected on every breakout with MT5 `retcode 10015` (invalid price). Root
cause: the strategy confirmed a breakout on a bar's CLOSE beyond the range edge, then placed a
**stop at the level** — but after the close the level is *behind* the market, so a buy-stop lands
below the market / a sell-stop above it, and MT5 rejects it. The backtester had been modelling that
stop as **filled at the level**, an entry the live path never actually achieves: a textbook
live ≠ backtest break at the entry seam (CLAUDE.md invariant #3). See `docs/RESTING_STOP_FIX.md`.

## What was tested (A/B on the real Parquet, 59,993 M15 bars, 2024-01 → 2026-05)
Same 224-trade selection, same SL/TP levels — **only the FILL differs**:

| entry mechanism | fill price | live-placeable? | trades | exp | win | PF | sharpe |
|---|---|---|---|---|---|---|---|
| stop at the level (the pre-fix backtest = `entry.mode=stop`) | the level, intrabar | **NO (10015)** | 224 | **+0.391R** | 73.2% | 2.39 | 4.20 |
| resting-stop OCO, intrabar touch (`SessionBreakoutERResting`) | the level, every touch | yes | — | **−0.267R** | 44% | 0.56 | — |
| market at the confirmed close (`entry.mode=market`, the new incumbent) | the close | yes | 224 | **−0.024R** | 59.4% | 0.79 | −0.91 |
| market + tight-overshoot filter (best, ≤3 pip) | the close | yes | 99 | +0.008R | 60.6% | 1.05 | — |

## Why (the structural finding)
The entire +0.391R comes from filling **at the level during the breakout bar** — capturing that
bar's continuation. That fill is not live-achievable because the two things the edge needs are
temporally incompatible with one order:
- **Selection** (only trade breakouts that *close* beyond the level — the 73%-win screen) can only
  be known at the close, by which point the market is at the close, not the level.
- **The level-fill** needs an order resting *before* the bar — a stop — which then fills on
  **every** touch, including the false breakouts that selection was meant to screen out.

Resting-stop = level-fill without selection (−0.267R). Market = selection without the level-fill
(−0.024R). You cannot have both. The retcode-10015 bug had been *masking* this by stopping the
strategy from trading at all.

## Decision & state
- Incumbent CODE is now close-confirmation + **market entry** (live-safe, no 10015) but **NOT
  profitable → not promotable**. Do not deploy expecting the promoted v4 numbers; those are
  level-fill artifacts.
- Resting-stop machinery (generic: `ArmSignal` → OCO pair in `decide` → intrabar touch-fill in the
  backtester → OCO lifecycle in `run.py`) is kept and exercised by the dev strategy
  `SessionBreakoutERResting`, reusable by any FUTURE strategy whose edge genuinely lives in a touch.
- `entry.mode` ("market"|"stop") and `entry.max_overshoot_pips` levers added for A/B.

## Generalizable lesson (for the research engine + reviewers)
**An entry's backtest fill MUST be one the live path can actually place.** A stop resting at a
level is only valid in the backtest if the live path rests it *before* the trigger; a stop placed
*after* a close beyond the level is not live-fillable (10015). Validate live-fillability of the
entry, not just the gates. Beware any edge that depends on a more-favourable fill than a live
market/stop order would receive.

## Candidate directions (each a fresh candidate; own walk-forward + lockbox)
1. Re-tune market-entry exits (wider R:R / trend runner) to fit the later fill.
2. Retest/limit entry for a pullback fill — but [[2026-06-11-breakout-retest]] was anti-selective.
3. Retire `SessionBreakoutER` as not live-viable; reallocate to other candidates.
