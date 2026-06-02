# R8 — Fundamental AI Overlay (Deferred Experiment): Findings

**Track:** R8 — Fundamental AI overlay (tier-3, designed-but-deferred)
**Question:** Does an AI-driven fundamental/macro overlay on higher timeframes (H1/H4/D1) actually improve results — enough to earn *any* influence over EURUSD trades — and how do we answer that with **evidence** rather than assumption?
**Date:** 2026-06-02
**Status:** Research complete. **Feature: DEFERRED. Do NOT build into core scope.**

> **Read this first.** This document is an *experiment design*, not a feature proposal and not a recommendation to build. The deterministic technical engine (R1 signal, R4 risk governor) is the product. This track exists to design a falsifiable test of a single hypothesis — *"a macro/regime bias on higher timeframes improves expectancy or reduces drawdown enough to justify its cost"* — and to specify the seam through which the answer could *later* be acted on. The default outcome we should expect, on base rates, is **reject** (see §6). The whole point of the gate is to make it easy to walk away.

---

## 1. Summary

The overlay is a **higher-timeframe macro/regime bias** that, at most, writes one optional value — `context_bias ∈ {normal, cautious, stand-down}` — to the engine. It is **not** the news blackout: a deterministic, scheduled-high-impact-news blackout already lives in the risk layer (R4 §9) and is binding from day one regardless of this track. R8 is a *softer, higher-level* signal — "is the macro tape hostile to a breakout right now?" — derived from rate differentials, central-bank stance, and a risk-on/risk-off read.

The design has three non-negotiable properties:

