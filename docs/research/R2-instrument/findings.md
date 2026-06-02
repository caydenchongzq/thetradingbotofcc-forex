# R2 — Instrument Selection: Findings

**Track:** R2 — Instrument selection (which single instrument to start with, and why)
**Scope:** Pick instrument #1 for the FTMO 2-Step bot from XAUUSD (gold) vs the majors EURUSD, GBPUSD, USDJPY, GBPJPY. Resolve whether gold's volatility is too aggressive for the 5% daily envelope, and whether the "GBP/USD/JPY pairs are mostly profitable" claim is real edge or folklore.
**Research date:** 2026-06-02. Live volatility numbers were pre-computed from 3 months of daily bars to 2026-06-02 (Yahoo Finance) and are used as-is below. Spread/leverage/session layers are from web research, cited inline. Re-verify FTMO's [Symbols page](https://ftmo.com/en/symbols/) (last modified 2026-02-24) before production; FTMO changes specs silently.

---

## 1. Summary

**Recommendation: start with EURUSD.** It has the tightest spread in absolute and relative terms (~0.4 pip raw on FTMO, roughly 0.6–0.7% of its average daily range), the deepest liquidity, the cleanest London/NY-overlap session structure, the smallest weekend gaps, and the highest FX leverage tier (1:100), and it is the most forgiving instrument to debug a first pipeline against. GBPUSD is a close, fully-acceptable second if you want a touch more daily range to work with.

**On Cayden's gold preference:** gold is *tradeable* under FTMO — the math works if you size tiny — but it is the *least forgiving* instrument to build a first system on, for reasons that compound: its daily range is ~3× the majors as a % of price, its spread is ~10–30× wider per unit of range, its weekend gaps are real and large, and its fat right tail (single-print spikes like the 2026-04-30 day) can jump a hard stop. Gold belongs on the roadmap as instrument #2 or #3, *after* the slippage model, news blackout, and kill-switch have been proven on a forgiving major. Forcing the first build onto the hardest instrument maximizes the chance that a pipeline bug and a volatility spike coincide on the one account you are trying to pass.

**On the GBP-pairs folklore:** the claim that "GBP/USD/JPY pairs are mostly profitable" is **not a real, robust edge** — it is survivorship-flavored folklore. There is no credible efficiency-ratio or autocorrelation evidence that GBP crosses are *structurally* more profitable than EURUSD; what is real is that they are more *volatile* (more range to capture if you are right, more damage if you are wrong). For a beginner-safe first build that distinction argues *against*, not for, leading with GBPJPY.

---

## 2. The comparison table

Volatility columns (ADR, ADR%, median DR, max DR) are the pre-computed live numbers (3mo daily bars → 2026-06-02). Spread, spread/ADR, session, and leverage columns are from web research (sourced in §4–§6). "Pips" for the JPY pairs = 0.01; for the USD majors = 0.0001; for gold, "pts" = $0.01 per oz is the conventional pip but the table uses whole-dollar points ($1 = 100 conventional gold pips) to keep the magnitudes legible.

| Instrument | Price | ADR | ADR % | Median DR | Max DR (sample) | FTMO raw spread | Spread ÷ ADR | $ / lot per 1-unit move | One ADR ≈ $/lot | FTMO leverage | Beginner suitability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **EURUSD** | ~1.164 | 62 pips | 0.53% | 56 pips | 175 pips | ~0.4 pip | **~0.6%** | $10 / pip | ~$620 | **1:100** | **Best** |
| **GBPUSD** | ~1.346 | 80 pips | 0.60% | 75 pips | 216 pips | ~0.5 pip | ~0.6% | $10 / pip | ~$800 | 1:100 | Very good |
| **USDJPY** | ~159.6 | 82 pips | 0.51% | 65 pips | 515 pips* | ~0.4 pip | ~0.5% | ~$6.3 / pip | ~$520 | 1:100 | Good |
| **GBPJPY** | ~214.9 | 111 pips | 0.52% | 88 pips | 606 pips | ~1.2–1.8 pip | ~1.3% | ~$6.3 / pip | ~$700 | 1:100 | Poor (advanced) |
| **XAUUSD** | ~4520 | 81.9 pts ($81.9) | **1.81%** | 68.4 pts | 379.6 pts* | ~$0.15–0.40 (15–40 cents) | **~2–5%** | $100 / $1 move | ~$8,200 | **1:50** (capped) | Worst-for-first |

