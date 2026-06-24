---
id: 2026-06-24-asian-range-london-breakout
name: AsianRangeLondonBreakout
family: breakout
status: probe-rejected
related: [2026-06-08-asian-sweep-fade, 2026-06-15-london-open-breakout-er, 2026-06-18-nr7-volatility-breakout, 2026-06-19-session-range-false-break-fade, 2026-06-15-resting-stop-and-market-entry]
sources: ["https://www.quantifiedstrategies.com/opening-range-breakout-strategy/", "https://github.com/je-suis-tm/quant-trading", "https://forextester.com/blog/opening-range-breakout-trading-strategies/", "https://liquidityfinder.com/news/how-to-anticipate-the-new-york-session-price-action-4492e", "https://github.com/wangzhe3224/awesome-systematic-trading/blob/master/Readme.md"]
trials_used: 0
verdict: "Probe-rejected, NO trial: the directional complement of the closed AsianSweepFade also loses — even GROSS of cost (best −0.248R, 72.4% stop-out). Wide 7h Asian box does NOT cut the false-break rate; live touch-fill takes the whipsaws like every prior breakout. Both the fade AND the break of the Asian range lose to the ~65% double-break chop tax. Breakout family stays closed (4th live-faithful confirmation)."
---

# AsianRangeLondonBreakout — trade the live-fillable break of the Asian consolidation box at the London open

## Hypothesis & market rationale
The "London breakout" / "Asian range box" is the most-cited intraday FX setup in the community
catalogs (je-suis-tm/quant-trading London Breakout; forextester; QuantifiedStrategies ORB).
Economic story: the 00:00–07:00 UTC Asian session is thin and range-bound; when London
liquidity arrives at 07:00 it repositions, and a break of the overnight range is supposed to
mark genuine directional repricing that *continues*.

Internal motivation for re-opening the (otherwise closed) breakout family on a NEW anchor:
the library's **AsianSweepFade** (2026-06-08) *faded* a sweep of this exact Asian range and
**lost** (−0.158R, PF 0.65). A losing fade is mechanically equivalent to "breaks tend to
CONTINUE, not revert." That makes the **directional break of the Asian box** the untested
complement, with a falsifiable prediction: *if the fade loses gross, the break should win
gross.* Pre-registered falsifier: the break direction has **negative gross expectancy net of
nothing** ⇒ reject (the continuation does not exist), regardless of geometry.

## Sources
- je-suis-tm/quant-trading — `London Breakout` strategy module (mechanism only; never copied).
- QuantifiedStrategies — Opening Range Breakout backtest write-up (notes the ORB edge has
  decayed and now needs filters/context).
- ForexTester / LiquidityFinder — Asian-range box + London-session repricing framing.
- wangzhe3224/awesome-systematic-trading — strategy-family catalog (London Breakout listed).
All hypothesis-only; the backtester/probe is the arbiter (spec 08 §6).

## Relation to prior library work
This is a breakout-family idea, and that family is **closed under live-faithful fills**. §4.3
requires explicit differentiation from each recorded failure mode:

- **[[2026-06-08-asian-sweep-fade]]** (tested-rejected, the fade of this same range): this is
  its directional COMPLEMENT, not a re-test. The differentiation IS the hypothesis (fade lost ⇒
  break should win). The probe falsifies it directly.
- **[[2026-06-15-london-open-breakout-er]]** (tested-rejected): used a 30-minute OPENING range
  at the London open. This uses the 7-hour Asian CONSOLIDATION box — wider and longer-formed,
  so the a-priori claim was a *lower false-break rate*. Tested explicitly below.
- **[[2026-06-18-nr7-volatility-breakout]]** (tested-rejected): a single-bar (NR7) contraction
  selecting the break. This is a multi-hour session box, not a one-bar pattern.
- **[[2026-06-15-resting-stop-and-market-entry]]**: built live-fillable from the start — a
  resting-stop OCO armed at 07:00 with both levels known in advance (intrabar TOUCH fill, no
  retcode 10015). So a positive result would NOT be a level-fill artifact.

Because the differentiation was a genuine, falsifiable complement, the probe was legitimate
(not a forbidden re-test) — but it had to clear a **gross** edge to earn a trial.

## Strategy spec (as probed)
- **Asian box:** high/low over 00:00–07:00 UTC (≥12 M15 bars required).
- **Arm at 07:00 UTC:** resting-stop OCO — `long_lvl = box_high + 1.5p`, `short_lvl = box_low − 1.5p`.
- **London window 07:00–12:00 UTC:** first intrabar touch fills at its level (resting stop);
  OCO cancels the other side. One fill per day.
