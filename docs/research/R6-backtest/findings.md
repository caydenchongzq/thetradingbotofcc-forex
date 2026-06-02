# R6 — Backtesting Stack & Data

**Track:** R6 — Backtesting stack & data
**Question:** How do we rigorously validate a strategy before risking an FTMO account — what tooling, what data, what metrics and gates, and how do we avoid fooling ourselves with an overfit backtest?
**Date:** 2026-06-02
**Status:** Research complete

---

## Summary

The backtest is the single most important guardrail in this project: it is the only place we can find out whether the R1 strategy — a session-gated London/NY-overlap volatility breakout with an Efficiency-Ratio + ATR regime gate, pivot±ATR stops, R-multiple partial TP and a bar-close step-trailed runner — would have *survived an FTMO challenge* without ever risking real evaluation capital. For an intraday EURUSD edge, the make-or-break is not the signal logic but the **cost and execution model**: spread (~0.4 pip), commission (~$14 round-trip per lot), and slippage routinely consume the entire theoretical edge of a breakout strategy, so any framework we pick must model all three faithfully and let us simulate FTMO's equity-based drawdown rules bar-by-bar.

**Recommended stack:** a **custom event-driven backtest loop in Python** as the system of record, with **Backtesting.py** ([repo](https://github.com/kernc/backtesting.py)) as a fast sanity-check harness for early single-instrument prototyping, and **vectorbt (open-source, Apache-2.0)** ([repo](https://github.com/polakowo/vectorbt)) as the vectorized engine for large parameter sweeps and walk-forward optimization. We deliberately do **not** adopt backtrader (effectively unmaintained — see below) as the core, and we treat nautilus_trader ([repo](https://github.com/nautechsystems/nautilus_trader)) as the *optional* high-fidelity validation engine if/when we want a second, independent, execution-realistic cross-check before going live. The reason for a custom core is that our strategy's exit logic (partial TP + bar-close step-trailing runner) and our FTMO-rule simulation (5% daily equity loss with a 00:00 CE(S)T reset, 10% static max loss, intraday breach detection) are exactly the things off-the-shelf libraries model *badly* — so owning the loop removes the single biggest source of "the backtest lied to me."

**Primary data source:** **Dukascopy tick data** (bid/ask, free) for development and the bulk of validation, because bid/ask is mandatory for honest spread modeling and tick granularity is the only way to model intrabar stop/limit fills correctly. **HistData.com** 1-minute is a useful free secondary/cross-check (but its bar files are bid-only). The **final** pre-promotion validation must additionally be run on **the broker/FTMO MT5 feed itself** (`copy_rates`/`copy_ticks` from the funded broker's terminal), because that is the exact price stream the live account will trade against, and matching it closes the largest backtest-to-live gap.

**Headline acceptance gates** (all must pass to promote backtest → forward-test → evaluation): expectancy ≥ **+0.10R net of all costs** over a statistically meaningful sample (**≥ 200–300 trades** and **≥ 3–5 years** of out-of-sample history spanning multiple regimes); **profit factor ≥ 1.3** net; **Sharpe ≥ 1.0 / Sortino ≥ 1.5**; out-of-sample walk-forward efficiency that does **not** collapse versus in-sample; parameter-stability (no knife-edge optima); and — the hard, non-negotiable gate — **zero simulated FTMO rule breaches** across the full history *and* across Monte-Carlo trade-order reshuffles, i.e. the simulated equity curve must never cross the 5% daily or 10% static loss line. A strategy that is profitable but would have tripped a daily-loss breach is a **fail**, not a tweak.

---

## 1. Backtesting tooling for Python

The honest landscape in mid-2026 is that there is no single library that does everything we need well. The relevant axes are: (a) can it model intraday FX with **bid/ask spread, per-lot commission, and slippage**; (b) can it model **partial exits + step-trailing stops** without hacks; (c) **multi-position / portfolio**; (d) **speed** for sweeps and walk-forward; (e) **maintenance** as of 2025–2026; (f) **learning curve**.

### backtrader — mature but effectively unmaintained

backtrader ([mementum/backtrader](https://github.com/mementum/backtrader)) is the classic, feature-rich, event-driven retail framework. It handles multi-asset, multi-timeframe, commission schemes, and broker integrations cleanly. The problem is maintenance: the original author considers the project **complete** and the repo is **not open to changes**; package-health trackers flag it as **inactive / discontinued**, with no recent PyPI releases ([Snyk advisor](https://snyk.io/advisor/python/backtrader), ["Is Backtrader dead?" community thread](https://community.backtrader.com/topic/3702/is-backtrader-dead)). Community forks (`backtrader2`, `backtrader-lucidinvestor`) exist but have limited activity and naming confusion. For a project that will live for years and feed an AI improvement loop, building the core on an abandoned dependency is an avoidable risk. **Verdict: not the core.** Fine as a reference implementation; not a foundation.

### Backtesting.py — easy, fast to prototype, but limited

Backtesting.py ([kernc/backtesting.py](https://github.com/kernc/backtesting.py)) is the quickest way to get a clean single-instrument backtest with a built-in optimizer and good plots. It supports commission and a basic trailing stop (`TrailingStrategy.set_trailing_sl`, ATR-based) and you can mutate `trade.sl` mid-trade ([Strategies Library](https://kernc.github.io/backtesting.py/doc/examples/Strategies%20Library.html), [trailing-stop discussion](https://github.com/kernc/backtesting.py/discussions/238)). Its limits matter for us: it is **single-instrument** (no real portfolio), partial exits and a multi-leg "partial TP + trailing runner" require workarounds, and it does not natively model a true bid/ask spread feed — you approximate spread via commission. **Verdict: keep as a fast prototyping/sanity harness, not the system of record.**

### vectorbt (open-source) / vectorbt-pro — speed for sweeps

vectorbt ([polakowo/vectorbt](https://github.com/polakowo/vectorbt)) is NumPy/pandas/Numba-vectorized and is the fastest realistic option for **massive parameter sweeps** (hundreds of thousands of parameter combinations in seconds) — exactly what walk-forward optimization and parameter-stability mapping need. Maintenance: the open-source version (Apache-2.0 with Commons Clause) is still bug-maintained by the author, but new feature work has migrated to the paid, invitation-only **vectorbt-pro** ([Future of VectorBT discussion](https://github.com/polakowo/vectorbt/discussions/619), [vectorbt.pro](https://vectorbt.pro/)). The trade-off: vectorized engines model **path-dependent** logic (intrabar step-trailing, partial fills, sequenced exits) less naturally than an event loop, so vectorbt is excellent for *ranking* parameter regions cheaply but should **not** be the final arbiter of P&L — the custom event loop is. **Verdict: adopt the open-source version as the sweep/optimization engine; pro is optional if speed/feature pressure justifies the subscription.** The Commons-Clause license is fine for internal use (we are not reselling it).

### nautilus_trader — highest execution fidelity, steepest curve

nautilus_trader ([nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader)) is a Rust-core, Python-API, **deterministic event-driven** engine explicitly designed to *minimize the backtest-to-live gap* — nanosecond-resolution quote/trade/bar/order-book simulation, realistic fill models, and the same strategy code runs in backtest and live ([backtesting concepts](https://nautilustrader.io/docs/latest/concepts/backtesting/)). It is **actively maintained** with a roughly bi-weekly release cadence through 2026 ([releases](https://github.com/nautechsystems/nautilus_trader/releases)). The cost is a **steep learning curve** and heavier infrastructure — it is a trading-systems framework, not a quick research notebook. **Verdict: optional second engine for final, execution-realistic validation and as a path to a unified backtest/live codebase later; overkill for early iteration.**

### zipline-reloaded — wrong shape for intraday FX

zipline-reloaded ([stefan-jansen/zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded)) is the maintained successor to Quantopian's Zipline and is still active in 2025–2026 ([repo](https://github.com/stefan-jansen/zipline-reloaded)). But it is built around **US equities, daily/minute bars, trading calendars and data bundles** — spot FX, 24×5 sessions, and bid/ask spread modeling are not its native home and require fighting the framework. **Verdict: not suitable here.**

### Custom event-driven loop — the system of record

A purpose-built event-driven loop (iterate bars/ticks in time order; on each bar evaluate signals, manage open positions, apply spread/commission/slippage, update trailing stops at bar close, and run the FTMO equity-rule checks) is more work up front but gives us the three things no library does well for *this* strategy:

1. **Exact exit logic** — partial TP at an R-multiple plus a bar-close step-trailed runner is path-dependent and idiosyncratic; owning the loop means the backtest matches the live execution code one-to-one (and can literally share the position-management module).
2. **Faithful FTMO simulation** — equity-based 5% daily loss with a **00:00 CE(S)T reset**, 10% static max loss, and **intraday** (real-time, not end-of-day) breach detection (see §3) is trivial to implement in a loop and awkward-to-impossible in vectorized/black-box engines.
3. **Honest cost model** — explicit bid/ask at fill, commission per side, and configurable slippage per entry type (see §5).

**Recommended stack, concretely:** custom event-driven loop = system of record and the thing that gates promotions and feeds the R5 "Backtest Analyst" agent; **vectorbt (OSS)** = fast sweep/WFO engine to find robust parameter *regions* (then re-run finalists through the event loop); **Backtesting.py** = lightweight prototyping/sanity harness; **nautilus_trader** = optional high-fidelity final cross-check and future unified backtest/live engine. Reference: a structured comparison of these frameworks for 2025–2026 ([autotradelab framework comparison](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded), [python.financial 2026 landscape](https://python.financial/)).

---

## 2. Historical data sources (development vs validation)

The decisive property for an intraday breakout with a 0.4-pip edge budget is **bid/ask, not mid** — a mid-price backtest silently omits the spread and will overstate the edge enough to flip a losing strategy "profitable." Tick granularity matters second, because intrabar fills on stops/limits cannot be modeled honestly from OHLC bars alone.

**Dukascopy (tick, bid/ask, free) — primary.** Dukascopy's historical export provides genuine **tick-by-tick bid/ask** data for 1,600+ instruments including FX majors and XAUUSD, free, in CSV, with deep history ([Dukascopy Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/), [Tickstory date ranges](https://tickstory.com/dukascopy-historical-data-available-date-ranges/)). It is widely regarded as the highest-quality free tick source. Practical caveat: the public download endpoints rate-limit (HTTP 429/503 after ~5–10 req/s), so bulk pulls take time and should be cached; open-source downloaders (`duka`, `dukascopy-node`, theorycraft-trading) help ([duka](https://giuse88.github.io/duka/), [theorycraft-trading/dukascopy](https://github.com/theorycraft-trading/dukascopy)). **Use for: development and the bulk of validation.**

**HistData.com (1-min + tick, free) — secondary / cross-check.** Easy bulk 1-minute downloads with a tidy Python API ([histdata download page](https://www.histdata.com/download-free-forex-data/), [philipperemy/FX-1-Minute-Data](https://github.com/philipperemy/FX-1-Minute-Data)). **Important limitation:** the **M1 bar files are bid-only**; bid/ask spread is only available in the **Generic ASCII tick** export, and the data carries gaps (>1-minute gaps are common in thin liquidity) with no warranty ([HistData FAQ](https://www.histdata.com/f-a-q/)). **Use for: a free independent cross-check, and tick where spread is needed — but Dukascopy is preferred for spread realism.**

**TrueFX (tick, bid/ask, free).** Tick-by-tick top-of-book bid/ask with millisecond GMT timestamps for majors, aggregated from multiple bank/market-maker sources ([TrueFX downloads](https://www.truefx.com/truefx-historical-downloads/)). Quality is good but has **occasional missing days and bad ticks**, so it is best as a corroborating source rather than the sole feed. **Use for: cross-validation of Dukascopy fills/spreads.**

**Tickstory (tooling over Dukascopy).** Not a separate feed — a desktop app that downloads Dukascopy tick data and converts it to MT4/MT5 formats for "99% modeling quality" backtests ([tickstory.com](https://tickstory.com/)). Useful if we ever want to validate inside MT5's Strategy Tester, but note MT5 stores OHLC, not ticks, internally. **Use for: optional MT5-side validation convenience.**

**Broker MT5 history (`copy_rates` / `copy_ticks`) — mandatory for final validation.** The R3 track confirmed we can pull OHLC and tick history directly from the FTMO/broker MT5 terminal in Python. **This is the exact feed the live account trades against**, including the broker's actual spreads and any feed quirks, so the *final* pre-promotion backtest must be re-run on it to catch divergence from Dukascopy. Limitation: broker history depth is shallower and generally lower-quality than Dukascopy/TrueFX for deep-history work ([broker data discussion](https://www.mql5.com/en/blogs/post/752891)). **Use for: final validation only — matching the execution venue.**

**Polygon.io.** Solid REST/WebSocket/flat-file FX coverage (1,000+ pairs) but priced for ongoing API use and oriented to US markets; more relevant as a *live/recent* data API than for cheap deep historical FX research ([Polygon forex docs](https://polygon.io/docs/forex), [Polygon pricing](https://polygon.io/pricing)). **Use for: optional live/recent data, not core historical research.**

**Databento.** Excellent for high-fidelity *exchange-listed* data, but it **does not provide spot FX** — its FX coverage is futures, and spot ('X') is an unsupported instrument class ([Databento docs](https://databento.com/), [Nautilus Databento integration](https://nautilustrader.io/docs/latest/integrations/databento/)). **Not applicable** to our spot-EURUSD use case (only relevant if we ever trade FX futures).

**FTMO's own feed.** FTMO does not publish a separate historical data product; in practice "FTMO's feed" = the FTMO MT5 terminal's `copy_rates`/`copy_ticks`, i.e. the broker-MT5 row above. The actionable point is the same: **match the FTMO terminal's prices for the final check.**

**Decision:** develop and bulk-validate on **Dukascopy tick (bid/ask)**; cross-check with **HistData / TrueFX**; run the **final** gate on the **FTMO MT5 feed** to match the live venue. Overview of the broader source landscape: [top forex data sources roundup](https://newyorkcityservers.com/blog/top-12-sources-to-download-forex-historical-data-free-paid).

---

## 3. Metrics & explicit pass/fail gates

We compute two metric families on every backtest: **per-trade/edge metrics** and **risk-adjusted/curve metrics**, plus the **FTMO-rule simulation**.

**Edge metrics.** Expectancy (average R per trade, net of all costs) is the headline — for a breakout it must clear costs by a real margin. Win rate and average win/loss R together explain the expectancy. **Profit factor** (gross profit / gross loss) summarizes edge density: PF > 1.5 is "solid," > 2 "outstanding," and we treat **PF ≥ 1.3 net** as the minimum bar ([QuantifiedStrategies — trading performance](https://www.quantifiedstrategies.com/trading-performance/)). **MAE/MFE** distributions ([MAE/MFE guide](https://trademetria.com/blog/understanding-mae-and-mfe-metrics-a-guide-for-traders/)) tell us whether stops and partial-TP levels are placed sensibly (e.g. if MFE shows we routinely leave large favorable excursions on the table, the TP/trail is mistuned; if MAE clusters just beyond our stop, the stop is too tight).

**Risk-adjusted / curve metrics.** **Max drawdown** (depth and duration) is the dominant constraint because FTMO caps it. **Sharpe** (target ≥ 1.0), **Sortino** (downside-only, target ≥ 1.5–2.0), and **Calmar** (annual return / max DD, where > 2–3 is good) capture return per unit of risk and per unit of drawdown ([advanced trading metrics](https://tradingwyckoff.com/en/algorithmic-trading/advanced-trading-metrics/)). **Exposure** (% of time in market) and **trade count** contextualize statistical significance — a beautiful Sharpe over 30 trades is noise. A common rule of thumb: SQN ≥ 2.5 over ≥ 100 trades, positive expectancy after ≥ 50 trades per setup ([QuantifiedStrategies](https://www.quantifiedstrategies.com/trading-performance/)); we set a *higher* bar than the minimum because we are gating real money (see gates below).

**FTMO-rule-breach simulation (hard gate).** The backtest must run an FTMO-account simulator alongside the equity curve, replicating FTMO's actual rules: the **Maximum Daily Loss = balance at 00:00 CE(S)T − 5% of initial capital**, recalculated each midnight CE(S)T; the **Maximum (static) Loss = 10%** of initial capital; both are **equity-based** (include floating P/L, commissions, swaps) and **breach in real time intraday**, not at end of day ([FTMO Academy — Maximum Daily Loss](https://academy.ftmo.com/lesson/maximum-daily-loss/), [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)). The simulator must therefore track **intrabar equity lows** (not just bar closes) and flag the *first* timestamp equity would have crossed either line. (R4 owns the authoritative rule model; R6 implements its simulation in the loop.)

### Promotion gates

A strategy advances through three stages; each stage has explicit pass/fail criteria. Anything failing a hard gate is rejected, not patched-and-re-tested on the same data (that is how curve-fitting starts).

**Stage 1 — Backtest → Demo forward-test.** All of: (1) **net expectancy ≥ +0.10R** after spread + commission + slippage; (2) **profit factor ≥ 1.3** net; (3) **Sharpe ≥ 1.0**, **Sortino ≥ 1.5**; (4) **≥ 200–300 trades** out-of-sample over **≥ 3–5 years** spanning trending *and* ranging regimes; (5) walk-forward efficiency healthy and parameters stable (§4); (6) **HARD GATE: zero simulated FTMO breaches** across the full history; (7) **HARD GATE:** survives Monte-Carlo trade-order reshuffle without a simulated breach in the worst-case paths (§4).

**Stage 2 — Demo forward-test → Evaluation account.** Run the *frozen, unchanged* strategy on a live demo (or paper) feed for a defined period (e.g. 1–3 months / ≥ 30–50 live trades). Pass if live expectancy and drawdown are **within the Monte-Carlo confidence band** of the backtest — i.e. live performance is statistically consistent with backtest, not merely positive. Material divergence (live edge collapses, or slippage is worse than modeled) is a **fail** and feeds back into the cost model. This stage is the primary backtest-to-live drift detector for the R5 loop.

**Stage 3 — Evaluation account.** Trade the FTMO challenge with the same frozen logic and position sizing validated by R4. The backtest's FTMO simulator should already imply a high pass probability; ongoing monitoring watches for live-vs-backtest drift.

---

## 4. Walk-forward & anti-overfitting methodology

Curve-fitting is the implicit failure mode of any prior discretionary/ad-hoc system and the thing this track exists to prevent. The defenses, in order of importance:

**Strict out-of-sample discipline.** Reserve a final OOS block that is touched **once**, at the very end, for the promotion decision — never for tuning. Any parameter chosen by looking at a data segment makes that segment in-sample.

**Walk-forward optimization (WFO).** Roll an in-sample (IS) optimization window forward and test on the immediately following OOS window, repeatedly across history ([QuantInsti WFO intro](https://blog.quantinsti.com/walk-forward-optimization-introduction/), [Surmount WFA vs backtesting](https://surmount.ai/blogs/walk-forward-analysis-vs-backtesting-pros-cons-best-practices)). The key statistic is **walk-forward efficiency** = OOS performance / IS performance; if OOS is a small fraction of IS, the strategy is overfit. WFO also produces a realistic OOS equity curve stitched from many small OOS windows.

**Purged & embargoed cross-validation.** Standard k-fold leaks information across the train/test boundary in time-series. **Purged k-fold** removes training samples whose label/outcome window overlaps the test set, and an **embargo** drops a buffer immediately after each test fold; **Combinatorial Purged CV (CPCV)** generates many train/test combinations and yields lower Probability of Backtest Overfitting (PBO) than plain WFO ([CPCV with code](https://www.quantbeckman.com/p/with-code-combinatorial-purged-cross), [synthetic OOS comparison, ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)). For an intraday strategy with multi-bar trade horizons, purging/embargo is necessary to avoid label leakage from overlapping trades.

**Parameter-stability checks.** Map performance across the parameter grid (vectorbt makes this cheap). A robust edge sits on a **broad plateau** — neighboring parameters perform similarly. A lone sharp spike ("knife-edge optimum") is almost certainly fitted to noise and is a **reject** signal even if its point estimate is great.

**Monte-Carlo on trade order / equity-curve bootstrap.** Reshuffle the trade sequence (permutation) and resample trades with replacement (bootstrap) ~**1,000–5,000 times** to build a distribution of equity paths, max-drawdowns, and — critically — **simulated FTMO breaches** ([Monte-Carlo robustness](https://blog.pickmytrade.trade/monte-carlo-trading-simulation-strategy-robustness-testing/), [BuildAlpha robustness guide](https://www.buildalpha.com/robustness-testing-guide/)). The historical trade order is just one of many possible sequences; a strategy that only avoids a daily-loss breach because the losers happened to be spread out is fragile. We require the **worst-case Monte-Carlo paths** to stay within FTMO limits, and we read the drawdown distribution (it routinely reveals drawdowns several× larger than the single backtest path) into the R4 sizing decision.

**Multiple-testing / deflated-Sharpe awareness.** Every parameter combination and every strategy variant we try is a *trial*, and the best-of-N Sharpe is upward-biased by selection. The **Deflated Sharpe Ratio** corrects the observed Sharpe for the number of trials and the non-normality of returns, penalizing edges that emerged from heavy data-mining ([Deflated Sharpe Ratio, Bailey & López de Prado](https://www.researchgate.net/publication/286121118_The_Deflated_Sharpe_Ratio_Correcting_for_Selection_Bias_Backtest_Overfitting_and_Non-Normality)). We track the count of configurations tested and deflate accordingly — a "Sharpe 1.4" found after testing 500 variants is not a Sharpe 1.4.

**How much is enough?** Statistically, target **≥ 200–300 trades** out-of-sample (and ≥ ~100 absolute minimum to say anything) and **≥ 3–5 years** of history so the sample spans at least one trending and one ranging/low-vol regime and several news cycles. Fewer trades or a single-regime window means the result is anecdote, not evidence — and for a session-gated intraday strategy generating few trades per day, this is the binding constraint on how short a history we can trust.

---

## 5. Realistic execution modeling (and backtest-to-live drift)

Costs and fills are where intraday edges live or die, so the loop models them explicitly rather than via a single round-number "commission."

**Spread.** Apply the **actual bid/ask** at fill from the data feed (this is why we insist on Dukascopy/TrueFX bid/ask, §2): buys fill at ask, sells at bid. Around **session opens and high-impact news**, spread widens well beyond the ~0.4-pip baseline — the model should widen the modeled spread in those windows (and the strategy is already session-gated to the London/NY overlap, which is liquid, but the macro-news calendar still matters). Underestimating spread is the most common way a breakout backtest lies.

**Commission.** ~**$7/lot/side ≈ $14 round-trip** per standard lot, applied on entry and exit, scaled to position size from R4. This is a fixed, known drag and must be in the per-trade P&L, not approximated away.

**Intrabar stop/limit fills.** OHLC bars hide the path within the bar, so we adopt **pessimistic fill assumptions**: a stop is assumed filled at the stop price **plus slippage** (never better), and if both the stop and a TP could have been touched in the same bar, assume the **adverse** one first unless tick data proves otherwise ([TradingView fill assumptions](https://www.tradingcode.net/tradingview/limit-fill-assumption/), [bar-magnifier intrabar inspection](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/)). Where we have Dukascopy **tick** data, we resolve the true intrabar sequence directly — the strongest argument for using tick data on the finalists rather than relying on bar-level assumptions.

**Slippage on breakout entries.** Breakout entries are momentum orders filled into a fast-moving book, so they slip **adversely** more than mean-reversion entries. Model a configurable slippage (e.g. a fixed pip allowance plus an ATR- or volatility-scaled component for news/open windows), always against us, and stress-test the strategy's sensitivity to the slippage assumption — if a small increase in modeled slippage erases the edge, the edge is too thin for live trading.

**The backtest-to-live gap (for the R5 loop).** Even a careful backtest diverges from live because of real spread/slippage variability, requotes, latency, and partial fills ([backtest limitations discussion](https://www.elitetrader.com/et/threads/understanding-the-limitations-of-backtesting-in-trading-systems.384617/)). Two design choices shrink and surface this gap: (1) running the **final** validation on the **FTMO MT5 feed** (§2) so the price stream matches; and (2) the **Stage-2 demo forward-test** (§3), which compares live fills against the modeled cost assumptions trade-by-trade. The differences (realized vs modeled slippage, realized vs modeled spread) are exactly the signal the R5 "Backtest Analyst" agent monitors to detect drift and decide when a strategy needs re-validation or retirement. nautilus_trader's design goal — running identical strategy code in backtest and live — is the structural way to minimize this gap if we later unify the engines ([Nautilus backtesting](https://nautilustrader.io/docs/latest/concepts/backtesting/)).

---

## Sources

**Tooling**
- [mementum/backtrader — GitHub](https://github.com/mementum/backtrader)
- [Snyk advisor — backtrader (inactive/discontinued)](https://snyk.io/advisor/python/backtrader)
- ["Is Backtrader dead?" — Backtrader Community](https://community.backtrader.com/topic/3702/is-backtrader-dead)
- [kernc/backtesting.py — GitHub](https://github.com/kernc/backtesting.py)
- [Backtesting.py Strategies Library (trailing SL)](https://kernc.github.io/backtesting.py/doc/examples/Strategies%20Library.html)
- [Backtesting.py trailing-stop discussion #238](https://github.com/kernc/backtesting.py/discussions/238)
- [polakowo/vectorbt — GitHub](https://github.com/polakowo/vectorbt)
- [Future of VectorBT — discussion #619](https://github.com/polakowo/vectorbt/discussions/619)
- [VectorBT PRO](https://vectorbt.pro/)
- [nautechsystems/nautilus_trader — GitHub](https://github.com/nautechsystems/nautilus_trader)
- [nautilus_trader — Backtesting concepts](https://nautilustrader.io/docs/latest/concepts/backtesting/)
- [nautilus_trader — Releases](https://github.com/nautechsystems/nautilus_trader/releases)
- [stefan-jansen/zipline-reloaded — GitHub](https://github.com/stefan-jansen/zipline-reloaded)
- [Framework comparison — autotradelab](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded)
- [The Python Backtesting Landscape 2026 — python.financial](https://python.financial/)

**Data**
- [Dukascopy — Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- [Tickstory — Dukascopy date ranges](https://tickstory.com/dukascopy-historical-data-available-date-ranges/)
- [duka — Dukascopy downloader](https://giuse88.github.io/duka/)
- [theorycraft-trading/dukascopy — GitHub](https://github.com/theorycraft-trading/dukascopy)
- [HistData.com — download free forex data](https://www.histdata.com/download-free-forex-data/)
- [HistData.com — FAQ (bid-only M1, gaps)](https://www.histdata.com/f-a-q/)
- [philipperemy/FX-1-Minute-Data — GitHub](https://github.com/philipperemy/FX-1-Minute-Data)
- [TrueFX — historical downloads](https://www.truefx.com/truefx-historical-downloads/)
- [Tickstory](https://tickstory.com/)
- [Polygon.io — Forex docs](https://polygon.io/docs/forex)
- [Polygon.io — pricing](https://polygon.io/pricing)
- [Databento](https://databento.com/) / [Nautilus Databento integration (spot FX unsupported)](https://nautilustrader.io/docs/latest/integrations/databento/)
- [Top 12 forex historical data sources](https://newyorkcityservers.com/blog/top-12-sources-to-download-forex-historical-data-free-paid)

**Metrics & FTMO simulation**
- [QuantifiedStrategies — trading performance metrics](https://www.quantifiedstrategies.com/trading-performance/)
- [Advanced trading metrics (Sharpe/Sortino/Calmar/SQN)](https://tradingwyckoff.com/en/algorithmic-trading/advanced-trading-metrics/)
- [MAE/MFE guide](https://trademetria.com/blog/understanding-mae-and-mfe-metrics-a-guide-for-traders/)
- [FTMO Academy — Maximum Daily Loss](https://academy.ftmo.com/lesson/maximum-daily-loss/)
- [FTMO — Trading Objectives](https://ftmo.com/en/trading-objectives/)

**Walk-forward & anti-overfitting**
- [QuantInsti — Walk-Forward Optimization](https://blog.quantinsti.com/walk-forward-optimization-introduction/)
- [Surmount — Walk-Forward vs Backtesting](https://surmount.ai/blogs/walk-forward-analysis-vs-backtesting-pros-cons-best-practices)
- [Combinatorial Purged Cross-Validation (with code)](https://www.quantbeckman.com/p/with-code-combinatorial-purged-cross)
- [Backtest overfitting: OOS testing methods — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)
- [Deflated Sharpe Ratio — Bailey & López de Prado](https://www.researchgate.net/publication/286121118_The_Deflated_Sharpe_Ratio_Correcting_for_Selection_Bias_Backtest_Overfitting_and_Non-Normality)
- [Monte-Carlo robustness testing — PickMyTrade](https://blog.pickmytrade.trade/monte-carlo-trading-simulation-strategy-robustness-testing/)
- [BuildAlpha — robustness testing guide](https://www.buildalpha.com/robustness-testing-guide/)

**Execution modeling**
- [TradingView — limit fill assumption](https://www.tradingcode.net/tradingview/limit-fill-assumption/)
- [TradingView — bar magnifier (intrabar)](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/)
- [Limitations of backtesting — Elite Trader](https://www.elitetrader.com/et/threads/understanding-the-limitations-of-backtesting-in-trading-systems.384617/)