\* The USDJPY 515-pip and gold 379.6-pt maxes include a likely single bad-print spike on **2026-04-30**; treat the maxes as indicative of *tail risk*, not a typical day. The XAUUSD sample also sits in an unusually volatile regime — a sharp sell-off from ~$5,400 to ~$4,400 over March 2026 — so its 1.81% ADR% is at the **high end** of gold's historical norm (more typical is ~1.0–1.4%). Even normalized, gold's ADR% is still ~2× the majors.

**The robust headline (do not lose this in the noise):** gold's daily range as a % of price is **~3× the FX majors**, and its absolute dollar swing per standard lot is an **order of magnitude larger** — 1.0 lot of gold = 100 oz = $100 per $1 move, so one ADR ≈ **$8,200 of P&L swing per lot** versus ~$520–800 per lot for the majors. That single fact drives almost everything that follows about sizing and forgiveness.

---

## 3. The FTMO 5%-envelope sizing math (why "gold is tradeable" is true but not the whole story)

On a $100k 2-Step account the daily loss budget is 5% = $5,000, and the Risk Governor (see R4) targets ~0.35% equity (~$350) per trade. The question "is gold too aggressive?" is really "can you size it small enough?" — and the answer is yes:

- **Gold:** $350 risk ÷ ~$8,200 ADR-per-lot ⇒ ~**0.04 lot** if your stop is one ADR wide. With a tighter intraday stop (say a third of ADR, ~$27/oz), you'd size ~0.13 lot. Either way the platform supports it — minimum lot is 0.01 — so gold *fits* the envelope.
- **EURUSD:** $350 risk on a ~20-pip intraday stop ⇒ $350 ÷ (20 × $10) = **~1.75 lots**. You are operating in a fat, comfortable part of the lot-size resolution where a 0.01-lot rounding error is negligible.

So the envelope is not the disqualifier for gold. The disqualifiers are the *second-order* properties that the envelope math hides: at 0.04 lot you are operating near the minimum-lot floor (rounding granularity matters more), your stop sits inside a price that routinely *spikes* $5–15 in seconds, your spread eats a far larger fraction of every move, and a weekend gap or a single-print tail can blow through the stop and realize *more* than the $350 you budgeted. None of those show up in the "can I size it?" calculation — they show up as **slippage and gap variance**, which is exactly the thing a first pipeline has not yet proven it handles.

---

## 4. Spreads & commission (the intraday cost drag)

Intraday, the cost that actually matters is **spread as a fraction of the range you're trying to capture**, because you pay it on every round trip regardless of whether the trade works.