- **Exit geometry (spec 08 §5.8 — justified by THIS mechanism, NOT inherited from the incumbent):**
  a range-*expansion* breakout should run, so give it room and target a measured move:
  - **stop** = `sl_atr_mult × ATR(M15,14)` from the fill, probed at **{1.0, 1.5}×** (volatility-scaled; 1.0× noise-outs, 1.5× gives the expansion room);
  - **target** = `tp_R × risk`, probed at **{1.0, 1.5, 2.0}R** (R:R ≥ 1:1 floor; ≥1.5 preferred for a continuation that should extend if the hypothesis holds);
  - rationale: a continuation breakout's reward is asymmetric *only if* it continues — exactly what the probe checks.
- Intrabar resolution: **stop-first** on an ambiguous bar (conservative).
- Would-be levers if it had survived: `box_start/end`, `london_window_end`, `buf`, `sl_atr_mult`, `tp_R`.

## Implementation notes
**No `src/` code, no registry entry, no trial.** Probe-only:
`scripts/probe_asian_range_london_breakout.py` (pure, reads the parquet read-only). No writes
to `state/`, no live-path touch, pytest unaffected (nothing under `src/` or `tests/` changed).
A build was gated on the probe clearing a gross edge; it did not, so none was written.

## Backtest results
Command: `python scripts/probe_asian_range_london_breakout.py` (probe, **0 trials**; cost 2.6p
round-trip; n=562 fills over 2.4yr ≈ 234/yr — the 200-floor is REACHABLE, so this is a SIGN
failure, not a trade-count failure).

| sl_atr | tp_R | n | win% | **gross R** | net R | PF(net) |
|---|---|---|---|---|---|---|
| 1.0 | 1.0 | 562 | 20.8 | −0.583 | −1.130 | 0.08 |
| 1.0 | 1.5 | 562 | 16.7 | −0.586 | −1.133 | 0.12 |
| 1.0 | 2.0 | 562 | 14.9 | −0.564 | −1.111 | 0.16 |
| 1.5 | 1.0 | 562 | 35.4 | −0.287 | −0.652 | 0.25 |
| 1.5 | 1.5 | 562 | 30.2 | −0.263 | −0.628 | 0.33 |
| **1.5** | **2.0** | 562 | 27.6 | **−0.248** | −0.613 | 0.37 |

Best cell (net) sl=1.5/tp=2.0: still **−0.248R gross**. ER split: low-ER n=355 net −0.718R,
high-ER n=207 net −0.432R — **even trending (high-ER) days are negative gross**. Stop-hit
(false-break) rate **72.4%**. No A/B vs HEAD and no walk-forward were run: a mechanism that is
negative *before* costs cannot beat a market-fill incumbent and does not warrant a trial.

## Verdict
**Probe-rejected. No trial spent** (trials remain 170; W26 budget 10/10). The pre-registered
falsifier fired: the Asian-box break has negative GROSS expectancy at every geometry. The
complement hypothesis is false — fading the Asian sweep loses AND breaking it loses, because
*both* directions are run over by the same intrabar whipsaw.

## Lessons
- **The "fade loses ⇒ break wins" complement does not hold on EURUSD M15.** Both the AsianSweepFade
  and its directional complement lose, because the binding cost is not direction but the **intrabar
  touch tax**: EURUSD's ~65% OR/range double-break rate means a touch fill on *either* side is
  usually the first leg of a whipsaw. Fade gets run over by continuation; break gets reversed by
  the revert. The chop eats the spread+slippage on both sides. (Same root cause flagged in
  [[2026-06-19-session-range-false-break-fade]].)
- **A wider, longer-formed range does NOT lower the false-break rate.** The 7-hour Asian box
  (vs a 30-min OR, vs a 1-bar NR7) still stops out 72% of fills. Range *width* is not the lever;
  the live-fillable directional-breakout edge simply is not there on this instrument/timeframe.
- **4th live-faithful confirmation the breakout family is closed** (market-at-close −0.024R,
  resting-touch −0.267R, NR7 −0.263R, now Asian-box −0.248R gross). Volatility expands both ways;
  a live order cannot front-run the whipsaw.
- **Process win:** a 0-trial probe settled a genuinely differentiated complement before it could
  burn DSR budget. Frequency was fine (234/yr) — the rejection is on SIGN, which is the cheaper
  thing to check first.

## Next steps
- Do **not** re-open any directional-breakout variant (session, range-width, or contraction
  filter) on current data without a *positive gross* probe first — the family is 4/4 closed.
- The real lever is unchanged from M5: a **longer-history and/or second-instrument export**
  (§8 backlog #4) to revive the dominant-but-floor-bound [[2026-06-14-trend-aligned-orb]] and
  the incumbent-filter queue. Until then, expect probe-rejections.
- Newly recorded data-blocks this run (see INDEX idea queue): **weekend gap-fill** — the M15
  feed is *continuous* across week boundaries (max boundary "gap" 0.7p over 125 weeks), so no
  weekend gap exists to trade; **currency carry / cross-sectional momentum** — needs a
  multi-currency export.
