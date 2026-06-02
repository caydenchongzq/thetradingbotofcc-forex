# R3 — Execution Platform Reality-Check

**Track:** R3 — Execution platform reality-check
**Question:** Can MT5 + Python do everything we need on an FTMO account, and what (if anything) is TradingView genuinely better at?
**Date:** 2026-06-02
**Status:** Research complete

---

## Summary

The locked baseline — **MetaTrader 5 driven by the official `MetaTrader5` Python package** — is confirmed as viable and is the correct choice for this project. The package is a first-party MetaQuotes product that can connect to an FTMO MT5 account, read live equity/balance/positions, and place, modify, and close orders with stop-loss and take-profit, all from deterministic Python. FTMO explicitly permits algorithmic trading and Expert Advisors, and the platform-side limits we must respect (notably **2,000 server requests per day** and **200 simultaneous orders**) come straight from FTMO's own FAQ, which validates a core design constraint we already assumed.

There are real, non-negotiable operational constraints. The `MetaTrader5` package is **Windows-only**, it is **not headless** — a real MT5 terminal process must be running and logged in for any Python call to succeed — and it talks to that terminal over local inter-process communication (IPC). This dictates our infrastructure: a Windows VPS (or a Windows VM / Wine bridge) with the terminal kept alive and auto-restarted. These are reliability engineering problems, not blockers.

TradingView is **not justified as a signal source or an automation dependency** for this project. Because our trade logic is deterministic Python that already has direct access to MT5 price data and order execution, routing signals through TradingView Pine → webhook → bridge → MT5 adds a paid subscription, an external point of failure, and webhook latency/reliability risk for no functional gain. TradingView earns at most a low-tier subscription as a **human research and chart-review aid**, not a hot-path component. cTrader's C#/.NET cBots are a genuinely cleaner automation environment, but they do not beat MT5+Python decisively enough to overturn a Python-language baseline, and switching would cost us the Python ecosystem we depend on for backtesting and the AI improvement loop.

**Verdict: GO on MT5 + Python as the baseline. TradingView subscription: not justified for the hot path; optional cheap tier for human chart review only.**

---

## 1. The MetaTrader5 Python package

### What it can do (confirmed against the official MQL5 reference)

