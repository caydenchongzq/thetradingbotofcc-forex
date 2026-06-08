---
id: 2026-06-08-asian-sweep-fade
name: AsianSweepFade
family: mean-reversion
status: tested-rejected
related: [2026-06-07-asian-sweep-fade, 2026-06-02-session-breakout-er, 2026-06-03-full-exit-model]
sources: ["https://fxopen.com/blog/en/what-is-ict-turtle-soup-and-how-can-you-use-it-in-trading/", "https://dailypriceaction.com/blog/liquidity-sweep-reversals/", "https://www.forexfactory.com/thread/1349219-eurusd-london-session-manipulation-amd", "https://www.fundedtradingplus.com/propiq/turtle-soup-strategy-fading-failed-breakouts/", "https://www.fluxcharts.com/articles/ict-turtle-soup-strategy-explained-how-to-identify-and-trade-it"]
trials_used: 1
verdict: "No edge: in-sample -0.158R, PF 0.65, 0/7 WF folds profitable, lockbox FAIL (-0.071R, PF 0.81); uniformly negative — structural, not regime-specific"
---

# AsianSweepFade — fade the failed Asian-range breakout at London open

## Hypothesis & market rationale
London open sweeps the Asian-session high/low to trigger resting stops, then reverses back
into the range ("liquidity sweep" / ICT turtle soup / AMD). Falsifiable as: a closed M15
bar exceeding the Asian high (+buffer) that closes back inside the range marks exhaustion;
shorting that close with a stop beyond the sweep extreme and a 1R target should be
positive-expectancy. The counterparty story: late breakout buyers + stopped-out shorts
provide the liquidity for the reversal. Pre-registered 2026-06-07 in
[[2026-06-07-asian-sweep-fade]] (spec fixed before any code or data contact).

## Sources
Practitioner-only (FXOpen, DailyPriceAction, ForexFactory AMD thread, FundedTradingPlus,
FluxCharts — see frontmatter). A repeat search on 2026-06-08 again found NO quantified
public backtest of the pattern; prior was low and stated so before testing. The harness
was the arbiter, as required.

## Relation to prior library work
Tests the strongest entry in the idea queue (queued 2026-06-07). Opposite-mechanism
complement to the incumbent [[2026-06-02-session-breakout-er]] (fade vs breakout,
08:00–11:00 vs 13:00–16:00 London — no window overlap). Exits deliberately reuse the
validated single-1R machinery from [[2026-06-03-full-exit-model]] so no live-mirror
would have been needed. Not a variant of any rejected family (first mean-reversion test).

## Strategy spec
- Asian range: London 00:00–08:00 M15 high/low; require ≥ 16 Asian bars else NoSignal.
- Window: London 08:00–11:00, one-shot per side, close-based.
- Short: bar high > asian_high + 1.5 pips AND close back inside (mirror for long);
  double-sided sweep in one bar ⇒ NoSignal (ambiguous). Market entry at the sweep close.
- Stop: max(distance to sweep extreme, 1.2×ATR14); single 1R target; no BE move.
- Regime (a-priori, recorded before testing): incumbent measurement, ER gate INVERTED
  (ER < 0.30 — exact complement of the trend gate, no new free parameter); same NORMAL
  ATR band [4, 22] pips, percentile (0.20, 0.90); same news blackout.
- Single pre-registered config (`config/dev/asian_sweep_fade.yaml`), deliberately not swept.

## Implementation notes
- `src/engine/strategy_asian_sweep.py` — `AsianSweepFade(SessionBreakoutER)`, evaluate()
  fully replaced; `_regime`/`_blackout`/`manage` reused; incumbent untouched.
- One `register("AsianSweepFade", ...)` line in `src/engine/registry.py` (additive).
- No new indicators needed. Tests: `tests/engine/test_asian_sweep.py` (11),
  `tests/backtest/test_asian_sweep_harness.py` (2). Full pytest green (exit 0).
- No writes to `state/` config or live path; live-mirror NOT needed (standard ExitPlan
  seam, broker-side SL/TP only).

## Backtest results
Command: `py scripts/run_backtest.py --config-file config/dev/asian_sweep_fade.yaml
--walkforward --trials 80` (cumulative trials incl. this candidate; ledger appended).
Data: 59,993 M15 bars 2024-01-01 → 2026-05-29.

| metric | gate | candidate | incumbent HEAD v4 (for reference) |
|---|---|---|---|
| trades | ≥ 200 | 179 | 224 |
| expectancy | ≥ +0.10R | **−0.158R** | +0.264R OOS |
| profit factor | ≥ 1.3 | **0.65** | 2.03 lockbox |
| sharpe | ≥ 1.0 | **−1.68** | passes |
| sortino | ≥ 1.5 | **−1.96** | passes |
| DSR (trials=80) | ≥ 0.95 | **0.000** | passes |
| FTMO breaches | = 0 | 0 (hard gate ok) | 0 |
| WF folds profitable | ≥ 60% | **0/7** | passes |
| severe fold (<−0.25R) | none | **2024-Q3: −0.348R** | none |
| lockbox 2025-11→2026-05 | exp ≥ 0.10R, PF ≥ 1.3 | **−0.071R, PF 0.81 — FAIL** | +0.303R, PF 2.03 |

Win rate 54.7% — the pattern *does* reverse more often than not, but with the stop at
max(structure, 1.2×ATR) the average loss exceeds the average win by enough that costs
push every fold negative. A/B vs HEAD via `compare_exits.py` was skipped as moot: the
candidate fails in-sample decisively and shares no window/mechanism with the incumbent
(noted per stage-5; no extra trial consumed).

## Verdict
REJECT — fails every soft gate in-sample; 0/7 walk-forward folds profitable; lockbox
FAIL. No proposal filed. Code + tests retained (dev-registered, unpromoted) as the
worked example of a market-entry mean-reversion strategy in the registry.

## Lessons
1. **The London-open Asian-sweep fade has no edge on EURUSD M15 2024–2026 as a
   symmetric-1R system.** Uniformly negative across all 7 folds AND the lockbox —
   structural, not regime-specific. Do not re-test pure sweep-fade entries with
   symmetric 1R exits; any variant must change the mechanism (asymmetric exit geometry,
   trend-side filter, or sweep-magnitude condition) and say why that fixes *this*
   failure mode (win rate > 50% but avg loss ≫ avg win after costs).
2. The 54.7% win rate with PF 0.65 is the signature of a stop that is structurally wider
   than the target (max(structure, 1.2×ATR) vs 1R of that same distance) plus market-entry
   spread costs. Practitioner sweep lore survives on asymmetric R:R claims (1:3+) that
   shift the burden to a low win rate — the symmetric version is provably negative here.
3. Market-entry (`entry_type="market"`) strategies work end-to-end in the harness — first
   such candidate; the seam needed no changes.
4. Inverted-ER gating (ER < 0.30) plus the NORMAL ATR band yields ~179 trades / 29 months
   in the 3h window — just under the 200 gate. Subtractive gates on a 3h window sit at the
   sample-size edge (echoes [[2026-06-07-pre-session-compression-filter]] headroom lesson).

## Next steps
- Queued instead: [[2026-06-08-london-fix-reversal]] (paper-backed WM/R 4pm-fix reversal).
- If the fade family is ever revisited: test the asymmetric-R version (tight structural
  stop above the sweep wick only, ≥ 2R target) — but note [[2026-06-07-tp-2r-sweep]]
  rejected pure ≥2R targets for the *incumbent*; a fade variant must argue why its R
  distribution differs, else it is gate-blocked by both rejections.
