# How the Bot Trades — Plain-English Overview (Config v4)

> A non-technical walkthrough of the live EURUSD trading bot. **No code here** — just the
> idea, the rules, and the formulas, written so you can understand the whole machine and
> tell us where to improve it. If you spot a better rule, a new filter, or a whole new
> strategy idea, jump to the last section ("Where Your Feedback Goes") and mark it up.
>
> This describes the **promoted live config, version 4** (`state/config/HEAD → v4`).

---

## 1. The one-sentence version

Every weekday, during the few hours when London and New York trade at the same time, the
bot watches EURUSD for the first 30 minutes, draws a box around the high and low of that
window, and then bets that price will **break out** of the box and keep going — but only
if the market looks "clean" enough to trust, and only risking a tiny, fixed slice of the
account on each trade.

It is built for the **FTMO 2-Step Challenge**, so the single most important rule isn't
"make money" — it's **"never break FTMO's loss limits."** Safety always wins over profit.

---

## 2. The cast of characters (how a trade flows)

Think of the bot as an assembly line with four stations. A trade only happens if it passes
every station, in order:

1. **The Strategy** — the idea generator. It looks at price and says "here's a trade worth
   taking" or "nothing right now." It never thinks about money or position size.
2. **The Risk Governor** — the safety officer. It takes the Strategy's idea and decides
   *how big* (or whether at all). It can shrink a trade or reject it, but it can **never
   make a trade bigger or riskier** than the Strategy asked.
3. **Execution** — the hands. It places the actual order with the broker (MT5) and tracks it.
4. **The Journal** — the memory. Every decision, fill, and number is written down forever
   so the trade can be audited and the bot improved later.

A separate, **offline** "improvement loop" studies the journal and *proposes* tweaks — but
it never touches a live trade. Every proposal must pass the backtester and a human before
it goes live (see §10–11).

> **Golden rule:** the Strategy is a *pure idea machine*. Give it the same price history and
> the same moment in time, and it always produces the exact same decision. No randomness, no
> "gut feel," no hidden memory. That's what makes it testable.

---

## 3. The trading idea, in plain English

The strategy is called **`SessionBreakoutER`**. It combines three classic ideas:

- **Session timing** — only trade during the London/New York overlap, the most liquid and
  most directional part of the EURUSD day.
- **Opening-range breakout** — let the market set a high and low in the first part of the
  session, then trade the break of that range.
- **Regime filter** — only take the breakout if the market is *trending cleanly* and its
  *volatility is in a healthy middle band* (not dead-quiet, not chaotic). This is the "ER"
  in the name, and it's the bot's secret sauce — it throws away most breakouts and keeps
  only the ones likely to follow through.

---

## 4. A day in the life of the bot

Here is exactly what happens, in order, every trading day (all times Europe/London,
adjusted automatically for daylight saving):

**Step 1 — Wait for the session.** Nothing happens until **13:00 London**. Outside the
13:00–16:00 window, the bot simply doesn't trade. (London/NY overlap.)

**Step 2 — Build the box (the "opening range").** From 13:00 to 13:30 (the first
**30 minutes**), the bot records the **highest high** and **lowest low**. That's the box:

```
range_high = highest high during 13:00–13:30
range_low  = lowest  low  during 13:00–13:30
```

**Step 3 — Set the trigger levels.** It adds a small **buffer of 1.5 pips** above and below
the box so a tiny wick doesn't trigger a false break:

```
long trigger  = range_high + 1.5 pips
short trigger = range_low  − 1.5 pips
```

**Step 4 — Wait for a clean break.** After 13:30, if a **completed 15-minute candle**
closes above the long trigger (or below the short trigger), that's a breakout candidate.
The bot only ever acts on *closed* candles — never a half-formed one.

**Step 5 — Check the regime gate (the hard filter).** Before allowing the trade, the market
must pass **both** tests (explained with formulas in §5). If it fails, the trade is thrown
away and logged as "regime_gate_failed" — so we can later study what we skipped.

**Step 6 — Check the news blackout.** If a high-impact EUR or USD news event is within
15 minutes (before or after), or we're within 2 hours of a weekend/long close, **no trade**.
If the news calendar can't be read at all, the bot assumes the worst and **stays out**.