- **FX majors on FTMO** run roughly **EURUSD ~0.4 pip, GBPUSD ~0.5 pip, USDJPY ~0.4 pip** raw, plus FTMO's commission. ([allproptradingfirms.com](https://allproptradingfirms.com/understanding-spreads-and-commissions-at-ftmo/), [FTMO Symbols](https://ftmo.com/en/symbols/)) FTMO charges **~$3 per side / ~$6 round-trip per standard lot on spot FX** (often quoted as "~$5 per $100k notional"). ([allproptradingfirms.com](https://allproptradingfirms.com/understanding-spreads-and-commissions-at-ftmo/), [thepayoutreport.com](https://thepayoutreport.com/ftmo-us-account-sizes-costs-how-to-choose-the-right-challenge/)) Against a 56–80 pip median range, a ~0.4–0.5 pip spread is **~0.6% of ADR** — a rounding error.
- **GBPJPY** is materially wider — typically **~1.2–1.8 pip** even on raw/ECN accounts, and it widens hard in the Asian session and at rollover. ([afterprime.com](https://afterprime.com/forex/gbpjpy), [daytrading.com](https://www.daytrading.com/gbpjpy)) At ~1.3% of its ADR that is roughly **2× the cost drag of EURUSD** per round trip.
- **Gold (XAUUSD)** is the widest by far. Raw/ECN gold spreads sit around **~15–40 cents** ($0.15–$0.40) per oz in good conditions and blow out to **$0.50–$1.00+** during news, rollover, and the early-Asia thin window. ([Exness raw ~0.3–0.7 "pip" = 3–7 cents in ideal conditions; industry ECN average ~2.5–3.5 "pips" = 25–35 cents](https://issuu.com/exness_blog/docs/exness.docx/s/67263034)) Even at the *good* end, $0.15–0.40 against a typical ~$25–80 intraday move you'd target is **~0.5–2% of range, blowing out to ~5%** in stress — an order of magnitude worse drag than EURUSD, and the worst-case is exactly when your stop is most likely to be tested. FTMO's metals commission is **~0.0025% per side of notional (~$5 round-trip per $100k notional)**, but for gold the spread, not the commission, is the dominant cost. ([thepayoutreport.com](https://thepayoutreport.com/ftmo-us-account-sizes-costs-how-to-choose-the-right-challenge/))

**Takeaway:** ranked by intraday cost-drag, best→worst is **EURUSD ≈ USDJPY < GBPUSD < GBPJPY ≪ XAUUSD.** For a bot whose edge per trade is thin, spread/ADR is one of the most decision-relevant numbers in this whole document, and it points squarely at the USD majors.

---

## 5. Session behaviour (when each is tradeable, when spreads blow out)

- **EURUSD / GBPUSD** are most liquid and tightest during the **London session (~08:00–17:00 GMT)** and especially the **London/NY overlap (~13:00–17:00 GMT / 8am–12pm ET)**, which carries the highest volume and tightest spreads of the day. ([maventrading.com](https://maventrading.com/blog/forex-liquidity-and-trading-conditions), [forex.com](https://www.forex.com/en-us/help-and-support/rollover/)) Outside those windows, and especially in the Asian session, GBP-leg liquidity thins and spreads widen.
- **USDJPY** adds the **Tokyo session** as a liquid window, so it has tradeable liquidity across more of the 24h clock, but its cleanest moves still come in London/NY.
- **GBPJPY** is a **cross**, so it inherits the *worst* of both legs' thin windows: its spread blows out badly in the **Asian session** (neither London nor a deep yen-cross book is fully present) and at the **5pm-ET rollover**, where even majors can gap to 20+ pips and illiquid crosses far more. ([forexfactory.com](https://www.forexfactory.com/thread/604325-how-do-you-deal-with-widening-spreads-at), [forexpeacearmy.com](https://www.forexpeacearmy.com/community/threads/spreads-go-crazy-at-5-pm-est.10799/)) Its best behaviour is the London open/overlap only.
- **Gold (XAUUSD)** trades ~23h/day (Sun 22:00 UTC → Fri 22:00 UTC) but its liquidity is concentrated in **London and NY**; the early-Asia and rollover windows are thin and spreads widen there. ([startrader.com](https://www.startrader.com/knowledge-intermediate/xauusd-trading-hours-open-close-best-times-to-trade-gold/), [tmgm.com](https://www.tmgm.com/en/academy/trading-academy/gold-trading-hours))

**Takeaway:** all candidates share the same "trade the London/NY overlap, avoid rollover and thin Asia" rule, which the bot should encode as a per-instrument trading-hours window. The majors give you the *widest clean window*; GBPJPY gives the *narrowest*.

---

## 6. Trendiness vs mean-reversion, and the GBP folklore

**The folklore claim — "GBP/USD/JPY pairs are mostly profitable" — does not survive scrutiny as a structural edge.** The web literature on currency-pair character (correlation, autocorrelation, detrended-fluctuation studies) finds that FX majors are close to a random walk at the daily scale; the more bounded/stationary a series is the more mean-reverting it tends to be, but there is **no credible source establishing that GBP crosses have a persistent, exploitable directional edge** over EURUSD. ([arxiv.org/pdf/1011.2385](https://arxiv.org/pdf/1011.2385), [fx2funding.com](https://fx2funding.com/blog/what-you-should-know-about-currency-correlation/)) What the GBP folklore actually conflates is **volatility with profitability**: GBPUSD and especially GBPJPY have *more range*, so a correct call pays more — but a wrong call loses more by exactly the same mechanism, and the wider spread and slippage tax every trade. That is leverage on your edge, not edge itself.

What *is* well-documented and honest:

- **GBPJPY ("the Beast"/"Geppy")** routinely moves **200–400 pips/day** and can swing **300–500 pips on BoJ/BoE surprises**, because it compounds a volatile non-safe-haven (GBP) against a volatile safe-haven (JPY) — when both legs move the same way, the cross's move is the *sum*. ([forexforstarters.com](https://forexforstarters.com/markets/minors/gbp-jpy/), [tmtradesfx.com](https://www.tmtradesfx.com/gbpjpy)) Every guide that praises its opportunity also explicitly warns it is **"not a pair for beginners"** because of extreme volatility, wide spreads, and slippage. ([forexforstarters.com](https://forexforstarters.com/markets/minors/gbp-jpy/), [saxo](https://www.home.saxo/learn/guides/forex/how-to-trade-the-gbpjpy-forex-pair))
- **EURUSD** is the most efficient/liquid pair, which cuts both ways: it is the *hardest to find a fat directional edge in* but the *easiest to execute cleanly and cheaply*. For a first build whose goal is to *prove the pipeline*, "easy to execute cleanly" is the property you want.
- **Gold** is structurally **trendy/momentum-prone** with sharp risk-on/risk-off regime shifts (the March 2026 ~$5,400→$4,400 sell-off in our sample is a live example) and a fat right tail — attractive for a mature momentum strategy, dangerous for an unproven one.

**Honest bottom line on edge:** none of these instruments hands you a free directional edge; the bot's edge has to come from the signal layer (R1), not the instrument. Given that, you should choose the instrument that makes a thin edge *easiest to realize after costs* — which again is EURUSD.

---

## 7. FTMO-specific quirks

- **Leverage tiers.** FTMO offers **1:100** on Standard FX. **Gold (XAU pairs) is capped lower at 1:50** (Standard) / 1:15 (Swing) — note this was actually an *improvement* from a lower prior cap, effective **Feb 1, 2026**. ([thepayoutreport.com Feb-2026 update](https://thepayoutreport.com/ftmo-february-2026-updates/), [FTMO Symbols](https://ftmo.com/en/symbols/)) The lower gold leverage rarely binds when you're sizing 0.04 lot, but it confirms FTMO itself treats gold as a higher-risk class.
- **Commission.** ~$3/side (~$6 round-trip) per standard lot on spot FX; ~0.0025%/side of notional (~$5 round-trip per $100k) on metals/indices. ([allproptradingfirms.com](https://allproptradingfirms.com/understanding-spreads-and-commissions-at-ftmo/), [thepayoutreport.com](https://thepayoutreport.com/ftmo-us-account-sizes-costs-how-to-choose-the-right-challenge/)) Commissions hit the equity-based daily-loss test, so the Risk Governor must include them in cost-to-stop.
- **Weekend gap risk.** Holding over the weekend is *allowed* in the Evaluation, but FTMO explicitly warns that **negative weekend gaps occur statistically more often** and encourages flattening. ([ftmo.com/holding-trades-over-the-weekend](https://ftmo.com/en/blog/holding-trades-over-the-weekend/)) **Gold gaps are notably larger** than major-FX gaps — geopolitics and risk events priced over the weekend hit gold hard at the Sunday reopen. ([startrader.com](https://www.startrader.com/knowledge-intermediate/xauusd-trading-hours-open-close-best-times-to-trade-gold/)) Because the daily-loss test is equity-based, a weekend gap on an open gold position can breach the limit *before you can react*. The bot should default to **flat-by-Friday-close** for any instrument, and this matters most for gold.
- **Swap / overnight financing** applies to positions held over the rollover and varies by symbol; for an intraday bot (timeframe floor 5m/15m) this is largely avoided by not holding overnight, but gold's swap and the triple-swap day should be configured if any carry is possible.
- **Trading-hours / maintenance quirks** (President's Day early closes, Lunar New Year, scheduled platform maintenance) thin liquidity and widen spreads on specific dates; the news/calendar blackout in R4 should suppress trading through these. ([thepayoutreport.com](https://thepayoutreport.com/ftmo-february-2026-updates/))

---

## 8. The pick and rationale

**Instrument #1: EURUSD.** It wins on every axis that matters for a *first* build:

1. **Lowest cost drag** — ~0.4 pip raw, ~0.6% of ADR, the cheapest round trip of any candidate, so a thin signal-layer edge survives execution.
2. **Most forgiving sizing** — at ~1.75 lots on a 20-pip stop you're far from the lot-resolution floor, unlike gold's ~0.04 lot.
3. **Deepest liquidity / smallest gaps / least slippage** — the property that most directly de-risks an *unproven* pipeline against the variance that the sizing math doesn't capture.
4. **Cleanest, well-understood session structure** (London/NY overlap) and the **top FX leverage tier (1:100)**.
5. **No structural edge given up** — since none of these instruments hands you free edge, choosing the most executable one costs you nothing real.

**GBPUSD is an acceptable substitute** if you want ~30% more daily range to work with for a breakout-style signal; its spread/ADR is essentially the same as EURUSD's. Treat EURUSD and GBPUSD as interchangeable "tier-1 first instruments" and let the R1 signal work decide between them.

**On gold honestly:** Cayden's preference is reasonable for the *eventual* system — gold trends, moves, and is genuinely tradeable under FTMO if sized tiny (~0.04 lot). But it is the *least forgiving* place to discover that your slippage buffer is too small, your news blackout has a gap, or your kill-switch latency is too slow. Every weakness in a v1 pipeline is amplified by gold's ~3× ADR%, ~10–30× spread/range, and large weekend gaps. The right sequencing is: **prove the pipeline on EURUSD, then add gold as instrument #2 or #3 once the slippage model, gap handling, and kill-switch are validated on live-feed paper trading.**

**GBPJPY** should be the *last* instrument added, if ever — it concentrates wide spreads, brutal slippage, and 300–500 pip event moves, and the "GBP pairs are profitable" lore gives no real reason to rush it.

---

## 9. What to revisit when adding instrument #2

The architecture is instrument-agnostic (per-instrument config), so adding gold (or GBPUSD) is a config change plus a validation pass, not a rewrite. What changes per-instrument:

- **`pip_value_per_lot` / contract spec** — gold is $100/lot per $1 move vs $10/pip for USD majors; the position-sizer keys off this.
- **`spread_buffer` / `slippage_spread_buffer`** — must be raised substantially for gold (wider, spikier spread). The R4 default of 0.20 is calibrated to majors; gold needs its own, larger value, and ideally a *dynamic* spread check that refuses to trade when live spread exceeds a ceiling.
- **`leverage` / margin** — gold is 1:50 on FTMO vs 1:100 FX; the margin/exposure check must read the per-instrument cap.
- **`trading_hours` window** — narrow gold's tradeable window to London/NY and explicitly exclude early-Asia and rollover; same discipline for GBPJPY but tighter.
- **`max_stop_distance` / min-lot interaction** — at gold's ~0.04 lot, verify the sizer's rounding doesn't push realized risk meaningfully above target; add a floor-lot sanity check.
- **`weekend_flatten` / gap policy** — keep flat-by-Friday as default; if ever relaxed, gold needs a tighter overnight-exposure cap than FX because of gap size.
- **Re-run the full backtest + live-paper validation (R6)** per instrument before it touches the funded account — never assume a major-calibrated config transfers to gold.

---

## Sources

- FTMO — [Symbols / Symbol Specifications](https://ftmo.com/en/symbols/) (modified 2026-02-24)
- FTMO — [Holding trades over the weekend](https://ftmo.com/en/blog/holding-trades-over-the-weekend/)
- The Payout Report — [FTMO February 2026 Updates (Gold leverage 1:50 / 1:15, effective Feb 1 2026)](https://thepayoutreport.com/ftmo-february-2026-updates/)
- The Payout Report — [FTMO US Account Sizes, Costs & How to Choose (commissions)](https://thepayoutreport.com/ftmo-us-account-sizes-costs-how-to-choose-the-right-challenge/)
- AllPropTradingFirms — [Understanding Spreads and Commissions at FTMO](https://allproptradingfirms.com/understanding-spreads-and-commissions-at-ftmo/)
- Afterprime — [GBPJPY spreads & trading costs](https://afterprime.com/forex/gbpjpy)
- DayTrading.com — [GBP/JPY brokers and strategies](https://www.daytrading.com/gbpjpy)
- Exness blog (via Issuu) — [XAUUSD spread review (raw/ECN gold spread ranges)](https://issuu.com/exness_blog/docs/exness.docx/s/67263034)
- Maven Trading — [How Forex Liquidity and Trading Conditions Impact Your Trades](https://maventrading.com/blog/forex-liquidity-and-trading-conditions)
- FOREX.com — [Trading Rollover FAQs](https://www.forex.com/en-us/help-and-support/rollover/)
- Forex Factory — [How do you deal with widening spreads at the rollover?](https://www.forexfactory.com/thread/604325-how-do-you-deal-with-widening-spreads-at)
- Forex Peace Army — [Spreads go crazy at 5pm EST](https://www.forexpeacearmy.com/community/threads/spreads-go-crazy-at-5-pm-est.10799/)
- StarTrader — [XAUUSD trading hours, sessions & rollover](https://www.startrader.com/knowledge-intermediate/xauusd-trading-hours-open-close-best-times-to-trade-gold/)
- TMGM — [Gold (XAUUSD) trading hours / best time to trade](https://www.tmgm.com/en/academy/trading-academy/gold-trading-hours)
- Forex For Starters — [GBPJPY: How to Trade the Beast](https://forexforstarters.com/markets/minors/gbp-jpy/)
- TMTradesFx — [GBP/JPY (Geppy / Beast) trading guide](https://www.tmtradesfx.com/gbpjpy)
- Saxo — [Complete guide to trading the GBP/JPY pair](https://www.home.saxo/learn/guides/forex/how-to-trade-the-gbpjpy-forex-pair)
- FX2 Funding — [Currency correlation strategies](https://fx2funding.com/blog/what-you-should-know-about-currency-correlation/)
- arXiv — [The foreign exchange market: return distributions, multifractality, anomalous multifractality and Epps effect (1011.2385)](https://arxiv.org/pdf/1011.2385)
- Volatility numbers (ADR, ADR%, median/max DR): pre-computed from Yahoo Finance daily bars, 3 months to 2026-06-02.