1. **Shadow-mode first.** When (if) we ever test it, the overlay runs in **logging-only** mode: it computes what it *would* have advised, writes that to the trade journal with a timestamp, and changes **nothing** about live trades. Advice is joined to outcomes after the fact. It only graduates logging → soft bias (size reduction / blackout windows) → never a hard live gate, and only on evidence.
2. **A pre-registered pass/fail bar.** Before looking at results we fix the counterfactual, the sample size, the significance bar (deflated per R6's multiple-testing discipline), and the explicit number that distinguishes "graduate to soft bias" from "kill the experiment." Skepticism is built in: §6 lists what makes us **reject**.
3. **A fail-safe seam.** The overlay writes only to the optional `context_bias` input. The engine treats *absent*, *stale*, and *`normal`* identically, so disabling the overlay — or a crashed/stale overlay — is a **no-op on the live path**. "Design the seam, defer the feature."

**Gating.** Per README §2 and the track card, this is started **only after** the deterministic core, the R5 improvement loop, and the journal all exist and have produced a meaningful sample of live/forward decisions. There is nothing to join advice *to* until the journal has trades in it.

**Honest read (stated up front):** the literature and base rates say discretionary macro rarely beats a disciplined technical system *intraday*; fundamentals set direction over weeks-to-months, not over a London/NY-overlap breakout's holding period ([FTMO: fundamental analysis in forex](https://ftmo.com/en/how-to-use-fundamental-analysis-in-forex/), [Trade Nation](https://tradenation.com/articles/fundamental-analysis/)). The *most defensible* version of this overlay is therefore not a direction-picker but a **risk-off / stand-down detector** — "don't fire breakouts into a hostile or untradeable macro regime" — which is a much lower bar than "predict EURUSD direction," and the one we should test.

---

## 2. What context could the overlay provide, and from which data sources

Everything here is **higher-timeframe** (H1/H4/D1) and **slow-moving**, which is what makes it cheap to compute (hourly or daily, see §3) and keeps the LLM off the hot path. The overlay's job is to compress a handful of macro series into one of three coarse states, not to forecast price.

### 2.1 The four context categories (EURUSD-specific)

**(a) Rate differentials and central-bank policy divergence.** The dominant medium-term EURUSD driver is the **Fed-vs-ECB policy gap** and the **short-end yield differential**. When the Fed is hiking/holding while the ECB is cutting (or vice-versa), the differential and its *expected path* push the pair. This is exactly what FRED serves for free and what the project's **FRED MCP** can pull directly:
- `FEDFUNDS` / `EFFR` — Fed policy rate ([FEDFUNDS](https://fred.stlouisfed.org/series/FEDFUNDS), [EFFR](https://fred.stlouisfed.org/series/EFFR)).
- `ECBDFR` — ECB Deposit Facility Rate ([ECBDFR](https://fred.stlouisfed.org/series/ECBDFR)); the Key ECB Rates release groups the three policy rates ([release 484](https://fred.stlouisfed.org/release?rid=484)).
- `DGS2` (US 2-year CMT yield, daily) as the market's *expected-path* proxy for the short end ([DGS2](https://fred.stlouisfed.org/series/DGS2), confirmed live via the FRED MCP, updated 2026-06-01). Pair with a euro-area 2-year equivalent for the differential.
- `DEXUSEU` — the daily USD/EUR reference rate, as the slow ground-truth the overlay's view should be sanity-checked against (the live engine prices off the broker feed, not FRED).
The LLM (or, better, a deterministic rule — see §2.3) summarises *"differential widening in USD's favour and central banks diverging"* → a directional lean; *"differential flat / both on hold"* → `normal`.

**(b) Risk-on / risk-off regime.** Breakout strategies behave differently in calm vs. panicked tape. The standard, mostly-free risk-regime cues are the **dollar index (DXY)**, **equity-vol (VIX)** and **bond yields / curve**: a VIX spike with falling yields is a classic risk-off signal, while rising yields + strong equities + firm dollar reads risk-on ([ACY: VIX/yields/DXY regime read](https://acy.com/en/market-news/education/gold-strategy-using-vix-yields-dxy-2025-l-s-162409/), [DXY on TradingView](https://www.tradingview.com/symbols/TVC-DXY/)). FRED carries the curve directly (`T10Y2Y`, daily, confirmed live via the MCP). VIX and DXY come from the calendar/market APIs below or a quote feed. The overlay maps a sharp risk-off regime → `cautious` or `stand-down` (breakouts into a vol spike are coin-flips with worse fills).

**(c) Economic-calendar awareness *beyond* the hard blackout.** The R4 blackout is a *binary, deterministic, short-window* gate around individual scheduled high-impact prints (don't *open* from roughly −5 to +5 min, wider for NFP/CPI/FOMC) ([R4 findings §9]). The overlay's calendar role is different and *coarser*: "is today/this session unusually **event-heavy** (FOMC + CPI + ECB in the same window)?" → a session-level `cautious` lean, distinct from the per-event lockout. Same calendar feeds R4 already evaluated:
- **Finnhub economic calendar** — JSON, impact field, generous free tier ([Finnhub calendar API](https://finnhub.io/docs/api/economic-calendar)).
- **Financial Modeling Prep (FMP)** — clean JSON economic-releases calendar, free tier + paid ([FMP economics calendar](https://site.financialmodelingprep.com/developer/docs/stable/economics-calendar)).
- **Trading Economics** — authoritative, paid, country/importance fields ([TE calendar API](https://tradingeconomics.com/api/calendar.aspx)).
- **ForexFactory** — the de-facto impact-rating standard but **no official API**; only via fragile third-party scrapers/aggregators ([ForexFactory API discussion](https://vocal.media/trader/forex-factory-economic-calendar-api)).
To avoid divergence, the overlay should **reuse R4's already-ingested calendar**, not add a parallel feed.

**(d) High-impact surprise detection.** *After* a release, did actual vs. consensus surprise materially (e.g. CPI hot by >2σ)? A large surprise → a transient `cautious` window (post-shock chop/whipsaw is hostile to mean-reverting breakout exits). Surprise = `(actual − consensus)` normalised; both fields come from the same calendar APIs above. This is the one place a news feed (e.g. an LLM summarising a headline burst) *could* add colour — but it is also the highest-hallucination-risk input (§6), so v1 should prefer the numeric surprise to free-text news.

### 2.2 How each is summarised into a single bias signal

The output is deliberately tiny — a 3-state enum, not a probability:
- `normal` — default; nothing notable; engine behaves exactly as if no overlay existed.
- `cautious` — macro tape is choppy/event-heavy/mildly risk-off; *would* advise smaller size or skipping marginal setups.
- `stand-down` — acute risk-off, a wall of tier-1 events, or a central-bank-decision day; *would* advise no new breakout entries for a defined window.

The mapping should be **mostly deterministic rules over the numeric series**, with the LLM used only to (i) *narrate/justify* the state for the journal (auditable reasoning), and (ii) optionally arbitrate genuinely ambiguous mixed signals. Keeping the LLM out of the *numeric* decision is the single biggest hallucination defence (§6) and is consistent with R5's "AI off the hot path" principle.

### 2.3 Realistic cost

Free/cheap tier: **FRED (free, already wired via MCP)** for rates/curve, **Finnhub or FMP free tier** for calendar + surprises, and DXY/VIX from the existing quote feed or the same APIs. Total recurring cost can be **$0–low**. LLM cost is negligible because the overlay runs hourly/daily, not per-tick (§3).

---

## 3. Shadow-mode design (logging-only; changes nothing)

**Principle.** In shadow mode the overlay is a *passive observer*. It reads data, computes a bias, and **appends one record to the trade journal**. The live decision path never reads that record. This is the only mode that exists until the §5 bar is cleared.

**Cadence.** Because the inputs are higher-timeframe and slow, the overlay runs **on a schedule, not per trade**: a **daily** pass at the start of the trading day (pre-London) plus an **hourly** refresh during the active EURUSD session, and an **event-triggered** refresh right after tier-1 releases for surprise detection. That is ~10–15 invocations/day — cheap, and well clear of any LLM rate/request budget (R4/R7).

**Shared journal & timestamps.** The overlay writes to the **same journal** the live engine writes its decisions to, with the **same clock** (UTC stored; CE(S)T derived, matching R4's 00:00 CEST reset semantics). This is what lets us later **join advice to outcomes**: every overlay record carries the timestamp window it was valid for, so any trade the engine opened during that window can be matched to "what the overlay would have said." Without a shared journal and shared timestamps there is no counterfactual.

**Record format (shadow mode).** Append-only JSON line, e.g.:

```json
{
  "record_type": "context_bias_shadow",
  "schema_version": 1,
  "ts_utc": "2026-06-02T06:30:00Z",
  "valid_from_utc": "2026-06-02T06:30:00Z",
  "valid_to_utc":   "2026-06-02T07:30:00Z",      // TTL window (see §5 seam)
  "instrument": "EURUSD",
  "advised_bias": "cautious",                     // normal | cautious | stand-down
  "would_action": "reduce_size_50pct",            // what soft-bias WOULD do; informational only
  "live_effect": "none",                          // ALWAYS "none" in shadow mode
  "drivers": {
    "rate_diff_2y_us_de_bps": 142,
    "rate_diff_trend": "widening_usd",
    "cb_divergence": "fed_hold_ecb_cut",
    "risk_regime": "risk_off",                     // from DXY/VIX/curve
    "vix": 23.8, "dxy": 104.7, "t10y2y": -0.05,
    "calendar_density_next_4h": "high",            // 2x tier-1 events
    "last_surprise_sigma": 1.1
  },
  "rationale": "ECB cut priced, US 2y firm; VIX>22 risk-off; CPI + ECB within 4h. Would advise smaller size on marginal breakouts.",
  "source_versions": {"fred":"2026-06-01","calendar":"finnhub@..."},
  "engine_state_ref": "decision_id or session_id"  // link back to live decisions in the same window
}
```

Two properties matter: `live_effect` is **always `"none"`** in shadow mode (a grep-able invariant a test can assert), and `engine_state_ref` ties the advisory to whatever the deterministic engine actually did in the same window. The improvement loop (R5) consumes these records exactly like any other journal data.

**Who evaluates it.** The R5 improvement loop (offline/async) owns the join-and-score job: periodically it reads the shadow records and the realised trade outcomes, builds the counterfactual of §4, and reports against the §5 bar. The overlay never grades itself in-line.

---

## 4. Evaluation methodology (the counterfactual)

**The question, precisely.** Over a meaningful sample, *would following the advice have improved the system?* Concretely: take every live/forward EURUSD trade the deterministic engine actually took, tag each with the overlay's contemporaneous bias (from the shared-timestamp join), and construct counterfactual P&L under the soft-bias policy the overlay *would* have applied:
- On `normal` windows: unchanged (this is the bulk of the sample and the control).
- On `cautious` windows: size reduced (e.g. ×0.5) and/or marginal setups skipped.
- On `stand-down` windows: the trade is **removed** (treated as not taken).

Then compare the **actual** equity curve to the **counterfactual** curve on the metrics that matter for an FTMO account:
1. **Expectancy (R-multiple, net of costs)** — did following advice raise it? (R6 gate context: the core must already clear ≥ +0.10R; the overlay must *add* to that, not just not-hurt.)
2. **Drawdown** — max depth and duration; did stand-down/size-down on `cautious`/`stand-down` windows *shave the worst stretches*? This is the most plausible place the overlay earns its keep.
3. **FTMO rule-breach proximity** — did the advice keep equity further from the 5% daily / 10% static floors? Even if expectancy is flat, *reliably reducing breach risk* has standalone value for a challenge-pass-focused bot (R4).

**Conditional analysis (the honest test).** The aggregate comparison is necessary but not sufficient — the real test is *conditional*: among trades flagged `cautious`/`stand-down`, was the realised win-rate / expectancy **actually worse** than on `normal` trades? If `stand-down`-flagged trades were, in hindsight, *no worse* (or better) than `normal` trades, the overlay is mislabelling good setups as bad and must be rejected — it is destroying edge, not protecting it. This conditional split is the core diagnostic.

**Statistical bar (and why it's strict).** A favourable counterfactual over a handful of `stand-down` events is **noise**, and we are explicitly searching across overlay configurations — so this is a multiple-testing problem exactly like R6's parameter sweeps:
- **Sample size:** require a meaningful number of *flagged* (non-`normal`) events, not just total trades — target **≥ 30–50 `cautious`/`stand-down`-tagged trades** before any conclusion, and ideally **≥ 6–12 months** of shadow data spanning more than one macro regime. A great-looking result over 5 flagged trades is folklore.
- **Significance, deflated:** apply R6's **Deflated Sharpe / multiple-testing** discipline — the improvement must survive correction for the number of overlay variants and thresholds we tried (Bailey & López de Prado) ([Deflated Sharpe Ratio](https://www.researchgate.net/publication/286121118_The_Deflated_Sharpe_Ratio_Correcting_for_Selection_Bias_Backtest_Overfitting_and_Non-Normality)). A "Sharpe uplift" found after testing 40 threshold combinations is not real uplift.
- **Robustness:** the conditional edge must hold under **Monte-Carlo trade-order reshuffles** and across **walk-forward** splits, not just on the full in-sample period.

### Explicit pass/fail bar (pre-registered before looking at results)

**GRADUATE logging → soft bias** *only if ALL* of the following hold on out-of-sample / walk-forward shadow data:
1. **Conditional edge exists:** trades tagged `cautious`/`stand-down` show a **materially worse** realised expectancy than `normal` trades — concretely **≥ 0.20R worse**, statistically distinguishable after deflation. (If the "bad" windows aren't actually bad, there is nothing to act on.)
2. **Counterfactual improves the account:** applying the soft-bias policy **either** raises net expectancy by a deflation-surviving margin **or** reduces max drawdown by **≥ 15%** *without* cutting net expectancy by more than a trivial amount.
3. **Breach safety is non-negative:** the counterfactual never *increases* proximity to any FTMO floor and ideally reduces worst-case daily-loss excursions.
4. **Sample is adequate:** ≥ 30–50 flagged trades, ≥ 6–12 months, ≥ 2 distinct macro regimes.
5. **It survives multiple-testing correction** (Deflated Sharpe / variant count) and Monte-Carlo reshuffle.

**REJECT (kill or keep-in-shadow) if ANY of:**
- Flagged windows are statistically indistinguishable from `normal` windows (no conditional edge) — the overlay is noise.
- Counterfactual *worsens* expectancy or drawdown, or only "wins" before deflation.
- The result rests on a handful of events, or flips sign across walk-forward splits / reshuffles (overfit to a couple of memorable macro episodes — see §6).
- The uplift, even if real, is smaller than the added operational risk/complexity (a stale feed mislabelling a window is itself a risk).

Even on a PASS, graduation is to **soft bias only** (size reduction / blackout windows), **never a hard live gate**, and the soft-bias version then runs its *own* shadow-vs-live comparison before any wider trust. The burden of proof is on the feature, permanently.

---

## 5. The seam contract (design confirmation)

The engine exposes exactly **one** optional input for this track:

```
context_bias: { value: "normal" | "cautious" | "stand-down", valid_to_utc: <timestamp> }   # optional
```

**Contract guarantees (these are the deferral):**
1. **Single write target.** The overlay writes *only* this `context_bias` record. It cannot touch signals (R1), sizing math, stops, or the risk governor (R4) directly. Its maximum authority, even after graduation, is to nudge size or open a soft blackout window — and only via this field.
2. **Absent ≡ `normal`.** The engine reads the field defensively: **missing field, unparseable value, and `normal` are handled by the identical code path.** Day one, the field is hardcoded `normal` and the read is a constant.
3. **TTL / staleness fail-safe.** Every record carries `valid_to_utc`. If `now > valid_to_utc` (overlay crashed, feed stale, scheduler missed a run), the engine **reverts to `normal`** — a stale bias can never silently persist. Fail-safe direction is toward *doing nothing different*, not toward acting on old data. (Contrast R4's news blackout, whose fail-safe is the *opposite* — default-to-blackout — because that gate is a hard safety rule, whereas this overlay is an optional nicety.)
4. **Disable = no-op on the live path.** Turning the overlay off (or it never having existed) leaves the engine on the `normal` path. There is **zero** code on the live trade path that *depends* on the overlay producing output. This is verifiable by a test: with the overlay process killed, live decisions are byte-identical to the hardcoded-`normal` baseline.
5. **Shadow mode writes a *different* record** (`context_bias_shadow`, §3) that the engine **does not read at all** — so even a mis-wired shadow overlay cannot affect trades.

This is the literal meaning of "design the seam, defer the feature": the field, the TTL semantics, and the absent≡normal handling are cheap to build into the engine now; everything that *fills* the field is deferred behind the §4 bar.

---

## 6. Risks & honest caveats

This section is deliberately the longest, because the default expectation is rejection.

**Base-rate skepticism (the big one).** The weight of practitioner and study evidence is that **fundamentals drive direction over weeks-to-months, not over an intraday breakout's holding period**; for pure intraday FX, technical timing dominates and macro is, at best, slow context ([FTMO](https://ftmo.com/en/how-to-use-fundamental-analysis-in-forex/), [Trade Nation](https://tradenation.com/articles/fundamental-analysis/)). A disciplined deterministic technical system with a hard risk governor is a high bar for a discretionary-flavoured macro overlay to *add* to. We should expect the overlay's *direction-picking* to fail and only its *risk-off stand-down* role to have any chance — which is why §4's bar is framed around "are flagged windows actually worse," not "can it predict EURUSD."

**Overfitting macro narratives to past trades.** It is trivially easy to find, post-hoc, a macro "reason" each losing trade happened ("of course it failed, it was an FOMC day"). With enough series and thresholds, some overlay configuration will *look* like it would have dodged the drawdowns — purely by selection. This is the same data-mining trap R6 warns about, which is why the bar demands **deflation**, **walk-forward**, **Monte-Carlo reshuffle**, and a **minimum count of flagged events**. A narrative that fits 3 historical drawdowns is worthless.

**Look-ahead bias (critical for any backtest of this).** This is the most dangerous failure mode and the easiest to commit accidentally:
- **Data-availability look-ahead:** macro series get **revised** (FRED vintages differ from first-print), and calendar `actual` values only exist *after* the release. Any backtest must use the value **as it was known at decision time** (first print / point-in-time), never the revised series. FRED's vintage/ALFRED data exists precisely for this and must be used.
- **LLM training look-ahead:** if an LLM summarises macro for a *backtest* period inside its training window, it may "know" what happened next. Recent work documents exactly this contamination and the partial fix of using models whose training cutoff predates the test window ([Lookahead bias in LLM forecasts](https://arxiv.org/pdf/2512.23847), [Look-ahead bias in GPT sentiment](https://arxiv.org/pdf/2309.17322), [Explicit bias in finance LLMs](https://arxiv.org/html/2602.14233v1)). Practical consequence: prefer **shadow-mode forward testing** (genuinely out-of-sample, no look-ahead possible) over LLM-driven historical backtests for this overlay, and keep the numeric mapping deterministic.

**LLM hallucinating macro views.** Free-text macro reasoning is the highest-risk input: an LLM can confidently assert a central-bank stance or a "risk-off" read that is wrong. Mitigations baked into §2.2: keep the *numeric* state machine deterministic over FRED/calendar series; use the LLM only to *narrate* the journal rationale and to arbitrate genuinely ambiguous cases; never let free-text news alone flip the bias. Surveys of LLM trading agents document hallucination and recommend exactly this "summarise inputs, decide with rules/indicators" structure ([LLM trading agent survey](https://arxiv.org/html/2408.06361v2)). Note the eye-catching "Sharpe 3.05 from LLM sentiment" results in the literature are **equities, daily, and not look-ahead-clean by their own admission** — do not import that optimism into intraday EURUSD ([Sentiment trading with LLMs](https://arxiv.org/pdf/2412.19245)).

**Added cost and complexity.** Even free data adds a moving part: a scheduler, two-plus external APIs that can go stale, a journal schema, and the cognitive load of reasoning about a second decision source. The TTL fail-safe (§5) bounds the *trading* risk to zero, but the *operational* and *attention* cost is real and counts against the feature in bar item §4-reject-last.

**Confusion with the R4 blackout.** Repeating because it matters: the **deterministic news blackout already exists in R4** and is binding regardless of this track. R8 must not duplicate, weaken, or be mistaken for it. If R8 is ever killed, the news blackout is untouched.

**Survivorship / regime fragility.** A few dramatic macro episodes (a CPI shock, an emergency cut) dominate any macro-overlay backtest. An overlay tuned to dodge *those specific* episodes is fitting the past, not a stable edge — hence the requirement that the conditional edge persist across walk-forward splits and regimes, not just over the memorable events.

**Bottom line.** This is a well-defined, falsifiable experiment with a strict, pre-registered bar and a zero-risk seam — exactly what "evidence-gated" (README §2) demands. It is *also* an experiment we should expect to fail, and we should be glad to fail it cheaply. Build the seam (a few lines), defer the feature, and only spend real effort once the core, R5, and a journal with a real trade history exist. If the conditional test in §4 ever clears the §5 bar, graduate to **soft bias in shadow** — and never further than the evidence carries.

---

## Sources

- FTMO — *How to use fundamental analysis in forex*: https://ftmo.com/en/how-to-use-fundamental-analysis-in-forex/
- Trade Nation — *Fundamental analysis and how to apply it*: https://tradenation.com/articles/fundamental-analysis/
- FRED — Federal Funds Effective Rate (FEDFUNDS): https://fred.stlouisfed.org/series/FEDFUNDS
- FRED — Effective Federal Funds Rate (EFFR): https://fred.stlouisfed.org/series/EFFR
- FRED — ECB Deposit Facility Rate (ECBDFR): https://fred.stlouisfed.org/series/ECBDFR
- FRED — Key ECB Interest Rates (release 484): https://fred.stlouisfed.org/release?rid=484
- FRED — 2-Year Treasury CMT Yield (DGS2): https://fred.stlouisfed.org/series/DGS2  *(confirmed live via the project FRED MCP, last updated 2026-06-01)*
- FRED — 10Y minus 2Y spread (T10Y2Y): used as curve/risk-regime input *(confirmed live via FRED MCP)*
- FRED API docs: https://fred.stlouisfed.org/docs/api/fred/
- Finnhub — Economic Calendar API (free tier, impact field): https://finnhub.io/docs/api/economic-calendar
- Financial Modeling Prep — Economic Data Releases Calendar API: https://site.financialmodelingprep.com/developer/docs/stable/economics-calendar
- Trading Economics — Calendar API: https://tradingeconomics.com/api/calendar.aspx
- ForexFactory calendar (no official API; third-party only): https://vocal.media/trader/forex-factory-economic-calendar-api
- ACY — Building a strategy using VIX, US yields, and DXY (risk-on/off regime read): https://acy.com/en/market-news/education/gold-strategy-using-vix-yields-dxy-2025-l-s-162409/
- TradingView — U.S. Dollar Index (DXY): https://www.tradingview.com/symbols/TVC-DXY/
- Bailey & López de Prado — *The Deflated Sharpe Ratio* (multiple-testing / overfitting): https://www.researchgate.net/publication/286121118_The_Deflated_Sharpe_Ratio_Correcting_for_Selection_Bias_Backtest_Overfitting_and_Non-Normality
- *A Test of Lookahead Bias in LLM Forecasts* (arXiv): https://arxiv.org/pdf/2512.23847
- *Assessing Look-Ahead Bias in Stock Return Predictions from GPT Sentiment* (arXiv): https://arxiv.org/pdf/2309.17322
- *Evaluating LLMs in Finance Requires Explicit Bias Consideration* (arXiv): https://arxiv.org/html/2602.14233v1
- *Large Language Model Agent in Financial Trading: A Survey* (arXiv): https://arxiv.org/html/2408.06361v2
- *Sentiment trading with large language models* (arXiv): https://arxiv.org/pdf/2412.19245

### Cross-references (internal)
- **R4 — FTMO rules & risk model** (`R4-risk/findings.md`) §9: the *deterministic* news blackout, distinct from this overlay.
- **R6 — Backtesting stack & data** (`R6-backtest/findings.md`): Deflated-Sharpe / multiple-testing discipline, walk-forward, Monte-Carlo reshuffle, FTMO-breach gating reused in §4.
- **R5 — AI improvement loop** (README §R5): the offline/async loop that owns the shadow-record join-and-score job and the §5 evaluation.
- **README §2:** technical-first, AI off the hot path, evidence-gated — the principles this track operationalises.