**Step 7 — Place the trade.** If everything passes, the Strategy hands a fully-specified
trade to the Risk Governor (direction, entry price, stop level, target). The Governor sizes
it and Execution places it.

**Step 8 — One shot per side.** Once it has fired a long, it won't take another long that
day (same for shorts). This caps the number of trades and avoids over-trading a choppy day.

**Step 9 — Manage and exit.** The trade runs to either its stop loss or its target (see §7).
At session end, any unfilled pending order is cancelled — nothing is carried overnight.

---

## 5. The two indicators (with formulas)

These are the only two numbers the regime gate cares about. Both are computed over a
**14-candle** window.

### 5.1 Efficiency Ratio (ER) — "is the market moving in a straight line?"

ER asks: of all the up-and-down wiggling price did over the last 14 candles, how much of it
actually went *somewhere*? A clean trend scores near **1.0**; aimless chop scores near **0**.

```
ER = | close_now − close_14_bars_ago |  ÷  Σ | each bar's close − previous close |
       (net distance travelled)              (total distance walked, wiggles included)
```

- A straight march up: net distance ≈ total distance → ER ≈ 1.0 ✅ (trustworthy breakout)
- A market that ends where it started after lots of zig-zag: net ≈ 0 → ER ≈ 0 ❌ (chop)

**The gate:** the breakout is only allowed if `ER ≥ 0.32` (this is the **er_threshold**, the
single most important tuning lever; v4 raised it from 0.30 to 0.32 to be slightly pickier).

### 5.2 Average True Range (ATR) — "how volatile is the market right now?"

ATR measures the typical size of a candle, including gaps. First, each candle's **True Range**
is the largest of three distances:

```
True Range = max(  high − low,
                   | high − previous close |,
                   | low  − previous close | )
```

Then ATR is a smoothed (Wilder) average of True Range over 14 candles — start with a simple
average of the first 14, then each new bar nudges it:

```
ATR_new = ( ATR_old × 13  +  newest True Range ) ÷ 14
```

ATR is expressed in **pips**. It does two jobs: it defines the **volatility band** (next
paragraph) and it sets the **stop-loss distance** (§7).

### 5.3 The volatility band — "not too quiet, not too wild"

The bot classifies volatility into LOW / NORMAL / HIGH and **only trades NORMAL**:

- **LOW** (skip): ATR below the **floor of 5 pips**, *or* ATR ranks in the bottom 20% of its
  recent history. Too quiet — breakouts fizzle.
- **HIGH** (skip): ATR above the **ceiling of 22 pips**, *or* ATR ranks in the top 10% of
  recent history. Too wild — stops get too wide for safe fixed-risk sizing.
- **NORMAL** (trade): everything in between.

"Ranks in the bottom 20%" uses a simple **percentile**: of the recent ATR readings, what
fraction are ≤ today's ATR? That fraction is the percentile.

### 5.4 The full gate

```
regime_gate_passed  =  ( ER ≥ 0.32 )  AND  ( volatility is NORMAL )
```

Both conditions must hold. If either fails, no trade. This filter is deliberately strict —
it's normal and expected for the bot to skip most days entirely.

---

## 6. Entry rules (summary)

- **Direction:** long if price breaks above the box, short if below.
- **Entry type:** a **stop order** placed *at the trigger level* — so we get filled as price
  breaks through, controlling slippage, rather than chasing after a candle closes.
- **Expiry:** the pending order is cancelled at session end if it never fills. No overnight risk.
- **One breakout per side per day.**

---

## 7. Stop loss and target — the exit (current v4)

### 7.1 Stop loss

The stop is placed at whichever is **further** away (safer) of two choices:

```
stop distance = max(  the opposite side of the opening-range box,
                      1.2 × ATR  )
```

So a wider, calmer-market ATR gives a wider stop; the box structure gives a floor. This
stop distance, in pips, is what the Risk Governor uses to size the position.

### 7.2 Target — "1R, take it all"

"R" means **one unit of risk** — the distance from entry to stop. The current live config
takes the **entire position off at a 1R profit** (a 1:1 reward-to-risk target) and uses
**no partial exits, no break-even move, no trailing stop**:

```
target_r_multiples = [1.0]      # one target, at 1× the risk
partial_fractions  = [1.0]      # close 100% of the position there
move_be_after_r    = none       # stop never moved to break-even
```

> **Why so simple?** The team *built* a fancier exit (take half at 1R, let the rest run to
> 2R, trail the stop). On paper it sometimes looked better per-trade, but when tested on
> held-out data it **lowered** the risk-adjusted return and **failed the lockbox test**
> (see `docs/EXIT_MODEL.md`: the fancy exit scored +0.09R / profit-factor 1.17 versus the
> simple exit's +0.30R / profit-factor 2.03). On *this* high-win-rate strategy, simpler won.
> This is the clearest example of the project's core belief: **a higher per-trade average is
> not a verdict — only the full test suite is.** The fancy exit machinery still exists in the
> code, switched off; it can be re-enabled for a *different* strategy if testing justifies it.

---

## 8. Position sizing — how big is each trade?

The Strategy never picks a size. The **Risk Governor** does, from one formula. The goal is to
risk a fixed **0.35% of account equity** per trade:

```
risk in dollars   = 0.35% × current equity

position (lots)   =        risk in dollars
                    ───────────────────────────────────────
                    stop distance (pips) × $/pip × (1 + 0.20 buffer)
```

The **20% buffer** is padding for spread and slippage, so the real loss if stopped out stays
*under* the 0.35% target rather than over it. The result is rounded **down** to the broker's
lot step (never up), and re-checked against every FTMO limit before approval. If it can't fit
safely even at the minimum lot size, the trade is **vetoed**.

---

## 9. The safety system — never breaching FTMO

This is the part the whole project is really about. FTMO has two hard loss limits, and
breaching either ends the challenge:

```
Daily floor   = (balance at 00:00 Prague time)  −  5% of the initial balance
Overall floor =  initial balance               − 10% of the initial balance
```

The Governor checks **equity** (balance + open trade P/L) against both floors *before* every
trade, assuming the new trade plus all open trades hit their stops at once. If that worst case
would touch a floor, the trade is shrunk or rejected.

On top of that, a **kill-switch** watches how much of today's 5% budget has been spent:

| Daily budget used | What happens |
|---|---|
| 0–40% | Normal trading |
| ≥ 40% | **Reduce** — new trades are sized smaller |
| ≥ 60% | **Halt** — no new trades for the rest of the day (existing ones still managed) |
| ≥ 85% | **Flatten** — close everything, and stay off until a **human** restarts the bot |

The clock resets at **00:00 Prague time** each day. The kill-switch only ever *reduces* risk,
and a flatten never auto-resumes — a person must clear it.

---

## 10. The "fail safe" principle

Whenever anything is unclear or broken — stale price data, an unreadable news calendar,
out-of-order candles, a degenerate calculation — the bot does **nothing new**. The only
actions always allowed are the ones that *reduce* risk (closing or protecting an open trade).
Ambiguity never produces a new trade.

---

## 11. How any change gets proven before it goes live

Nothing — not a parameter tweak, not a new strategy — ships on opinion. It must clear the
**backtester**, which is treated as the final judge. The bar to clear ("R6 gates"):

- Average expectancy ≥ **0.10R** per trade
- Profit factor ≥ **1.3**
- Annualised Sharpe ≥ **1.0**, Sortino ≥ **1.5**
- At least **200 trades** (enough to be meaningful)
- A "deflated Sharpe" score ≥ **0.95** (penalises us for trying many variations — guards
  against curve-fitting)
- **ZERO** simulated FTMO breaches — a hard, non-negotiable gate

Then two anti-overfitting checks:

- **Walk-forward:** the strategy is re-tested on rolling out-of-sample chunks of history;
  most chunks must be profitable and none catastrophic.
- **Lockbox:** a slice of data sealed away and *never* looked at during tuning. The change
  must pass on this untouched data too. (This is what killed the fancy exit in §7.)

---

## 12. The offline improvement loop

A set of scheduled AI agents study the journal each week and **propose** changes — but only
parameter tweaks within pre-approved bounds (the "allowed levers"). Each proposal is run
through the exact test suite in §11, and a **human approves every promotion**. Config moves
forward one numbered version at a time and is fully reversible. (That's how v4 came to be:
the optimizer proposed nudging the ER threshold 0.30 → 0.32, it passed the gates, and a human
promoted it.) Structural changes — new exit logic, new indicators, whole new strategies — are
human/agent dev work, validated through the same harness.

---

## 13. The current v4 settings, at a glance

| Setting | Value | Plain meaning |
|---|---|---|
| Instrument / timeframe | EURUSD, 15-minute | What and how often it looks |
| Session window | 13:00–16:00 London | London/NY overlap only |
| Opening range | first 30 min | The box |
| Breakout buffer | 1.5 pips | Wick-noise guard |
| ER window / threshold | 14 / **0.32** | Trend-cleanliness filter (the key lever) |
| ATR window | 14 | Volatility measure |
| ATR floor / ceiling | 5 / 22 pips | Volatility band edges |
| ATR low / high percentile | 20% / 90% | Relative volatility band edges |
| Stop loss | max(box, 1.2 × ATR) | How far the stop sits |
| Target | **1.0R, full exit** | Take it all at 1:1; no partials/trail/BE |
| Risk per trade | 0.35% of equity | Fixed small bet |
| Slippage buffer | 20% | Padding so real risk ≤ target |
| News blackout | ±15 min, 2h pre-close | Stay out around news/closes |
| Trades per side per day | 1 | Anti-over-trading |

---

## 14. Where your feedback goes — the parts you can change

The whole point of this document is so you can suggest improvements. Here's the menu of
*what kinds* of changes are possible, with the questions worth asking for each. Mark up
anything below, or add your own.

**A. Tune an existing dial (easiest — the "levers").**
These are numbers the bot already understands; a change is a backtest away.
- Is **ER 0.32** too picky or not picky enough? (Higher = fewer, cleaner trades.)
- Is the **30-minute opening range** right? Try 15 or 60?
- Are the **ATR band edges (5/22 pips, 20%/90%)** cutting off good trades or letting in bad ones?
- Is **0.35% risk** per trade too timid or too aggressive for the FTMO math?
- Is the **1.5-pip breakout buffer** filtering noise or causing late entries?

**B. Change the exit logic.**
- Should we re-test letting winners run (partial at 1R, rest to 2R, trailing stop)? It was
  rejected once on this strategy — but a *new* strategy might love it.
- Should the stop move to break-even after some profit?
- Is a fixed 1R target leaving money on the table, or is its high win rate worth keeping?

**C. Add a new entry filter / indicator.**
- A **higher-timeframe trend bias** (e.g. only take longs if the daily trend is up)?
- A **time-of-day or day-of-week** filter (skip Mondays? avoid the last 30 min)?
- A **"volatility-of-volatility"** gate, or a momentum/volume confirmation?
- A different **regime measure** instead of (or alongside) ER?

**D. Propose a whole new strategy.**
The engine is built to swap strategies in and out. Ideas worth specifying:
- A **mean-reversion** play (fade extremes) for choppy days the breakout skips.
- A **different session** (Asian range, or the London open before NY).
- A **second instrument** (GBPUSD, gold) to prove the pipeline generalises.

**E. Add a fundamental / news overlay.**
- A "shadow-mode" macro bias that can tell the bot to trade smaller or stand down around big
  events — without ever forcing a trade.

> **How to give feedback:** describe the idea in plain words and, if you can, the *rule* —
> e.g. "only go long if yesterday's daily candle closed up" or "skip trades when ATR is in the
> top 5%." We'll translate it into a precise, testable change, run it through the §11 gates +
> walk-forward + lockbox, show you the numbers, and only then — with your approval — promote
> it to a new version. Higher average profit alone never wins; it has to clear the whole suite.

---

*This overview reflects live config v4 (promoted 2026-06-03). The authoritative detail lives
in `docs/specs/01–07`; the build state in `docs/IMPLEMENTATION_STATUS.md`; the exit-model
decision in `docs/EXIT_MODEL.md`.*