The `MetaTrader5` package is published and documented by MetaQuotes itself, installed with `pip install MetaTrader5` ([MQL5 Python Integration reference](https://www.mql5.com/en/docs/python_metatrader5)). The official function table confirms every capability our FTMO bot needs:

- **Connect / authenticate:** `initialize()` establishes a connection to a running MT5 terminal, and `login()` connects to a specific trading account with server/password ([initialize](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py), [MQL5 Python Integration reference](https://www.mql5.com/en/docs/python_metatrader5)).
- **Read live account state:** `account_info()` returns live balance, equity, margin, free margin and profit ([account_info](https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py)). `positions_get()` / `positions_total()` return open positions, and `orders_get()` returns active pending orders — both filterable by symbol or ticket ([MQL5 Python Integration reference](https://www.mql5.com/en/docs/python_metatrader5)).
- **Place / modify / close orders with SL/TP:** `order_send()` submits a trade request structure; `order_check()` pre-validates margin sufficiency. A market entry uses `TRADE_ACTION_DEAL` with `sl`/`tp` fields; modifying the SL/TP of a live position uses `TRADE_ACTION_SLTP` referencing the position `ticket`; closing is a counter-`order_send` on the position ([order_send](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py); worked SLTP example: [TradePretty — Managing Orders with MT5 and Python](https://tradepretty.com/orders-mt5-python/), [Medium — Modifying Open Trades](https://medium.com/@elospieconomics/algorithmic-trading-with-python-and-mt5-modifying-open-trades-8622d31632f3)).
- **Read market data natively:** `copy_rates_from_pos()` / `copy_rates_range()` return OHLC bars at any timeframe down to M1, and `copy_ticks_*` return tick history ([MQL5 Python Integration reference](https://www.mql5.com/en/docs/python_metatrader5)). **This is the key point for minimising external-feed dependence:** our 1m–15m bars come from the same terminal that executes the trades, so signal data and execution data are consistent by construction and we need no third-party price feed.

This fully covers the FTMO-relevant requirements: reading live equity/balance/positions, placing/modifying/closing orders with SL/TP, and computing signals on intraday timeframes — all in deterministic Python with no LLM on the hot path.

### Known limitations (the constraints the design must respect)

These are confirmed and are the heart of this reality-check:

1. **Windows-only.** The official `MetaTrader5` wheel runs only on Python for Windows; there is no native Linux/macOS build ([mt5linux project notes](https://github.com/lucas-campagna/mt5linux), [MetaTrader 5 build 2085 release note re: Wine support](https://www.metatrader5.com/en/news/2086)). Linux usage is only possible by running the Windows terminal + Windows Python under **Wine** and bridging to native Linux Python over RPyC (the `mt5linux` / `MT5LinuxEnhanced` packages). That works but adds a fragile layer.
2. **Not headless — the terminal must be running and logged in.** The Python package is an IPC client of a live MT5 terminal; it does not connect to the broker independently. If the terminal is closed or not logged in, every call fails. Community and forum consensus is explicit: "there is no way to use it headless," and the bindings "require a running MT5 terminal which only runs on Windows" ([MQL5 forum — IPC timeout discussion](https://www.mql5.com/en/forum/447937), [Medium — fixing accidental MT disconnection](https://medium.com/the-trading-scientist/how-to-fix-accidental-disconnection-of-metatrader-2365ea899c3f)). In practice the terminal can run minimised/in a session on a VPS, but a GUI process must exist.
3. **IPC timeout / reconnection.** The common failure is `initialize()` returning an "IPC timeout — pipe server didn't answer" error when the terminal is slow or not ready ([MQL5 forum](https://www.mql5.com/en/forum/447937)). To switch account or terminal you must call `mt5.shutdown()` before re-initialising. Broker-side reconnection is handled by the terminal itself (Tools → Options → Server, Reconnect/Retry settings), not by the Python layer, so our Python code must treat the terminal as an external dependency that can transiently disappear and must retry/health-check accordingly ([NYC Servers — MetaTrader error survival guide](https://newyorkcityservers.com/blog/metatrader-error-survival-guide-2025-fix-trade-disabled-more)).
4. **Threading / single-connection caveat.** The package maintains a single IPC connection to one terminal instance per process. It is not designed for heavy multi-threaded concurrent calls into the same connection; the robust pattern is to serialise MT5 calls through one worker (one terminal = one Python controller). This is folklore-level rather than documented, so we treat it as a design guideline: **serialise all MT5 access behind a single broker-adapter object.**
5. **Rate limits are FTMO-side, not package-side.** The package itself imposes no documented request quota, but FTMO does (see §2). Our throttling logic lives in our code, not the library.

**Confidence:** High on capabilities and the Windows-only / not-headless constraints (first-party docs + multiple corroborating sources). Medium on the precise threading behaviour (forum consensus, not documented).

---

## 2. FTMO specifics

### Algorithmic trading and EAs are explicitly allowed

FTMO's own FAQ states plainly that traders may use "discretionary trading, **algorithmic trading, EAs**, etc.", with the only conditions being that trading is legitimate, respects proper risk management, conforms to real market conditions, and is replicable on a live account ([FTMO FAQ — instruments & strategies](https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/)). A fully-automated Python-driven MT5 bot is squarely within these terms. Two caveats are explicit:

- **Third-party EA / capital-allocation risk:** using an off-the-shelf EA that other clients also run can breach the maximum capital-allocation rule (commonly cited as ~$400k per strategy). Because we are building our **own** strategy in Python, this risk does not apply to us — a point in favour of native logic over a shared bridge product.
- **No HFT / no external copy-trading / no glitch or arbitrage exploitation.** These are out of scope for a technical swing/intraday bot anyway, but the design must avoid anything resembling them ([FTMO Forbidden Trading Practices](https://ftmo.com/en/forbidden-trading-practices/)).

### The server-request limits (a hard design constraint)

Directly from FTMO's FAQ: "platform servers have **200 orders at a time** and **2000 max positions per day** limitation, just as the limited acceptance of the server messages (orders and order modifications such as updates of TP/SL and updates of limit orders). If your EA causes hyperactivity to a platform server, we might alert you and ask you to adjust" ([FTMO FAQ](https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/)). The Forbidden Practices framing is stricter still: an account must not become "hyperactive in the sense of an excessive number of more than **2,000 server requests per day**" across opening, modifying, or closing trades/pending orders. **Crucially, every `TRADE_ACTION_SLTP` modification counts as a server request** — so a naive trailing-stop loop that nudges SL every tick would blow the budget fast. Our design must batch/rate-limit order modifications and budget the daily request count.

### Account specifications, server, leverage, order types

- **Platform & server:** FTMO offers MT4, MT5, cTrader, and DXtrade; MT5 is the modern, fully-featured choice and matches our baseline ([FTMO Trading Platforms](https://ftmo.com/en/trading-platforms/)). FTMO runs its own broker servers (e.g. the FTMO-Server group inside MT5); server time is GMT+2 with DST, which matters for our news-blackout timestamps ([The Payout Report — FTMO MT5 setup](https://thepayoutreport.com/ftmo-us-mt5-setup-guide-servers-symbols-settings/)).
- **Leverage:** Standard accounts up to **1:100**; Swing accounts **1:30** ([The Payout Report — FTMO platform & execution](https://thepayoutreport.com/ftmo-us-platform-execution-mt5-netting-fifo/), corroborating FTMO account-spec material). Our position-sizing must read leverage/margin from `account_info()` rather than hard-coding it, since account type changes this.
- **Order types & fill policy:** MT5 supports market orders plus six pending types (buy/sell limit, buy/sell stop, buy/sell stop-limit). FTMO execution is simulated and typically uses Fill-or-Kill semantics — an order fills in full at the price or is rejected, no partials ([The Payout Report — FTMO MT5 netting/FIFO execution](https://thepayoutreport.com/ftmo-us-platform-execution-mt5-netting-fifo/)). Our `order_send` requests must set an appropriate `type_filling` (FOK/IOC/Return) per what the symbol accepts, and we must handle outright rejection as a normal code path.
- **News blackout (this is a real, dated FTMO rule):** On targeted instruments, FTMO Account holders on **Standard** accounts may not open or close any trade — including pending-order, SL, or TP activation — within a window of **2 minutes before to 2 minutes after** a list of restricted macro releases (e.g. US NFP/CPI/FOMC, ECB/BoE/BoC/RBA/RBNZ/SNB rate decisions, Crude Oil Inventories). The restriction does **not** apply during the Evaluation Process, and **Swing** accounts are exempt entirely ([FTMO FAQ — Can I trade news?](https://ftmo.com/en/faq/can-i-trade-news/)). Implication for our bot: the news-blackout module must (a) know the account type and phase, (b) map restricted events to affected currency symbols, and (c) suppress both entries AND modifications/closes — and be aware that even a SL/TP *triggering* inside the window is a breach, so positions on targeted instruments should be flattened or de-risked before the window opens once we are on a funded Standard account.

> **Rules change.** FTMO's news page was last modified 2026-04-30 and the strategies page 2026-05-27 per their own metadata. Treat all the above as current-as-of-June-2026 and re-verify before going live.

---

## 3. TradingView — what a subscription actually buys, and whether it belongs in the loop

### What a paid plan provides

TradingView's paid tiers (Essential $12.95/mo, Plus $29.95/mo, Premium $59.95/mo, Ultimate $199.95/mo, annual billing) gate the features relevant to automation behind specific tiers ([TradingView Pricing](https://www.tradingview.com/pricing/), [Mind Math Money — plans compared](https://www.mindmathmoney.com/articles/tradingview-plans-compared-free-vs-essential-vs-plus-vs-premium-vs-ultimate-2025-guide)):

- **Webhook alerts require at least the Plus plan**; alert counts scale by tier (20 / 100 / 400 / unlimited) ([TradingView — configure webhook alerts](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)).
- **Server-side alerts that fire 24/7 with your machine off require Premium+** — important because a desktop-bound alert is useless for an unattended bot.
- Premium also adds more simultaneous charts, deeper history, second-based timeframes, and advanced chart types — all of which are **human analysis** benefits, not automation primitives.

### Why the webhook to bridge path is not worth it for us

The architecture is the disqualifier. **MT5 has no inbound webhook listener** — it is a desktop app speaking its own broker protocol, so a TradingView alert cannot reach MT5 directly. Every TradingView→MT5 solution inserts a relay: TradingView fires an HTTPS POST to a server you run, and an MQL5 EA or bridge **polls** that server every few hundred milliseconds and then places the trade ([Inakatrader — TradingView webhook to MT5](https://inakatrader.com/blog/tradingview-webhook-to-mt5), [PineConnector](https://www.pineconnector.com/)). Even the better bridges quote end-to-end latency "under ~300 ms to ~1 s" with a polling loop and an external relay in the path ([PineConnector latency claims](https://www.pineconnector.com/blogs/pico-blog/bridging-the-gap-tradingview-to-mt5-automation)).

Stacked against our locked baseline, this adds: (1) a recurring TradingView subscription; (2) a public webhook endpoint to host and secure; (3) a bridge/relay product or self-built listener as a new point of failure; (4) network and polling latency; and (5) a **second source of truth** for signals separate from the MT5 data the execution layer already sees — a recipe for signal/execution divergence. We gain nothing functional, because our signals are deterministic Python that can read the exact same MT5 bars and act on them in-process with no network hop.

**There is no scenario in this project where TradingView should be the signal source.** TradingView would only be the right signal origin if the edge depended on a Pine indicator or TradingView-exclusive data we could not reproduce in Python — which contradicts the project's deterministic-Python, technical-signal premise. The genuine value TradingView offers us is **human-facing**: fast manual chart review, prototyping a signal idea visually before coding it in Python, and ad-hoc alerting for a human supervisor. That is worth at most a cheap tier, and even the free tier covers most of it.

**Recommendation:** Do **not** put TradingView on the hot path and do **not** buy a Premium plan for automation. If a team member wants TradingView for manual research/charting, the free or Essential tier suffices; treat it as a discretionary research cost, not infrastructure.

---

## 4. cTrader (cBot) — brief comparison

FTMO supports cTrader, and FTMO permits cBots ([FTMO Trading Platforms](https://ftmo.com/en/trading-platforms/), [The Payout Report — FTMO platforms MT4 vs MT5 vs cTrader vs DXtrade](https://thepayoutreport.com/ftmo-global-platforms-mt4-vs-mt5-vs-ctrader-vs-dxtrade/)). On pure automation ergonomics, cTrader is arguably **better engineered than MT5**: cBots are written in modern **C#/.NET** with first-class Visual Studio tooling, cTrader Automate is a cleaner API than MQL5, the platform offers **cloud cBot hosting** (so you needn't keep a desktop terminal alive), and its ECN-style execution and transparency are often praised for algo/scalping ([New York City Servers — cTrader vs MetaTrader for algo](https://newyorkcityservers.com/blog/ctrader-vs-metatrader-algo-trading-comparison), [DailyForex — cTrader vs MT5](https://www.dailyforex.com/forex-articles/ctrader-vs-mt5/229151)).

However, cTrader does **not** justify overturning the baseline for this project, for three reasons:

1. **Language mismatch.** Our project is committed to **Python** for strategy logic, backtesting, and the AI improvement loop. cBots are C#; choosing cTrader means either rewriting the brain in C# or building a Python↔cTrader bridge via the **cTrader Open API** (FIX/Protobuf over the network) — which reintroduces exactly the kind of external moving part we are avoiding with MT5's local IPC.
2. **Ecosystem.** Python's MT5 binding plugs directly into pandas/NumPy and the rest of our analysis stack; the MT5 community and data tooling are vastly larger.
3. **No decisive FTMO-side advantage.** Both platforms are simulated-execution on FTMO servers under the same firm rules and the same 2,000-request limit. cTrader's execution edge is marginal for a non-HFT intraday/swing strategy.

**Conclusion:** Keep cTrader on the radar as a fallback if MT5's headless/Windows constraints become unmanageable, but it is not a reason to change the baseline now.

---

## 5. Running MT5 headless 24/5 — practical reliability notes

The single biggest operational risk is that the `MetaTrader5` Python layer is only a client of a **live, logged-in Windows terminal**, so our reliability work is really about keeping that terminal healthy:

- **Windows host is effectively mandatory.** Simplest robust setup is a **Windows VPS** (or Windows VM) running the FTMO MT5 terminal plus our Python process. FTMO explicitly permits VPS/VPN use ([FTMO FAQ — Can I travel or use VPN/VPS?](https://ftmo.com/en/faq/can-i-travel-or-use-vpn-vps/)). This feeds directly into track R7 (infra/VPS).
- **Wine/Linux is possible but second-tier.** Running the Windows terminal + Windows Python under Wine and bridging via `mt5linux`/RPyC works and is used in production by some, but adds a translation layer and more failure surface ([mt5linux](https://github.com/lucas-campagna/mt5linux), [Medium — MT5 in Linux with Docker](https://medium.com/@asc686f61/use-mt5-in-linux-with-docker-and-python-f8a9859d65b1)). Prefer native Windows unless there is a strong infra reason otherwise.
- **The terminal must stay open and logged in.** Keep it running (it can be minimised); ensure auto-login is configured and the chart/symbols we trade are in Market Watch so `copy_rates`/`symbol_info_tick` return data.
- **Common failure modes to engineer around:**
  - *IPC timeout on `initialize()`* — terminal not up yet or hung; mitigate with a startup health-check, retry/backoff, and a watchdog that restarts the terminal process if Python cannot reach it ([MQL5 forum — IPC timeout](https://www.mql5.com/en/forum/447937)).
  - *Broker disconnects* — the terminal reconnects on its own (configure Reconnect/Retry); our code must treat "no connection" as transient, pause trading, and resume on reconnect rather than crashing ([Medium — fixing accidental MT disconnection](https://medium.com/the-trading-scientist/how-to-fix-accidental-disconnection-of-metatrader-2365ea899c3f)).
  - *Terminal/VPS crash* — supervise the terminal process (e.g. a watchdog or scheduled task that relaunches it), and have the Python side `shutdown()` and re-`initialize()` cleanly on reconnection.
  - *Stale data / trade-disabled states* — validate `terminal_info().connected` and `account_info()` freshness before every trading decision; never act on stale bars.
- **Weekend handling.** Forex runs 24/5; build in a clean stop at week close and a safe restart at week open, and verify the news-blackout schedule reloads.

A health-checking watchdog (Python pings the terminal; if dead, relaunch terminal, re-login, re-initialise) is the standard mitigation and should be a first-class component of our ops design under R7.

---

## Platform-constraints checklist (the design MUST respect these)

1. **Windows runtime.** The bot's broker adapter runs on Windows (VPS/VM), or under a Wine+RPyC bridge as a fallback. No assumption of a native-Linux MT5 binding.
2. **Live MT5 terminal dependency.** A logged-in MT5 terminal process must be running at all times; treat it as an external service that can disappear. Include a watchdog that restarts and re-initialises it.
3. **Single serialised MT5 connection.** Route all MT5 calls through one broker-adapter object; do not fan out concurrent calls into the same IPC connection.
4. **Connection health gating.** Before any trade decision, verify `terminal_info().connected` and fresh `account_info()`; pause trading on disconnect and resume cleanly.
5. **Server-request budget.** Stay under **2,000 server requests/day** and **200 simultaneous orders**. Count every open/modify/close — including SL/TP updates and pending-order changes — against the budget. Rate-limit or batch trailing-stop / SL-TP modifications; no per-tick order edits.
6. **News blackout.** Implement a per-event, per-symbol blackout of **-2 min to +2 min** around FTMO's restricted releases for Standard funded accounts; suppress entries AND closes/modifications, and pre-flatten/de-risk targeted instruments before the window so a SL/TP cannot trigger inside it. Make it account-type- and phase-aware (exempt during Evaluation and for Swing). Source the event schedule from FTMO's calendar and keep it updated.
7. **Read config from the account, not constants.** Pull leverage, margin, contract size, min stop distance, and allowed fill policy from `account_info()` / `symbol_info()` at runtime; never hard-code FTMO specs that can change.
8. **Order execution realities.** Set an appropriate `type_filling` per symbol (FOK/IOC/Return) and handle full-rejection (no partial fills) as a normal path with retry/abort logic.
9. **No forbidden patterns.** No HFT, no external copy-trading, no glitch/arbitrage exploitation; keep behaviour "replicable on a live account." Build our own strategy (avoids the third-party-EA capital-allocation risk).
10. **Self-contained data.** Source signal bars/ticks from MT5 (`copy_rates_*`, `copy_ticks_*`) so signal and execution share one consistent data source; avoid mandatory external feeds on the hot path.
11. **No TradingView / webhook on the hot path.** Signals computed in-process in Python; no external relay or webhook in the live trade loop.

---

## Go / No-Go recommendation

### MT5 + Python baseline: **GO (confirmed)**

The official, first-party `MetaTrader5` Python package does everything the FTMO bot requires — live equity/balance/position reads, order placement/modification/closure with SL/TP, and native intraday market data — in deterministic Python with no LLM on the hot path. FTMO explicitly allows algorithmic trading and EAs, and the platform's hard limits (2,000 requests/day, 200 concurrent orders, news blackout) are well-documented and designable-around. The Windows-only and not-headless constraints are real but are infrastructure problems (a supervised Windows VPS + terminal watchdog), not capability gaps. No evidence was found that would justify overturning the locked baseline; the evidence strongly supports it.

### TradingView: **NO-GO for the hot path; optional cheap tier for human research only**

A TradingView subscription buys better human charting/alerting and Pine-based signals via webhook — but every webhook→MT5 path requires an external relay/poller (MT5 has no inbound webhook), adding cost, a new failure point, latency, and a second signal source that can diverge from MT5 execution data. Since our signals are deterministic Python with direct MT5 data and execution, TradingView adds risk for no functional benefit. **Do not subscribe to Premium for automation.** A free or Essential tier is fine purely as a discretionary human chart-review/prototyping tool. TradingView would only become the right signal source if the edge depended on a TradingView-exclusive indicator or dataset we could not reproduce in Python — which is not the case for this project.

### cTrader: keep as a documented fallback, do not switch

C#/.NET cBots and cloud hosting are genuinely cleaner for automation, but switching abandons our Python strategy/backtest/AI stack and replaces MT5's local IPC with a network API bridge, with no decisive FTMO-side advantage for a non-HFT strategy. Revisit only if MT5's Windows/headless constraints prove unmanageable in production.

---

## Sources

**Primary — MetaTrader5 / MQL5 (first-party):**
- [MQL5 — Python Integration reference (function list & example)](https://www.mql5.com/en/docs/python_metatrader5)
- [MQL5 — initialize() (Python)](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py)
- [MQL5 — account_info() (Python)](https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py)
- [MQL5 — order_send() (Python)](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)
- [MetaTrader 5 build 2085 release note — Python integration & Wine support](https://www.metatrader5.com/en/news/2086)
- [MQL5 forum — IPC timeout on initialize()](https://www.mql5.com/en/forum/447937)

**Primary — FTMO (first-party):**
- [FTMO FAQ — Which instruments / strategies am I allowed to use (EAs, 200 orders / 2000 positions limit)](https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/)
- [FTMO — Forbidden Trading Practices (2,000 server requests/day, no HFT)](https://ftmo.com/en/forbidden-trading-practices/)
- [FTMO FAQ — Can I trade news? (2-min blackout, restricted events table)](https://ftmo.com/en/faq/can-i-trade-news/)
- [FTMO — Trading Platforms (MT4/MT5/cTrader/DXtrade)](https://ftmo.com/en/trading-platforms/)
- [FTMO FAQ — Can I travel or use VPN/VPS?](https://ftmo.com/en/faq/can-i-travel-or-use-vpn-vps/)

**Primary — TradingView (first-party):**
- [TradingView — Pricing](https://www.tradingview.com/pricing/)
- [TradingView — How to configure webhook alerts](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)

**Corroborating / secondary:**
- [The Payout Report — FTMO MT5 setup: servers, symbols, settings](https://thepayoutreport.com/ftmo-us-mt5-setup-guide-servers-symbols-settings/)
- [The Payout Report — FTMO MT5 netting/FIFO execution & leverage](https://thepayoutreport.com/ftmo-us-platform-execution-mt5-netting-fifo/)
- [The Payout Report — FTMO platforms: MT4 vs MT5 vs cTrader vs DXtrade](https://thepayoutreport.com/ftmo-global-platforms-mt4-vs-mt5-vs-ctrader-vs-dxtrade/)
- [TradePretty — Managing Orders with MT5 and Python](https://tradepretty.com/orders-mt5-python/)
- [Medium — Algorithmic Trading with Python and MT5: Modifying Open Trades](https://medium.com/@elospieconomics/algorithmic-trading-with-python-and-mt5-modifying-open-trades-8622d31632f3)
- [Inakatrader — How TradingView Webhook to MT5 Works (2026)](https://inakatrader.com/blog/tradingview-webhook-to-mt5)
- [PineConnector — TradingView Alerts to MT4/MT5 (bridge, latency)](https://www.pineconnector.com/)
- [PineConnector — Bridging the Gap: TradingView to MT5 Automation](https://www.pineconnector.com/blogs/pico-blog/bridging-the-gap-tradingview-to-mt5-automation)
- [Mind Math Money — TradingView plans compared (2026)](https://www.mindmathmoney.com/articles/tradingview-plans-compared-free-vs-essential-vs-plus-vs-premium-vs-ultimate-2025-guide)
- [New York City Servers — cTrader vs MetaTrader for algo trading](https://newyorkcityservers.com/blog/ctrader-vs-metatrader-algo-trading-comparison)
- [DailyForex — cTrader vs MT5](https://www.dailyforex.com/forex-articles/ctrader-vs-mt5/229151)
- [mt5linux — MetaTrader5 for Linux (Wine + RPyC bridge)](https://github.com/lucas-campagna/mt5linux)
- [Medium — Use MT5 in Linux with Docker and Python](https://medium.com/@asc686f61/use-mt5-in-linux-with-docker-and-python-f8a9859d65b1)
- [Medium — How to fix accidental disconnection of MetaTrader](https://medium.com/the-trading-scientist/how-to-fix-accidental-disconnection-of-metatrader-2365ea899c3f)
- [New York City Servers — MetaTrader Error Survival Guide 2026](https://newyorkcityservers.com/blog/metatrader-error-survival-guide-2025-fix-trade-disabled-more)
